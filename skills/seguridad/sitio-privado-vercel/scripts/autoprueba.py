#!/usr/bin/env python3
"""autoprueba.py · prueba real de sitio-privado-vercel, sin red externa y sin llaves. Sale con 0 si todo cumple.

1. Revisa sin ejecutar nada: vercel.json (CSP con report-uri y report-to, Reporting-Endpoints, HSTS y demás
   cabeceras, /data/* reescrito a la función), index.html sin scripts ni estilos en línea, .vercelignore y
   .env.example sin valores reales.
2. Con Node: levanta la plantilla en 127.0.0.1 con un puerto libre (scripts/servidor_local.cjs, que ejecuta las
   funciones reales de api/) con una contraseña y un secreto generados al vuelo, y comprueba por HTTP:
   401 sin cookie · 401 con contraseña mala · cookie HttpOnly; Secure; SameSite=Strict con la buena · 200 con
   cookie válida · 401 con cookie manipulada, caducada o firmada con otro secreto · 429 + Retry-After tras 5
   fallos · rotación con SESSION_SECRET_PREVIOUS · salida · buzón CSP (acepta los dos formatos, rechaza basura)
   · 500 si faltan las variables · ruta transversal bloqueada · .env.example no se sirve.
   Sin Node, la parte HTTP se OMITE con aviso claro y la salida es 0 (lo estático sí se comprueba).
   Para exigir Node (p. ej. en CI): SITIO_EXIGIR_NODE=1 → sin Node sale con 1.
Solo biblioteca estándar de Python.
"""
import base64, hashlib, hmac, http.client, json, os, pathlib, re, secrets, shutil, subprocess, sys, threading, time

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
SITIO = RAIZ / 'templates' / 'sitio'
SERVIDOR = AQUI / 'servidor_local.cjs'

ok, fallos = 0, []


def check(cond, que):
    global ok
    if cond:
        ok += 1
        print('  ok   ', que)
    else:
        fallos.append(que)
        print('  FALLA', que)


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


# ---------------------------------------------------------------- 1. comprobaciones estáticas
print('Configuración (sin ejecutar):')
vj = json.loads((SITIO / 'vercel.json').read_text(encoding='utf-8'))
rutas = vj.get('routes', [])
general = next((r for r in rutas if r.get('src') == '/(.*)' and r.get('headers')), {})
cab = general.get('headers', {})
csp = cab.get('Content-Security-Policy', '')
directivas = {d.strip().split(' ')[0]: d.strip() for d in csp.split(';') if d.strip()}
check(bool(csp), 'vercel.json declara Content-Security-Policy para todo el sitio')
check(directivas.get('report-uri') == 'report-uri /api/csp-report', 'la CSP tiene report-uri /api/csp-report')
grupo = directivas.get('report-to', 'report-to ').split(' ', 1)[1].strip()
endpoints = dict(re.findall(r'([A-Za-z0-9_-]+)="([^"]+)"', cab.get('Reporting-Endpoints', '')))
check(bool(grupo) and endpoints.get(grupo) == '/api/csp-report',
      'la CSP tiene report-to «%s» y Reporting-Endpoints lo apunta a /api/csp-report' % grupo)
check(directivas.get('script-src') == "script-src 'self'", "script-src 'self' (sin 'unsafe-inline' ni 'unsafe-eval')")
check("'unsafe-" not in csp, "ninguna directiva usa 'unsafe-*'")
for d, v in (('default-src', "'self'"), ('object-src', "'none'"), ('frame-ancestors', "'none'"),
             ('base-uri', "'self'"), ('form-action', "'self'")):
    check(directivas.get(d) == '%s %s' % (d, v), 'CSP: %s %s' % (d, v))
hsts = re.search(r'max-age=(\d+)', cab.get('Strict-Transport-Security', ''))
check(bool(hsts) and int(hsts.group(1)) >= 31536000, 'HSTS con max-age de 1 año o más')
for k, v in (('X-Frame-Options', 'DENY'), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'),
             ('Cross-Origin-Opener-Policy', 'same-origin')):
    check(cab.get(k) == v, '%s: %s' % (k, v))
check('camera=()' in cab.get('Permissions-Policy', ''), 'Permissions-Policy restringe cámara, micrófono y ubicación')
datos = next((r for r in rutas if r.get('src') == '/data/(.*)'), {})
check(datos.get('dest') == '/api/data?file=$1' and rutas.index(datos) < [r.get('handle') for r in rutas].index('filesystem'),
      '/data/* se reescribe a /api/data antes de servir archivos estáticos')
