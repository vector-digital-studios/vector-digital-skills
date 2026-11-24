#!/usr/bin/env python3
"""autoprueba.py · prueba real de informe-movil, sin red y sin llaves. Sale con 0 si todo cumple.

1. Construye los tres informes de ejemplo (templates/) con los tres temas y las tres vistas.
2. Comprueba que cada HTML existe, es UN solo archivo autocontenido (CSS, JS, fuente e iconos dentro; ningún recurso
   externo) y que trae lo que la fuente declara (secciones, decisiones, cifras, sello pendiente).
3. Mide, sin navegador, que ≥ 98,5 % de las palabras y cifras de la fuente están en el HTML (paridad).
4. Comprueba los errores esperados (tema desconocido, Markdown sin secciones).
5. Si hay Node + puppeteer-core + Chrome: sella el ejemplo de negocio (Chrome a 390 px, claro y oscuro, toque a toque)
   y exige «TODO EN ORDEN». Si falta algo, lo avisa y salta ese paso (sale 0 igualmente).
   Forzar a saltarlo: INFORME_SIN_CHROME=1.
"""
import sys, re, pathlib, tempfile, shutil, subprocess, io, contextlib, json, os

AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
import informe, paridad, sellar  # noqa: E402

fallos, ok = [], 0
def check(cond, que):
    global ok
    if cond: ok += 1
    else: fallos.append(que); print('FALLA', que)

def autocontenido(h):
    externos = re.findall(r'''(?:src|href)\s*=\s*["']((?:https?:)?//[^"']+)''', h, re.I)
    externos = [u for u in externos if not re.search(r'<a\b[^>]*href\s*=\s*["\']' + re.escape(u), h)]   # los enlaces <a> son navegación, no recursos
    return (not externos and '<link ' not in h and '@import' not in h and 'url(http' not in h
            and "url(data:font/woff2;base64," in h and '<symbol id="i-' in h and h.count('<style>') >= 1 and '<script>' in h), externos

