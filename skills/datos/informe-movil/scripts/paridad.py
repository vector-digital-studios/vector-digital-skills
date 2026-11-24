#!/usr/bin/env python3
"""paridad.py · ¿está todo el contenido original en el HTML? Compara palabras y cifras de la fuente Markdown
con el texto del HTML final (incluye lo plegado y las respuestas de las decisiones). Sirve de sello de «contenido íntegro»."""
import re, json, html, unicodedata, collections, pathlib, hashlib, base64, subprocess, tempfile, shutil
from html.parser import HTMLParser

SKIP_KW = {'tab', 'icono', 'tono', 'ft', 'ordenable', 'antes', 'despues', 'url', 'max', 'vista', 'rib', 'mejor', 'src', 'clip', 'poster', 'md5', 'local', 'img', 'aprox', 'ab', 'verificado', 'ar', 'loop', 'muted', 'alt', 'etiqueta', 'dur'}
COLS_SKIP = {'kpis': {3}, 'ranking': {3}, 'metricas': {5, 7}, 'vs': {3}, 'revisar': {3}, 'audio': {1, 3}, 'video': {1, 3}}
TAG = re.compile(r'</?[A-Za-z][^>]*>')

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower()) if not unicodedata.combining(c))

def tokens(s): return [t for t in re.findall(r'\w+', norm(s)) if len(t) > 1 or t.isdigit()]

def limpio(s):
    s = re.sub(r'<(script|style)\b.*?</\1>', ' ', str(s), flags=re.S | re.I)
    s = re.sub(r'data:image/[^"\')\s]+', ' ', s)
    return html.unescape(TAG.sub(' ', s)) if '<' in s else html.unescape(s)

def textos_doc(doc):
    out = [doc['meta'].get('titulo', ''), doc['meta'].get('subtitulo', '')]
    def blk(B):
        t = B['t']
        for k in ('md', 'h'):
            if B.get(k): out.append(limpio(B[k]))
        for k in ('b', 'det', 'items'): out.extend(B.get(k, []))
        for r in B.get('rows', []):
            for i, c in enumerate(r):
                if i in COLS_SKIP.get(t, ()): continue
                if t == 'pilas' and i > 0: c = ':'.join(c.split(':')[:2]).replace(':', ' ')
                out.append(re.sub(r'^\{(ok|warn|bad|info)\}', '', c))
        for o in B.get('ops', []): out.extend([o[0], o[1]])
        out.extend(B.get('pos', []))
        for k, v in B.get('kw', {}).items():
            if k not in SKIP_KW: out.append(v)
        out.extend(str(v) for v in B.get('x', []))
        for q in B.get('cuadros', []): out.extend(re.sub(r'\|\s*(ok|warn|bad|info|n)\s*$', '', v) if k == 'medida' else v for k, v in q.items() if k not in ('img', 'aprox'))
        for h in B.get('hijos', []): blk(h)
    for s in doc['secciones']:
        out.extend([s['titulo'], s['lead']])
        for B in s['bloques']: blk(B)
    return out

class _T(HTMLParser):
    def __init__(s): super().__init__(convert_charrefs=True); s.o, s.skip = [], 0
    def handle_starttag(s, tag, attrs):
        if tag in ('script', 'style'): s.skip += 1
        for k, v in attrs:
            if k in ('data-r', 'alt', 'aria-label') and v: s.o.append(v)
    def handle_endtag(s, tag):
        if tag in ('script', 'style') and s.skip: s.skip -= 1
    def handle_data(s, d):
        if not s.skip: s.o.append(d)

def texto_html(h):
    p = _T(); p.feed(h); return ' '.join(p.o)

def cobertura(origen, h):
    """Las frases idénticas de 3 o más palabras que el origen repite (p. ej. la misma decisión en el resumen y en su sección)
    se muestran una sola vez a propósito: se cuentan una vez y se declara cuántas se colapsaron."""
    vistos, dep, dup = set(), [], 0
    for s in origen:
        tk = tokens(s); k = ' '.join(tk)
        if len(tk) >= 3 and k in vistos: dup += 1; continue
        vistos.add(k); dep.append(s)
    seq = tokens(texto_html(h))
    co, ch = collections.Counter(tokens(' '.join(dep))), collections.Counter(seq)
    tot = sum(co.values()); ok = sum(min(n, ch[t]) for t, n in co.items())
    faltan = sorted(((n - ch[t], t) for t, n in co.items() if ch[t] < n), reverse=True)[:15]
    # comprobación inversa: texto en pantalla que no viene del origen (la interfaz aporta rachas cortas; un volcado de bytes, miles de palabras)
    vocab = set(co) | set(tokens(' '.join(origen))); run = best = 0
    for t in seq:
        run = 0 if t in vocab else run + 1; best = max(best, run)
    ajenas = sum(1 for t in seq if t not in vocab)
    return {'pct': round(100 * ok / tot, 2) if tot else 100.0, 'total': tot, 'faltan': [(t, n) for n, t in faltan], 'duplicados': dup,
            'racha_ajena': best, 'ajeno_pct': round(100 * ajenas / len(seq), 1) if seq else 0.0}