check(vj.get('functions', {}).get('api/data.js', {}).get('includeFiles') == 'data/**', 'api/data.js empaqueta data/**')
html = (SITIO / 'index.html').read_text(encoding='utf-8')
check(not re.search(r'<script(?![^>]*\bsrc=)[^>]*>', html, re.I), 'index.html sin <script> en línea (compatible con la CSP)')
check(not re.search(r'\son[a-z]+\s*=', html, re.I) and not re.search(r'\sstyle\s*=', html, re.I),
      'index.html sin manejadores on*= ni atributos style')
ign = (SITIO / '.vercelignore').read_text(encoding='utf-8').split()
check('.env' in ign and '.env.*' in ign and '*.md' in ign, '.vercelignore excluye .env, .env.* y *.md')
env_ej = (SITIO / '.env.example').read_text(encoding='utf-8')
check('REEMPLAZAR' in env_ej and not re.search(r'^SESSION_SECRET=(?!REEMPLAZAR)\S{20,}', env_ej, re.M),
      '.env.example solo trae marcadores, ningún valor real')
n_estaticas = ok + len(fallos)

# ---------------------------------------------------------------- 2. pruebas HTTP con Node
node = os.environ.get('NODE') or shutil.which('node')
if node and not pathlib.Path(node).exists() and not shutil.which(node):
    node = None
if not node:
    print('\nOMITIDO: no se encontró Node (instálalo o define NODE=/ruta/a/node). Las pruebas HTTP no se corrieron.')
    if os.environ.get('SITIO_EXIGIR_NODE') == '1':
        print('%d de %d comprobaciones · FALLA (SITIO_EXIGIR_NODE=1 y no hay Node)' % (ok, ok + len(fallos)))
        sys.exit(1)
    estado = 'OK' if not fallos else 'FALLA'
    print('%d de %d comprobaciones estáticas · pruebas HTTP OMITIDAS (sin Node) · %s' % (ok, ok + len(fallos), estado))
    sys.exit(0 if not fallos else 1)

CLAVE = 'prueba-' + secrets.token_urlsafe(12)
SAL = secrets.token_bytes(16)
HASH = 'scrypt$%s$%s' % (b64u(SAL), b64u(hashlib.scrypt(CLAVE.encode(), salt=SAL, n=16384, r=8, p=1, dklen=32)))
SECRETO = secrets.token_urlsafe(32)
SECRETO_NUEVO = secrets.token_urlsafe(32)


class Servidor:
    def __init__(self, env_extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('SITE_', 'SESSION_', 'LOGIN_'))}
        env.update(env_extra)
        self.p = subprocess.Popen([node, str(SERVIDOR), '--dir', str(SITIO), '--port', '0'], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.err = []
        threading.Thread(target=lambda: [self.err.append(l) for l in self.p.stderr], daemon=True).start()
        linea = self.p.stdout.readline().strip()
        m = re.match(r'LISTO http://([\d.]+):(\d+)', linea)
        if not m:
            self.p.kill()
            raise SystemExit('el servidor local no arrancó: %r %s' % (linea, ''.join(self.err)[-500:]))
        self.host, self.port = m.group(1), int(m.group(2))

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None):
        c = http.client.HTTPConnection(self.host, self.port, timeout=20)
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo)
        try:
            c.request(metodo, ruta, body=cuerpo, headers=cabeceras or {})
            r = c.getresponse()
            datos = r.read()
        except (OSError, http.client.HTTPException) as e:  # el servidor se cayó o cortó: cuenta como fallo, no rompe
            print('  (sin respuesta a %s %s: %s)' % (metodo, ruta, type(e).__name__))
            c.close()
            return 0, {'set-cookie-todas': []}, b''
        cab = {k.lower(): v for k, v in r.getheaders()}
        cab['set-cookie-todas'] = r.headers.get_all('Set-Cookie') or []
        c.close()
        return r.status, cab, datos

    def cerrar(self):
        self.p.terminate()
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


def token(secreto, exp_ms):
    payload = b64u(json.dumps({'exp': exp_ms, 'v': 1}).encode())
    firma = b64u(hmac.new(secreto.encode(), payload.encode(), hashlib.sha256).digest())
    return payload + '.' + firma