tmp = pathlib.Path(tempfile.mkdtemp(prefix='informe_autoprueba_'))
try:
    ejemplos = sorted((RAIZ / 'templates').glob('ejemplo-*.md'))
    check(len(ejemplos) >= 3, 'hay al menos 3 informes de ejemplo en templates/')
    vista_esperada = {'ejemplo-negocio': 'A', 'ejemplo-tecnico': 'B', 'ejemplo-investigacion': 'C'}
    for md in ejemplos:
        for tema in ('neutro', 'carbon', 'menta'):
            out = tmp / ('%s_%s.html' % (md.stem, tema))
            with contextlib.redirect_stdout(io.StringIO()):
                g = informe.generar(md, out, tema=tema)
            h = out.read_text(encoding='utf8') if out.exists() else ''
            check(out.is_file() and len(h) > 20000, '%s/%s: el HTML existe y no está vacío' % (md.stem, tema))
            ac, ext = autocontenido(h)
            check(ac, '%s/%s: autocontenido, sin recursos externos %s' % (md.stem, tema, ext[:3]))
            check(h.startswith('<!doctype html>') and 'name="viewport"' in h, '%s/%s: documento HTML con viewport móvil' % (md.stem, tema))
            check(g['vista'] == vista_esperada.get(md.stem, g['vista']), '%s: vista elegida por «tipo:» (%s)' % (md.stem, g['vista']))
            n_sec = len(g['doc']['secciones']); n_dec = sum(1 for s in g['doc']['secciones'] for b in s['bloques'] if b['t'] == 'decision')
            check(n_sec >= 4, '%s: %d secciones analizadas' % (md.stem, n_sec))
            check(h.count('class="card dc"') == n_dec and n_dec >= 1, '%s/%s: %d decisiones con sus opciones' % (md.stem, tema, n_dec))
            check('Sin medir todavía' in h, '%s/%s: sin sello todavía se dice en el propio informe' % (md.stem, tema))
            check(re.search(r'<meta name="theme-color" content="#[0-9A-Fa-f]{6}">', h) is not None, '%s/%s: color de tema aplicado' % (md.stem, tema))
            par = paridad.verificar(h, g['doc'], g['medios'])
            check(par['pct'] >= 98.5, '%s/%s: contenido íntegro %.1f %% (faltan %s)' % (md.stem, tema, par['pct'], par['faltan'][:5]))
            check(par['externos'] == 0 and not par['enlaces_mal'], '%s/%s: enlaces válidos y 0 recursos externos' % (md.stem, tema))
    # las tres vistas y el modo comparar con el mismo documento
    md = RAIZ / 'templates' / 'ejemplo-negocio.md'
    for v in 'ABC':
        out = tmp / ('vista_%s.html' % v)
        with contextlib.redirect_stdout(io.StringIO()): informe.generar(md, out, vista=v)
        check('id="vista-%s"' % v in out.read_text(encoding='utf8'), 'la vista %s se construye' % v)
    out = tmp / 'comparar.html'
    with contextlib.redirect_stdout(io.StringIO()): informe.generar(md, out, modo='comparar')
    hc = out.read_text(encoding='utf8')
    check(all('id="vista-%s"' % v in hc for v in 'ABC') and 'role="tablist"' in hc, 'el modo comparar trae las tres vistas con selector')
    # CLI de verdad (subproceso), salida por defecto junto a la entrada
    cp = tmp / 'cli.md'; shutil.copyfile(RAIZ / 'templates' / 'plantilla.md', cp)
    r = subprocess.run([sys.executable, str(AQUI / 'informe.py'), str(cp), '--tema', 'carbon'], capture_output=True, text=True, encoding='utf8', errors='replace')
    check(r.returncode == 0 and (tmp / 'cli.html').is_file() and r.stdout.startswith('OK'), 'la CLI genera cli.html junto a la entrada (salida: %s)' % (r.stdout or r.stderr).strip()[:120])
    # tema propio por ruta
    propio = tmp / 'mi-tema.css'; propio.write_text((AQUI / 'temas' / 'neutro.css').read_text(encoding='utf8').replace('#5B9DFF', '#7A8CFF'), encoding='utf8')
    out = tmp / 'propio.html'
    with contextlib.redirect_stdout(io.StringIO()): informe.generar(md, out, tema=str(propio))
    check('#7A8CFF' in out.read_text(encoding='utf8'), 'un tema propio (.css por ruta) se aplica')
    # errores esperados
    try:
        informe.ruta_tema('no-existe'); check(False, 'un tema desconocido debe dar error')
    except SystemExit as e: check('Tema desconocido' in str(e), 'un tema desconocido da un error claro')
    vacio = tmp / 'vacio.md'; vacio.write_text('---\ntitulo: x\n---\nsin secciones\n', encoding='utf8')
    try:
        informe.generar(vacio, tmp / 'vacio.html'); check(False, 'un .md sin secciones debe dar error')
    except SystemExit as e: check('secciones' in str(e), 'un .md sin secciones da un error claro')
    # paridad: el medidor detecta contenido perdido (se provoca el fallo a propósito)
    hbase = (tmp / 'ejemplo-negocio_neutro.html').read_text(encoding='utf8')
    doc = informe.parse(md.read_text(encoding='utf8'))
    roto = re.sub(r'<div class="card dc".*?</div></div>', '', hbase, flags=re.S)
    check(paridad.verificar(roto, doc, [])['pct'] < paridad.verificar(hbase, doc, [])['pct'], 'la paridad baja si se borra contenido del HTML')

    # ── sello con Chrome (opcional) ──
    if os.environ.get('INFORME_SIN_CHROME'):
        print('AVISO: INFORME_SIN_CHROME=1 · se salta el sello con Chrome.')
        sello_txt = 'sello omitido (INFORME_SIN_CHROME)'
    else:
        disp, motivo = sellar.disponible()
        if not disp:
            print('AVISO: no se puede sellar en esta máquina (%s). Se salta esa parte; el resto de la prueba vale.' % motivo)
            sello_txt = 'sello omitido: sin Chrome/Node'
        else:
            dest = tmp / 'sellado.html'; buf = io.StringIO()
            with contextlib.redirect_stdout(buf): rc = sellar.sellar(md, dest)
            salida = buf.getvalue(); sj = informe.ruta_sello(dest)
            check(rc == 0 and 'TODO EN ORDEN' in salida, 'el ejemplo de negocio pasa el sello en Chrome (rc=%s)\n%s' % (rc, '\n'.join(l for l in salida.splitlines() if l.startswith('FALLA'))))
            datos = json.loads(sj.read_text(encoding='utf8')) if sj.exists() else {}
            check(datos.get('estable') is True and len(datos.get('lineas', [])) >= 10, 'el sello queda en %s, estable y con ≥10 comprobaciones' % sj.name)
            check('Sello de verificación' in dest.read_text(encoding='utf8'), 'el sello va incrustado en el propio HTML')
            sello_txt = 'sello en Chrome: %d de %d comprobaciones' % (sum(1 for l in datos.get('lineas', []) if l[0]), len(datos.get('lineas', [])))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

total = ok + len(fallos)
if fallos:
    print('%d de %d comprobaciones · FALLA' % (ok, total)); sys.exit(1)
print('%d de %d comprobaciones · %s · OK' % (ok, total, sello_txt))