# ───────────────────────── medios: ¿están todos los reproductores del origen, con su mismo archivo? ─────────────────────────
RX_PLAYER = re.compile(r'<(audio|video)\b', re.I)
RX_DATA = re.compile(r'<(audio|video)\b[^>]*?\ssrc="data:([\w/+.-]+);base64,([A-Za-z0-9+/=]+)"', re.I)
HORA = re.compile(r'^\d{1,2}(:\d{2}){1,2}$')

def _cadenas(x):
    if isinstance(x, dict):
        for v in x.values(): yield from _cadenas(v)
    elif isinstance(x, list):
        for v in x: yield from _cadenas(v)
    elif isinstance(x, str): yield x

def _md5(b64): return hashlib.md5(base64.b64decode(re.sub(r'\s+', '', b64))).hexdigest()

def medios_origen(doc, medios):
    """Reproductores que declara la fuente: cuántos de cada tipo y la huella de cada archivo que se puede leer."""
    exp, hue = {'audio': 0, 'video': 0}, collections.Counter()
    def blk(B):
        if B['t'] in ('audio', 'video'):
            n = len([r for r in B.get('rows', []) if r and not HORA.match(r[0].strip())]) or (1 if any(B.get('kw', {}).get(k) for k in ('src', 'clip', 'url')) else 0)
            exp[B['t']] += n
        for h_ in B.get('hijos', []): blk(h_)
    for sec in doc['secciones']:
        for B in sec['bloques']: blk(B)
    for s_ in _cadenas(doc):
        for m in RX_PLAYER.finditer(s_): exp[m.group(1).lower()] += 1
    for e in medios:
        if e['tipo'] in ('audio', 'video') and e['modo'] == 'incrustado':
            p = pathlib.Path(e['origen']); md = hashlib.md5(p.read_bytes()).hexdigest() if p.is_absolute() and p.is_file() else e['md5']
            hue[(e['tipo'], md)] += 1
    return exp, hue

def medios_paridad(doc, medios, h):
    exp, hue = medios_origen(doc, medios)
    n = {'audio': 0, 'video': 0}
    for m in RX_PLAYER.finditer(h): n[m.group(1).lower()] += 1
    pres = collections.Counter((m.group(1).lower(), _md5(m.group(3))) for m in RX_DATA.finditer(h))
    n['video'] += len(re.findall(r'<a class="mdl', h))                 # un vídeo con enlace es una tarjeta, no un <video>
    faltan = [(t, md[:8]) for (t, md), c in hue.items() if pres[(t, md)] < c]
    no_inc = [(e['tipo'], (e.get('origen') or '')[:70], e.get('motivo', '')) for e in medios if e['tipo'] in ('audio', 'video') and e['modo'] in ('pesado', 'falta')]
    return {'esperados': exp, 'presentes': n, 'huellas_faltan': faltan, 'no_incluidos': no_inc, 'imagenes_faltan': sum(1 for e in medios if e['tipo'] == 'imagen' and e['modo'] == 'falta')}

def validar_reproductores(h):
    """ffprobe sobre cada archivo incrustado: ¿tiene duración medible? (un base64 corrupto o un códec raro se ve aquí)"""
    ff = shutil.which('ffprobe'); vistos, mal, n = set(), [], 0
    if not ff: return {'n': 0, 'mal': [], 'sin_ffprobe': True}
    for m in RX_DATA.finditer(h):
        t, mime, b64 = m.group(1).lower(), m.group(2), m.group(3); k = hashlib.md5(b64[:200].encode() + str(len(b64)).encode()).hexdigest()
        if k in vistos: continue
        vistos.add(k); n += 1
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tf: tf.write(base64.b64decode(b64)); ruta = tf.name
        try:
            r = subprocess.run([ff, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta], capture_output=True, text=True, timeout=60)
            try: ok = float(r.stdout.strip().split()[0]) > 0
            except Exception: ok = False
        except Exception: ok = False
        finally:
            try: pathlib.Path(ruta).unlink()
            except OSError: pass
        if not ok: mal.append('%s %s %s' % (t, mime, _md5(b64)[:8]))
    return {'n': n, 'mal': mal}

def verificar(h, doc, medios):
    """h = texto del HTML final; doc = documento analizado (informe.parse); medios = registro de medios de informe.generar."""
    r = cobertura(textos_doc(doc), h); r['origen'] = 'documento'
    r['medios'] = medios_paridad(doc, medios, h); r['reproductores'] = validar_reproductores(h)
    enl = re.findall(r'<a [^>]*href="([^"]+)"', h)
    r['enlaces'] = len(enl); r['enlaces_mal'] = [e for e in enl if not re.match(r'^(https?://\S+|mailto:\S+|#\S*)$', e)]
    r['externos'] = len(re.findall(r'(?:src|href)=["\']https?://[^"\']+\.(?:css|js|woff2?|png|jpe?g|svg)\b', h, re.I))
    return r

if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import informe
    if len(sys.argv) != 3: print('Uso: python paridad.py fuente.md informe.html'); sys.exit(2)
    doc = informe.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf8'))
    print(json.dumps(verificar(pathlib.Path(sys.argv[2]).read_text(encoding='utf8'), doc, []), ensure_ascii=False, indent=1))