JSON_CT = {'Content-Type': 'application/json'}
ahora_ms = int(time.time() * 1000)
s = Servidor({'SITE_PASSWORD_HASH': HASH, 'SESSION_SECRET': SECRETO})
try:
    print('\nHTTP contra la plantilla servida en 127.0.0.1:%d (funciones reales de api/):' % s.port)
    st, h, b = s.pedir('GET', '/')
    check(st == 200 and b'id="formAcceso"' in b, 'GET / → 200 con el formulario de acceso')
    check('report-uri /api/csp-report' in h.get('content-security-policy', '') and 'max-age=' in h.get('strict-transport-security', ''),
          'la página sale con CSP (report-uri) y HSTS')
    st, h, _ = s.pedir('GET', '/data/resumen.json')
    check(st == 401, 'GET /data/resumen.json sin cookie → 401 (%d)' % st)
    st, _, _ = s.pedir('GET', '/api/data?file=resumen.json')
    check(st == 401, 'GET /api/data sin cookie → 401 (%d)' % st)

    ip = {'X-Forwarded-For': '203.0.113.10', **JSON_CT}
    st, h, _ = s.pedir('POST', '/api/login', {'password': 'no-es-esta'}, ip)
    check(st == 401 and not h['set-cookie-todas'], 'login con contraseña mala → 401 y sin cookie (%d)' % st)
    st, h, _ = s.pedir('POST', '/api/login', '{esto no es json', ip)
    check(st == 401, 'login con cuerpo ilegible → 401 (%d)' % st)
    st, _, _ = s.pedir('GET', '/api/login')
    check(st == 405, 'GET /api/login → 405 (%d)' % st)

    st, h, _ = s.pedir('POST', '/api/login', {'password': CLAVE}, {'X-Forwarded-For': '203.0.113.20', **JSON_CT})
    sc = (h['set-cookie-todas'] or [''])[0]
    atributos = [a.strip() for a in sc.split(';')]
    check(st == 200 and sc.startswith('sp_session='), 'login con la contraseña buena → 200 y cookie sp_session (%d)' % st)
    check({'HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/'} <= set(atributos),
          'la cookie es HttpOnly; Secure; SameSite=Strict; Path=/')
    check('Max-Age=43200' in atributos, 'sin «recordarme» la sesión dura 12 h (Max-Age=43200)')
    cookie = sc.split(';')[0]
    st, h, _ = s.pedir('POST', '/api/login', {'password': CLAVE, 'remember': True}, {'X-Forwarded-For': '203.0.113.21', **JSON_CT})
    check('Max-Age=2592000' in (h['set-cookie-todas'] or [''])[0], 'con «recordarme» dura 30 días (Max-Age=2592000)')

    st, h, b = s.pedir('GET', '/data/resumen.json', cabeceras={'Cookie': cookie})
    check(st == 200 and json.loads(b).get('titulo'), 'GET /data/resumen.json con cookie válida → 200 y JSON (%d)' % st)
    check(h.get('cache-control') == 'no-store', 'los datos privados salen con Cache-Control: no-store')

    valor = cookie.split('=', 1)[1] if '=' in cookie else ''
    payload, firma = (valor.split('.') + ['', ''])[:2]
    firma = firma or 'sin-firma'
    falso = b64u(json.dumps({'exp': ahora_ms + 10 ** 12, 'v': 1}).encode()) + '.' + firma
    variantes = {
        'payload cambiado (exp alargado) con la firma vieja': falso,
        'firma alterada': payload + '.' + ('A' if firma[0] != 'A' else 'B') + firma[1:],
        'token caducado (firmado bien, exp en el pasado)': token(SECRETO, ahora_ms - 1000),
        'token firmado con otro secreto': token(secrets.token_urlsafe(32), ahora_ms + 3600_000),
        'basura': 'hola.mundo',
    }
    for nombre, t in variantes.items():
        st, _, _ = s.pedir('GET', '/data/resumen.json', cabeceras={'Cookie': 'sp_session=' + t})
        check(st == 401, 'cookie con %s → 401 (%d)' % (nombre, st))

    for f, esperado in (('../api/_sesion.js', 400), ('..%2Fapi%2F_sesion.js', 400), ('no-existe.json', 404)):
        st, _, _ = s.pedir('GET', '/api/data?file=' + f, cabeceras={'Cookie': cookie})
        check(st == esperado, 'con sesión, file=%s → %d (%d)' % (f, esperado, st))
    for ruta in ('/.env.example', '/api/_sesion', '/api/_sesion.js'):
        st, _, _ = s.pedir('GET', ruta)
        check(st == 404, '%s no se sirve → 404 (%d)' % (ruta, st))

    bloque = {'X-Forwarded-For': '203.0.113.30', **JSON_CT}
    codigos = [s.pedir('POST', '/api/login', {'password': 'mala-%d' % i}, bloque)[0] for i in range(5)]
    check(codigos == [401] * 5, '5 intentos fallidos desde una IP → 401 ×5 %s' % codigos)
    st, h, b = s.pedir('POST', '/api/login', {'password': 'mala-6'}, bloque)
    check(st == 429 and int(h.get('retry-after', '0')) > 0, '6.º intento → 429 con Retry-After=%s s (%d)' % (h.get('retry-after'), st))
    st, h, _ = s.pedir('POST', '/api/login', {'password': CLAVE}, bloque)
    check(st == 429 and not h['set-cookie-todas'], 'bloqueada, ni la contraseña buena entra → 429 (%d)' % st)
    st, _, _ = s.pedir('POST', '/api/login', {'password': CLAVE}, {'X-Forwarded-For': '203.0.113.31', **JSON_CT})
    check(st == 200, 'otra IP no queda bloqueada → 200 (%d)' % st)

    st, h, _ = s.pedir('POST', '/api/logout', cabeceras={'Cookie': cookie})
    check(st == 200 and 'Max-Age=0' in (h['set-cookie-todas'] or [''])[0], 'POST /api/logout borra la cookie (Max-Age=0)')

    legado = {'csp-report': {'document-uri': 'https://ejemplo.test/?q=1', 'violated-directive': 'script-src-elem',
                             'blocked-uri': 'https://cdn.ejemplo.test/x.js', 'line-number': 3}}
    st, _, _ = s.pedir('POST', '/api/csp-report', legado, {'Content-Type': 'application/csp-report'})
    check(st == 204, 'csp-report acepta un informe report-uri (application/csp-report) → 204 (%d)' % st)
    nuevo = [{'type': 'csp-violation', 'url': 'https://ejemplo.test/', 'body': {
        'documentURL': 'https://ejemplo.test/', 'effectiveDirective': 'img-src', 'blockedURL': 'https://img.ejemplo.test/p.gif'}}]
    st, _, _ = s.pedir('POST', '/api/csp-report', nuevo, {'Content-Type': 'application/reports+json'})
    check(st == 204, 'csp-report acepta un informe report-to (application/reports+json) → 204 (%d)' % st)
    for nombre, cuerpo, esperado in (('texto que no es JSON', 'no soy un informe', 400),
                                     ('JSON que no es un informe CSP', {'a': 1}, 400),
                                     ('lista sin csp-violation', [{'type': 'deprecation', 'body': {}}], 400),
                                     ('cuerpo de 20 KB', {'csp-report': {'violated-directive': 'x' * 20000}}, 413)):
        st, _, _ = s.pedir('POST', '/api/csp-report', cuerpo, JSON_CT)
        check(st == esperado, 'csp-report rechaza %s → %d (%d)' % (nombre, esperado, st))
    st, _, _ = s.pedir('GET', '/api/csp-report')
    check(st == 405, 'GET /api/csp-report → 405 (%d)' % st)
    time.sleep(0.3)
    registro = ''.join(s.err)
    check(registro.count('"evento":"csp_violacion"') == 2 and '?q=1' not in registro,
          'el buzón dejó 2 líneas csp_violacion en el registro, sin la query de la URL')
    check(CLAVE not in registro and SECRETO not in registro, 'el registro no contiene la contraseña ni el secreto')
finally:
    s.cerrar()

# servidor sin variables: debe negarse
s2 = Servidor({})
try:
    print('\nSin variables de entorno:')
    st, _, _ = s2.pedir('POST', '/api/login', {'password': CLAVE}, JSON_CT)
    check(st == 500, 'login sin SITE_PASSWORD_HASH ni SESSION_SECRET → 500 (%d)' % st)
    st, _, _ = s2.pedir('GET', '/data/resumen.json', cabeceras={'Cookie': 'sp_session=' + token('x' * 40, ahora_ms + 3600_000)})
    check(st == 401, 'sin SESSION_SECRET ningún token vale → 401 (%d)' % st)
finally:
    s2.cerrar()

# rotación: secreto nuevo + el anterior solo para verificar
s3 = Servidor({'SITE_PASSWORD_HASH': HASH, 'SESSION_SECRET': SECRETO_NUEVO, 'SESSION_SECRET_PREVIOUS': SECRETO})
try:
    print('\nRotación del secreto:')
    st, _, _ = s3.pedir('GET', '/data/resumen.json', cabeceras={'Cookie': 'sp_session=' + token(SECRETO, ahora_ms + 3600_000)})
    check(st == 200, 'con SESSION_SECRET_PREVIOUS, una sesión firmada con el secreto anterior sigue valiendo (%d)' % st)
    st, h, _ = s3.pedir('POST', '/api/login', {'password': CLAVE}, JSON_CT)
    nueva = (h['set-cookie-todas'] or [''])[0].split(';')[0].split('=', 1)[-1]
    p_, f_ = (nueva.split('.') + [''])[:2]
    esperado = b64u(hmac.new(SECRETO_NUEVO.encode(), p_.encode(), hashlib.sha256).digest())
    check(st == 200 and hmac.compare_digest(f_, esperado), 'las sesiones nuevas se firman con el secreto nuevo')
finally:
    s3.cerrar()

total = ok + len(fallos)
print('\n%d de %d comprobaciones (%d de configuración + %d HTTP) · %s' % (
    ok, total, n_estaticas, total - n_estaticas, 'OK' if not fallos else 'FALLA'))
sys.exit(0 if not fallos else 1)
