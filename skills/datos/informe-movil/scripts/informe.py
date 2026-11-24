#!/usr/bin/env python3
"""informe.py · informe-movil: Markdown de bloques -> informe HTML de un solo archivo, móvil primero (390 px).
  python informe.py entrada.md -o salida.html [--tema neutro|carbon|menta|mi-tema.css] [--vista A|B|C] [--modo una|comparar]
  python informe.py entrada.md -o salida.html --sellar     mide el HTML en Chrome sin pantalla y le incrusta el sello
  python informe.py entrada.md -o salida.html --previo     la misma medición, sin estampar: imprime lo que falla
El autor (persona o agente) solo escribe contenido (references/formato.md). El diseño vive en estilos.css, app.js y temas/.
Junto al HTML, --sellar deja <salida>.sello.json con el resultado de la medición.
"""
import re, sys, json, html, base64, shlex, pathlib, datetime, math, os, io, hashlib, unicodedata, urllib.parse, shutil, subprocess
from html.parser import HTMLParser

AQUI = pathlib.Path(__file__).resolve().parent
VERSION = '1.0.0'
E = lambda s: html.escape(str(s), quote=True)
TN = {'ok': 't-ok', 'warn': 't-warn', 'bad': 't-bad', 'info': 't-info'}
tn = lambda t: TN.get((t or '').strip().lower(), 't-n')
PAL = {'ac': 'var(--c1)', 'ok': 'var(--c1)', 'in': 'var(--c2)', 'wa': 'var(--c3)', 'ba': 'var(--c4)', 'vi': 'var(--c5)', 'mu': 'var(--c6)'}
EVT = {'Medido': 'ok', 'Leído': 'info', 'Inferido': 'warn', 'Estimado': 'warn', 'Historial': 'n', 'Criterio': 'warn'}
TABS = [('resumen', 'Resumen', 'layout-dashboard'), ('datos', 'Datos', 'chart-bar'), ('analisis', 'Análisis', 'bulb'), ('decidir', 'Decisión', 'checklist'), ('fuentes', 'Fuentes', 'link')]

# ───────────────────────── iconos (Tabler, sprite) ─────────────────────────
def sprite():
    out = []
    for f in sorted((AQUI / 'assets' / 'iconos').glob('*.svg')):
        s = f.read_text(encoding='utf8')
        inner = re.sub(r'^.*?<svg[^>]*>', '', s, flags=re.S).replace('</svg>', '')
        inner = re.sub(r'<path stroke="none"[^>]*/>', '', inner).strip()
        out.append('<symbol id="i-%s" viewBox="0 0 24 24">%s</symbol>' % (f.stem, inner))
    return '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">%s</svg>' % ''.join(out)

ICONOS = {f.stem for f in (AQUI / 'assets' / 'iconos').glob('*.svg')}
ic = lambda n, c='': '<svg class="i %s" aria-hidden="true"><use href="#i-%s"/></svg>' % (c, n if n in ICONOS else 'sparkles')   # un icono desconocido cae a uno neutro: nunca un recuadro vacío

# ───────────────────────── texto ─────────────────────────
def nb(s):
    return re.sub(r'(\d) (%|px|KB|MB|mil|min|k)(?![\wáéíóú])', '\\1\u00a0\\2', str(s))

def inline(s):
    s = E(nb(s))
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<![*\w])\*([^*\n]+)\*(?![*\w])', r'<i>\1</i>', s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s

def num(s):
    m = re.search(r'-?\d[\d.,]*', str(s))
    if not m: return None
    t = m.group(0).rstrip('.,')
    t = t.replace('.', '') if re.fullmatch(r'-?\d{1,3}(\.\d{3})+', t) else t.replace(',', '.')
    try: return float(t)
    except ValueError: return None

def mil(n):
    return ('%.1f' % (n / 1000)).replace('.', ',') + ' mil' if n >= 1000 else '%d' % n

def md_basic(t):
    out = []
    for p in re.split(r'\n\s*\n', t.strip()):
        L = [l for l in p.split('\n') if l.strip()]
        if not L: continue
        if all(re.match(r'^\s*[-*]\s+', l) for l in L):
            out.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(re.sub(r'^\s*[-*]\s+', '', l)) for l in L))
        elif all(re.match(r'^\s*\d+[.)]\s+', l) for l in L):
            out.append('<ol>%s</ol>' % ''.join('<li>%s</li>' % inline(re.sub(r'^\s*\d+[.)]\s+', '', l)) for l in L))
        else:
            out.append('<p>%s</p>' % inline(' '.join(l.strip() for l in L)))
    return '<div class="tx">%s</div>' % ''.join(out)

def nota_chip(n):
    m = re.match(r'^(Medido|Leído|Inferido|Estimado|Historial|Criterio)\s*:\s*(.*)$', n)
    if m: return '<span class="chip %s">%s</span>%s' % (tn(EVT[m.group(1)]), m.group(1), inline(m.group(2)))
    return inline(n)

def celda(c):
    m = re.match(r'^\{(ok|warn|bad|info)\}(.*)$', c)
    return '<span class="sc %s">%s</span>' % (tn(m.group(1)), inline(m.group(2))) if m else inline(c)

# ───────────────────────── parser ─────────────────────────
def args(s):
    try: tk = shlex.split(s)
    except ValueError: tk = s.split()
    pos, kw = [], {}
    for t in tk:
        if re.match(r'^\w+=', t): k, v = t.split('=', 1); kw[k] = v
        else: pos.append(t)
    return pos, kw

def filas(inner):
    out = []
    for l in inner:
        if not l.strip() or l.lstrip().startswith('#'): continue
        out.append([c.replace('\\|', '|').strip() for c in re.split(r'(?<!\\)\|', l)])
    return out

def mk(t, a, inner):
    pos, kw = args(a)
    B = {'t': t, 'pos': pos, 'kw': kw}
    if t in ('kpis', 'ranking', 'vs', 'tabla', 'pilas', 'matriz', 'pasos', 'fuentes', 'glosario', 'metricas', 'revisar', 'archivos', 'rubrica', 'enlaces', 'audio', 'video'):
        B['rows'] = filas(inner)
    elif t == 'veredicto':
        L = [l.strip() for l in inner if l.strip()]
        B['h'] = L[0] if L else ''
        B['b'] = [re.sub(r'^[-*]\s*', '', l) for l in L[1:]]
    elif t == 'grafica':
        for l in inner:
            if l.startswith('x:'): B['x'] = [c.strip() for c in l[2:].split(',')]
            elif l.startswith('serie:'): B['y'] = [num(c) or 0 for c in l[6:].split(',')]
    elif t == 'decision':
        B['det'], B['ops'] = [], []
        for l in inner:
            if l.lstrip().startswith('- '):
                c = [x.replace('\\|', '|').strip() for x in re.split(r'(?<!\\)\|', l.lstrip()[2:])]
                B['ops'].append((c[0], c[1] if len(c) > 1 and c[1] else c[0], len(c) > 2 and c[2] == '*'))
            elif l.strip(): B['det'].append(l.strip())
        B['ops'].sort(key=lambda o: not o[2])
    elif t in ('nota', 'texto', 'codigo', 'copiable', 'html'):
        B['md'] = '\n'.join(inner).strip('\n')
    elif t == 'lista':
        B['items'] = [re.sub(r'^\s*[-*]\s+', '', l).strip() for l in inner if l.strip()]
    elif t == 'storyboard':
        B['cuadros'] = cuadros_de(inner)
    elif t == 'detalle':
        B['hijos'] = bloques_de(inner)
    return B

def bloques_de(lines):
    out, buf, i = [], [], 0
    def flush():
        nonlocal buf
        txt = '\n'.join(buf).strip()
        if txt: out.append({'t': 'texto', 'md': txt, 'pos': [], 'kw': {}})
        buf = []
    while i < len(lines):
        m = re.match(r'^:::\s*(\w+)\s*(.*)$', lines[i])
        if m:
            flush(); d, j, inner = 1, i + 1, []
            while j < len(lines):
                if re.match(r'^:::\s*\w+', lines[j]): d += 1
                elif lines[j].strip() == ':::':
                    d -= 1
                    if d == 0: break
                inner.append(lines[j]); j += 1
            out.append(mk(m.group(1), m.group(2), inner)); i = j + 1; continue
        buf.append(lines[i]); i += 1
    flush(); return out

def parse(md):
    L = md.replace('\r', '').split('\n'); meta, i = {}, 0
    if L and L[0].strip() == '---':
        j = 1
        while j < len(L) and L[j].strip() != '---':
            if ':' in L[j]: k, v = L[j].split(':', 1); meta[k.strip()] = v.strip()
            j += 1
        i = j + 1
    secs, cur, dep = [], None, 0
    for ln in L[i:]:
        if dep == 0:
            m = re.match(r'^#\s+(.*?)\s*(?:\{([^}]*)\})?\s*$', ln)
            if m and not ln.startswith('##'):
                _, kw = args(m.group(2) or '')
                cur = {'titulo': m.group(1), 'kw': kw, 'lines': []}; secs.append(cur); continue
        if re.match(r'^:::\s*\w+', ln): dep += 1
        elif ln.strip() == ':::' and dep > 0: dep -= 1
        if cur is not None: cur['lines'].append(ln)
    for k, s in enumerate(secs):
        s['id'] = 's%d' % k; s['lead'] = ''
        ls = s['lines']
        while ls and not ls[0].strip(): ls.pop(0)
        if ls and ls[0].startswith('>>'): s['lead'] = ls.pop(0)[2:].strip()
        s['bloques'] = bloques_de(ls); del s['lines']
        s['tab'] = s['kw'].get('tab', 'resumen' if k == 0 else 'analisis'); s['icono'] = s['kw'].get('icono', {t[0]: t[2] for t in TABS}[s['tab']])
    return {'meta': meta, 'secciones': secs}

# ───────────────────────── bloques ─────────────────────────
def titulo(B):
    return '<p class="bt">%s</p>' % inline(B['pos'][0]) if B['pos'] else ''

def r_kpis(B, c):
    its = ''
    for r in B['rows']:
        v, l, d, t = (r + ['', '', '', ''])[:4]
        its += '<div class="k %s"><b class="kv">%s</b><span class="kl">%s</span><span class="kd">%s</span></div>' % (tn(t), E(v), inline(l), inline(d))
    return '<div class="%s"%s>%s</div>' % ('rib' if c.get('rib') else 'kp', ' data-scroll-x' if c.get('rib') else '', its)

def r_veredicto(B, c):
    t = tn(B['kw'].get('tono', 'warn')); conf = B['kw'].get('confianza', ''); cf = B['kw'].get('cifra', ''); rg = ring(cf)
    lab = inline(B['kw'].get('cifra_l', ''))
    if rg:
        tam = ' xl' if len(rg[1]) >= 5 else ' lg' if len(rg[1]) >= 4 else ''   # una cifra larga no debe pisar el anillo
        hero = '<div class="vm"><div class="rg%s" style="--p:%.1f" role="img" aria-label="%s"><b>%s<small>%s</small></b></div><span class="vnl">%s</span></div>' % (tam, rg[0], E(cf), E(rg[1]), E(rg[2]), lab)
    elif cf: hero = '<div class="vm"><b class="vn">%s</b><span class="vnl">%s</span></div>' % (E(nb(cf)), lab)
    else: hero = ''
    bl = '<ul class="vl">%s</ul>' % ''.join('<li>%s</li>' % inline(x) for x in B['b']) if B['b'] else ''
    return ('<div class="card ver %s"><div class="vt"><span class="chip">Veredicto</span>%s</div>%s<p class="vh">%s</p>%s</div>' %
            (t, '<span class="chip t-ok">Confianza %s</span>' % E(conf) if conf else '', hero, inline(B['h']), bl))

def r_ranking(B, c, rows=None):
    mx = float(B['kw'].get('max', 10)); un = B['kw'].get('unidad', ''); out = ''
    for r in (rows or B['rows']):
        lab, val, nota, tono = (r + ['', '', '', ''])[:4]; w = max(4, min(100, 100 * (num(val) or 0) / mx))
        out += ('<div class="rr %s"><div class="rh"><span class="rl">%s</span><b class="rv">%s%s</b></div><span class="bar"><i style="--w:%.0f%%"></i></span>%s</div>' %
                (tn(tono), inline(lab), E(val), E(un), w, '<p class="rn">%s</p>' % nota_chip(nota) if nota else ''))
    return '<div class="card">%s<div class="rk">%s</div></div>' % (titulo(B), out)

def r_vs(B, c):
    a, b = B['kw'].get('a', 'A'), B['kw'].get('b', 'B'); sa = sb = 0; rows = ''
    for r in B['rows']:
        cr, va, vb, g, por = (r + [''] * 5)[:5]; g = g.strip().upper(); wa, wb = g == 'A', g == 'B'; sa += wa; sb += wb
        na, nb_ = num(va), num(vb); top = max(na or 0, nb_ or 0)
        def lado(cls, nom, val, n, gana):
            if n is not None and nb_ is not None and na is not None and top > 0:
                return '<div class="vs1 %s%s"><em>%s</em><span class="bar"><i style="--w:%.0f%%"></i></span><b>%s</b></div>' % (cls, ' w' if gana else '', E(nom), (0 if n == 0 else max(4, 100 * n / top)), E(val))
            return '<div class="vs1 t2 %s%s"><em>%s</em><b>%s</b></div>' % (cls, ' w' if gana else '', E(nom), inline(val))
        rows += '<div class="vr"><p class="vc">%s</p>%s%s%s</div>' % (inline(cr), lado('a', a, va, na, wa), lado('b', b, vb, nb_, wb), '<p class="vp">%s</p>' % inline(por) if por else '')
    return ('<div class="card">%s<div class="vsh"><div class="p a%s"><b>%s</b></div><span class="x">VS</span><div class="p b%s"><b>%s</b></div></div>'
            '<p class="vsm"><b class="ca">%d</b> %s &nbsp;·&nbsp; <b class="cb">%d</b> %s &nbsp;·&nbsp; criterios ganados</p>%s</div>' % (titulo(B), ' w' if sa >= sb else '', E(a), ' w' if sb > sa else '', E(b), sa, E(a), sb, E(b), rows))

def r_tabla(B, c):
    rows = [r for r in B['rows'] if not re.match(r'^[\s|:\-]+$', '|'.join(r))]; head, body = rows[0], rows[1:]
    od = B['kw'].get('ordenable') == '1'
    th = ''.join('<th%s>%s</th>' % (' data-s' if od and i > 0 else '', inline(h)) for i, h in enumerate(head))
    tr = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % celda(x) for x in r) for r in body)
    return '%s<div class="tw" data-scroll-x><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s' % (
        titulo(B), th, tr, ('<p class="hint">Toque un encabezado con ↕ para ordenar.</p>' if od else '') + ('<p class="hint">Deslice de lado para ver todas las columnas.</p>' if len(head) > 3 else ''))

def r_pilas(B, c):
    cyc, col, tot = ['ac', 'in', 'wa', 'ba', 'vi', 'mu'], {}, []
    for r in B['rows']:
        for s in r[1:]:
            p = s.split(':')
            if p[0] not in col: col[p[0]] = p[2] if len(p) > 2 else cyc[len(col) % len(cyc)]
    for r in B['rows']: tot.append(sum(num(s.split(':')[1]) or 0 for s in r[1:]))
    mx, out = max(tot), ''
    for r, t in zip(B['rows'], tot):
        segs, det = '', []
        for s in r[1:]:
            p = s.split(':'); v = num(p[1]) or 0; w = 100 * v / mx
            segs += '<i style="--w:%.1f%%;--c:%s" title="%s: %s">%s</i>' % (w, PAL[col[p[0]]], E(p[0]), mil(v), mil(v).replace(' mil', '') if w >= 11 else '')
            det.append('%s %s' % (E(p[0]), mil(v)))
        out += '<div class="plr"><p class="pll"><span>%s</span><b>%s</b></p><div class="pls">%s</div><p class="pld">%s</p></div>' % (inline(r[0]), mil(t), segs, ' · '.join(det))
    lg = ''.join('<span style="--c:%s">%s</span>' % (PAL[v], E(k)) for k, v in col.items())
    return '<div class="card">%s<div class="pl">%s</div><div class="lg">%s</div></div>' % (titulo(B), out, lg)

def r_grafica(B, c):
    xs, ys = B.get('x', []), B.get('y', []); mx = max(ys) or 1; hi = ys.index(mx); cols = ''
    for i, (x, y) in enumerate(zip(xs, ys)):
        lab = '<b>%g</b>' % y if i in (hi, len(ys) - 1) else ''
        cols += '<div class="c%s" style="--h:%.0f%%" title="%s: %g"><i></i>%s</div>' % (' hi' if i == hi else '', max(2, 100 * y / mx), E(x.replace('/', ' ')), y, lab)
    sub = '<p class="bs">%s</p>' % inline(B['kw']['sub']) if 'sub' in B['kw'] else ''
    return '<div class="card">%s%s<div class="gb">%s</div><div class="gx">%s</div></div>' % (titulo(B), sub, cols, ''.join('<span>%s%s</span>' % (E(x.split('/')[0]), '<small>%s</small>' % E(x.split('/')[1]) if '/' in x else '') for x in xs))

def r_matriz(B, c):
    dots, leg = '', ''
    for r in B['rows']:
        n, lab, x, y = (r + ['', '', '5', '5'])[:4]; cx = min(94, max(6, 10 * (num(x) or 5))); cy = min(94, max(6, 10 * (10 - (num(y) or 5))))
        dots += '<span class="d" style="left:%.0f%%;top:%.0f%%">%s</span>' % (cx, cy, E(n))
        leg += '<li><span class="n">%s</span><span>%s</span><small>esfuerzo %s · impacto %s</small></li>' % (E(n), inline(lab), E(x), E(y))
    xa, ya = B['kw'].get('x', 'Esfuerzo'), B['kw'].get('y', 'Impacto')
    return ('<div class="card">%s<div class="mx"><div class="q"><span>Hacer ya</span></div>%s</div><p class="hint">A la derecha, más %s. Arriba, más %s.</p><ul class="ml">%s</ul></div>' %
            (titulo(B), dots, E(xa.lower()), E(ya.lower()), leg))

def r_decision(B, c):
    d = B['pos'][0] if B['pos'] else 'D'; q = B['pos'][1] if len(B['pos']) > 1 else ''; ops = ''
    for i, (t, r, rec) in enumerate(B['ops'], 1):
        ops += '<button class="op%s" data-d="%s" data-o="%d" data-r="%s"><span class="ck"></span><span class="ot">%s</span>%s</button>' % (' rec' if rec else '', E(d), i, E(r), inline(t), '<em>Recomendada</em>' if rec else '')
    det = ' '.join(B['det'])
    return '<div class="card dc" data-d="%s"><p class="dq"><span class="did">%s</span><span>%s</span></p>%s%s<div class="ops">%s</div><p class="rsp"></p></div>' % (
        E(d), E(d), inline(q), '<p class="dd">%s</p>' % inline(det) if det else '', '<p class="hint dh">Toque una opción para elegirla</p>' if ops else '', ops)

def r_pasos(B, c):
    li = ''.join('<li><span class="pp">%s</span><div><b>%s</b><p>%s</p>%s</div></li>' % (E(r[0]), inline(r[1]), inline(r[2] if len(r) > 2 else ''), '<span class="ef">%s</span>' % E(r[3]) if len(r) > 3 and r[3] else '') for r in B['rows'])
    return '%s<ol class="ps">%s</ol>' % (titulo(B), li)

def r_fuentes(B, c):
    li = ''
    for r in B['rows']:
        t, ti, ref, n = (r + ['', '', '', ''])[:4]
        li += '<li><span class="chip %s">%s</span><div><b>%s</b>%s%s</div></li>' % (tn(EVT.get(t, 'n')), E(t), inline(ti), '<code>%s</code>' % E(ref) if ref else '', '<small>%s</small>' % inline(n) if n else '')
    return '%s<ul class="fu">%s</ul>' % (titulo(B), li)

def r_nota(B, c):
    t = B['kw'].get('tono', 'info'); ico = {'ok': 'circle-check', 'warn': 'alert-triangle', 'bad': 'alert-triangle', 'info': 'info-circle'}.get(t, 'info-circle')
    return '<aside class="nt %s">%s<div>%s%s</div></aside>' % (tn(t), ic(ico), '<b class="nh">%s</b>' % inline(B['pos'][0]) if B['pos'] else '', md_basic(B['md']).replace('<div class="tx">', '').replace('</div>', ''))

def r_glosario(B, c):
    return '<dl class="gl">%s</dl>' % ''.join('<dt>%s</dt><dd>%s</dd>' % (inline(r[0]), inline(r[1] if len(r) > 1 else '')) for r in B['rows'])

def r_verificacion(B, c):
    q = c.get('qa')
    if not q: return '<aside class="nt t-warn">%s<div><b class="nh">Sin medir todavía</b><p>Este archivo aún no pasó por la revisión automática.</p></div></aside>' % ic('alert-triangle')
    items = ''.join('<p class="%s">%s<span>%s</span></p>' % ('' if ok else 'bad', ic('circle-check' if ok else 'circle-x'), inline(t)) for ok, t in q['lineas'])
    return '<div class="card"><p class="bt">Sello de verificación</p><p class="bs">Medido el %s con Chrome sin pantalla a 390 px, sobre este mismo archivo.</p><div class="vf">%s</div></div>' % (E(q['fecha']), items)

# ───────────────────────── imágenes y HTML saneado (bloques imagen y html) ─────────────────────────
_IMG = {}

def _recomprimir(data, maxw=1100):
    """Reduce a 1100 px de ancho (suficiente para 390 px a 2-3x) y recomprime; así el HTML pesa lo justo."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)); im.load()
        alfa = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
        if im.width > maxw: im = im.resize((maxw, max(1, round(im.height * maxw / im.width))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if alfa: im.convert('RGBA').save(buf, 'PNG', optimize=True); mime = 'image/png'
        else: im.convert('RGB').save(buf, 'JPEG', quality=82, optimize=True, progressive=True); mime = 'image/jpeg'
        b = buf.getvalue()
        if not alfa and len(b) > len(data) and data[:3] == b'\xff\xd8\xff' and im.width <= maxw: b, mime = data, 'image/jpeg'
        return 'data:%s;base64,%s' % (mime, base64.b64encode(b).decode())
    except Exception:
        mime = 'image/png' if data[:4] == b'\x89PNG' else 'image/jpeg'
        return 'data:%s;base64,%s' % (mime, base64.b64encode(data).decode())

def img_uri(src, base=None, maxw=1100):
    src = (src or '').strip()
    if not src: return None
    k = hashlib.md5((src if len(src) < 300 else src[:150] + src[-150:] + str(len(src))).encode('utf8', 'ignore')).hexdigest() + str(base) + str(maxw)
    if k in _IMG: return _IMG[k]
    data = None
    try:
        if src.startswith('data:image/'):
            head, _, body = src.partition(',')
            data = base64.b64decode(body) if ';base64' in head else urllib.parse.unquote_to_bytes(body)
        elif re.match(r'^https?://', src, re.I):
            _IMG[k] = src; return src
        else:
            p = hallar(src, base)
            if p: data = p.read_bytes()
    except Exception:
        data = None
    _IMG[k] = _recomprimir(data, maxw) if data else None
    if not _IMG[k]: _MED.append({'tipo': 'imagen', 'modo': 'falta', 'etiqueta': '', 'origen': 'incluida en el original' if src.startswith('data:') else src[:240], 'motivo': 'no se encontró o no se pudo leer'})
    return _IMG[k]

S_OK = {'button', 'p', 'br', 'b', 'strong', 'i', 'em', 'u', 'small', 'code', 'pre', 'ul', 'ol', 'li', 'a', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'span', 'div', 'details', 'summary',
        'img', 'figure', 'figcaption', 'hr', 'mark', 'sup', 'sub', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'svg', 'g', 'line', 'path', 'rect', 'circle', 'ellipse', 'polyline', 'polygon', 'text', 'title', 'desc'}
S_VOID = {'br', 'hr', 'img', 'line', 'path', 'rect', 'circle', 'ellipse', 'polyline', 'polygon'}
S_SVG = {'svg', 'g', 'line', 'path', 'rect', 'circle', 'ellipse', 'polyline', 'polygon', 'text', 'title', 'desc'}
S_SVGA = {'viewbox': 'viewBox', 'width': 'width', 'height': 'height', 'x': 'x', 'y': 'y', 'x1': 'x1', 'y1': 'y1', 'x2': 'x2', 'y2': 'y2', 'cx': 'cx', 'cy': 'cy', 'r': 'r', 'rx': 'rx', 'ry': 'ry', 'd': 'd',
          'points': 'points', 'fill': 'fill', 'stroke': 'stroke', 'stroke-width': 'stroke-width', 'stroke-linecap': 'stroke-linecap', 'stroke-linejoin': 'stroke-linejoin', 'stroke-dasharray': 'stroke-dasharray',
          'opacity': 'opacity', 'transform': 'transform', 'font-size': 'font-size', 'font-weight': 'font-weight', 'text-anchor': 'text-anchor', 'dominant-baseline': 'dominant-baseline', 'role': 'role',
          'aria-label': 'aria-label', 'preserveaspectratio': 'preserveAspectRatio', 'fill-opacity': 'fill-opacity', 'stroke-opacity': 'stroke-opacity', 'xmlns': 'xmlns'}
HMAP = {'h1': 'h4', 'h2': 'h4', 'h3': 'h4', 'h4': 'h4', 'h5': 'h5', 'h6': 'h5'}

def tono_color(v):
    """Un color escrito a mano en un informe viejo pasa a un tono del tema (así se lee igual en claro y en oscuro)."""
    v = v.strip().lower()
    fijo = {'var(--mu)': 'c-mu', 'var(--mu2)': 'c-mu', 'var(--ac)': 'c-ac', 'var(--ok)': 'c-ok', 'var(--wa)': 'c-wa', 'var(--ba)': 'c-ba'}
    if v in fijo: return fijo[v]
    m = re.match(r'^#([0-9a-f]{3}|[0-9a-f]{6})$', v)
    if not m: return None
    h = m.group(1); h = ''.join(c * 2 for c in h) if len(h) == 3 else h
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    mx, mn = max(r, g, b), min(r, g, b); d = mx - mn
    if d < .18 or mx < .4: return None
    hue = (60 * (((g - b) / d) % 6)) if mx == r else (60 * ((b - r) / d + 2)) if mx == g else (60 * ((r - g) / d + 4))
    if hue < 20 or hue >= 335: return 'c-ba'
    if hue < 75: return 'c-wa'
    if hue < 170: return 'c-ok'
    if hue < 260: return 'c-in'
    return None

def estilo_a_clases(style):
    cl, extra = [], ''
    for pr in style.split(';'):
        if ':' not in pr: continue
        k, v = [x.strip().lower() for x in pr.split(':', 1)]
        if k == 'display' and v == 'flex': cl.append('fx')
        elif k == 'text-align' and v in ('right', 'center'): cl.append('al-r' if v == 'right' else 'al-c')
        elif k == 'white-space' and v.startswith('pre'): cl.append('pw')
        elif k == 'font-weight' and v in ('600', '700', '800', 'bold'): cl.append('fw')
        elif k == 'color':
            t = tono_color(v)
            if t: cl.append(t)
        elif k == 'width' and re.match(r'^\d{1,3}(\.\d+)?%$', v) and float(v[:-1]) <= 100: extra = 'width:%s' % v
    return cl, extra

class _San(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True); self.o, self.st, self.base, self.mudo, self.med = [], [], base, 0, None

    def handle_starttag(self, tag, attrs):
        if tag in ('audio', 'video'):
            a = {k: (v if v is not None else '') for k, v in attrs}
            self.mudo = getattr(self, 'mudo', 0) + 1; self.med = {'tag': tag, 'a': a, 'at': len(self.o), 'listo': False}; self.o.append('')   # hueco: se llena con el reproductor (o con un aviso)
            if a.get('src'): self._llenar(a['src'])
            return
        if tag == 'source':
            s = dict(attrs).get('src')
            if s and getattr(self, 'med', None) and not self.med['listo']: self._llenar(s)
            return
        if tag in ('script', 'style', 'iframe'):
            self.mudo = getattr(self, 'mudo', 0) + 1; return
        if tag not in S_OK:
            self.o.append(E(self.get_starttag_text())); return
        t = HMAP.get(tag, tag); a = {k: (v if v is not None else '') for k, v in attrs}
        cls, sty, at = [], '', ''
        if 'style' in a: cls, sty = estilo_a_clases(a['style'])
        if a.get('align') in ('right', 'center'): cls.append('al-r' if a['align'] == 'right' else 'al-c')
        if t == 'a':
            h = a.get('href', '').strip()
            if re.match(r'^(https?://|mailto:|#)', h, re.I): at += ' href="%s"' % E(h) + ('' if h.startswith('#') else ' target="_blank" rel="noopener"')
        elif t == 'img':
            uri = img_uri(a.get('src', ''), self.base)
            if not uri:
                self.o.append('<span class="c-mu">[imagen no disponible%s]</span>' % (': ' + E(a['alt']) if a.get('alt') else '')); return
            at += ' src="%s" alt="%s" loading="lazy"' % (uri, E(a.get('alt', '')))
        elif t in ('td', 'th'):
            for k in ('colspan', 'rowspan'):
                if a.get(k, '').isdigit(): at += ' %s="%s"' % (k, a[k])
        elif t in S_SVG:
            for k, v in a.items():
                if k in S_SVGA: at += ' %s="%s"' % (S_SVGA[k], E(v))
        elif t == 'details' and 'open' in a: at += ' open'
        elif t == 'button':
            if a.get('data-t'): at += ' type="button" data-copia="%s"' % E(a['data-t']); cls += ['btn', 'mini']
            else: at += ' type="button" disabled'; cls += ['btn', 'mini']
        if cls: at += ' class="%s"' % ' '.join(dict.fromkeys(cls))
        if sty: at += ' style="%s"' % sty
        if t == 'table': self.o.append('<div class="tw" data-scroll-x>')
        self.o.append('<%s%s>' % (t, at))
        if t not in S_VOID: self.st.append(t)

    def handle_endtag(self, tag):
        t = HMAP.get(tag, tag)
        if tag in ('audio', 'video'):
            self.mudo = max(0, getattr(self, 'mudo', 0) - 1); d = getattr(self, 'med', None)
            if d and not d['listo']: self.o[d['at']] = aviso_medio({'modo': 'falta', 'origen': ''}, d['tag'])
            self.med = None; return
        if tag in ('script', 'style', 'iframe'):
            self.mudo = max(0, getattr(self, 'mudo', 0) - 1); return
        if tag not in S_OK or t in S_VOID or t not in self.st: return
        while self.st:
            x = self.st.pop(); self.o.append('</%s>' % x + ('</div>' if x == 'table' else ''))
            if x == t: break

    def handle_data(self, d):
        if not getattr(self, 'mudo', 0): self.o.append(E(d))

    def _llenar(self, src):
        d = self.med; a = d['a']; tipo = d['tag']; et = a.get('aria-label') or a.get('title') or ''; m = medio(src, self.base, tipo, et)
        if m['modo'] in ('incrustado', 'enlace'):
            if tipo == 'audio': h = tag_audio(m, et)
            else:
                poster = img_uri(a['poster'], self.base, 640) if a.get('poster') else None
                h = tag_video(m, et, poster, loop='loop' in a, muted='muted' in a) if m['modo'] == 'incrustado' else enlace_video(m['uri'], et, poster)
        else: h = aviso_medio(m, tipo)
        self.o[d['at']] = h; d['listo'] = True

    def cerrar(self):
        while self.st:
            x = self.st.pop(); self.o.append('</%s>' % x + ('</div>' if x == 'table' else ''))

def sanear(h, base=None):
    p = _San(base); p.feed(h); p.close(); p.cerrar(); return ''.join(p.o)

# ───────────────────────── bloques de los informes convertidos y de métricas ─────────────────────────
def fmt(x):
    if x is None: return ''
    return ('%d' % x) if float(x).is_integer() else ('%.1f' % x).replace('.', ',')

def ok_url(u): return bool(re.match(r'^https?://', (u or '').strip(), re.I))

def segs(t):
    m = re.match(r'^\s*(?:(\d+):)?(\d+):(\d{2})\s*$', str(t))
    if m: return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return int(float(t)) if re.match(r'^\s*\d+(\.\d+)?\s*$', str(t)) else None

NIVELES = [(9, 'referencia del sector'), (7, 'sólido'), (5, 'cumple con fallos'), (3, 'fallos que se notan'), (0, 'no cumple')]
def nivel(n): return next((t for lim, t in NIVELES if n >= lim), 'sin puntuar') if n is not None else 'sin puntuar'

def ring(cifra):
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*$', cifra or '')
    if m:
        a, b = float(m.group(1).replace(',', '.')), float(m.group(2).replace(',', '.'))
        if b > 0: return min(100, 100 * a / b), m.group(1), '/' + m.group(2)
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*%\s*$', cifra or '')
    if m and float(m.group(1).replace(',', '.')) <= 100: return float(m.group(1).replace(',', '.')), m.group(1), '%'
    return None

def delta_html(dif, mejora):
    if abs(dif) < 1e-9: return '<i class="dl eq">= igual</i>'
    return '<i class="dl %s">%s %s%s</i>' % ('up' if mejora else 'dn', '▲' if dif > 0 else '▼', '+' if dif > 0 else '−', fmt(abs(round(dif, 2))))

def r_titulo(B, c):
    return '<h3 class="sbt">%s</h3>' % inline(B['pos'][0] if B['pos'] else '')

def r_lista(B, c):
    li = ''.join('<li class="lx hx">%s</li>' % sanear(x[6:], c.get('base')) if x.startswith('!html ') else '<li>%s</li>' % inline(x) for x in B['items'])
    return '<div class="lsc">%s<ul>%s</ul></div>' % (titulo(B), li)

def r_copiable(B, c):
    lab = B['pos'][0] if B['pos'] else 'Texto'
    return ('<div class="cpb"><div class="cpt"><b>%s</b><button class="btn mini" data-cp>%s<span>Copiar</span></button></div><pre>%s</pre></div>' % (inline(lab), ic('copy'), E(B['md'])))

def r_archivos(B, c):
    out = ''
    for r in B['rows']:
        ti, ruta, nota = (r + ['', '', ''])[:3]
        out += ('<div class="arf"><div class="arh"><b>%s</b><button class="btn mini" data-cp>%s<span>Copiar ruta</span></button></div>%s<code class="rp"><bdi>%s</bdi></code></div>' %
                (inline(ti), ic('copy'), '<small>%s</small>' % inline(nota) if nota else '', E(ruta)))
    return '%s<div class="rk">%s</div>' % (titulo(B), out)

def r_enlaces(B, c):
    out = ''
    for r in B['rows']:
        ti, url, nota = (r + ['', '', ''])[:3]
        if ok_url(url):
            out += '<a class="arf lnk" href="%s" target="_blank" rel="noopener"><span><b>%s</b>%s</span><em>Abrir ↗</em></a>' % (E(url), inline(ti), '<small>%s</small>' % inline(nota) if nota else '')
        else:
            out += '<div class="arf"><b>%s</b>%s%s</div>' % (inline(ti), '<small>%s</small>' % inline(nota) if nota else '', '<code>%s</code>' % E(url) if url else '')
    return '%s<div class="rk">%s</div>' % (titulo(B), out)

def r_revisar(B, c):
    base = B['kw'].get('url', ''); li = ''
    for r in B['rows']:
        t, que, alt, url = (r + ['', '', '', ''])[:4]; u = url or base; s = segs(t)
        chip = ('<a class="tm" href="%s#t=%d" target="_blank" rel="noopener">%s</a>' % (E(u), s, E(t)) if ok_url(u) and s is not None else '<span class="tm">%s</span>' % E(t))
        li += '<li class="rvi">%s<div>%s%s</div></li>' % (chip, inline(que), '<small>%s</small>' % inline(alt) if alt else '')
    return '%s<ul class="rvs">%s</ul>' % (titulo(B), li)

def r_metricas(B, c):
    out = ''
    for r in B['rows']:
        nom, a, d, lo, hi, mx, un, mejor, nota = (r + [''] * 9)[:9]
        na, nd, nlo, nhi, nmx = num(a), num(d), num(lo), num(hi), num(mx) or 100
        if nd is None: continue
        un = un.strip(); bajo = mejor.strip().lower() == 'bajo'; pct = lambda v: max(0, min(100, 100 * v / nmx))
        if bajo and nhi is not None: bueno = nd <= nhi
        elif nlo is not None: bueno = nd >= nlo
        else: bueno = True
        u = ('\u00a0' + un) if un else ''
        band = '<i class="band" style="left:%.1f%%;width:%.1f%%"></i>' % (pct(nlo), max(1.5, pct(nhi) - pct(nlo))) if nlo is not None and nhi is not None else ''
        dif = (nd - na) if na is not None else 0
        delta = delta_html(dif, (dif < 0) if bajo else (dif > 0)) if na is not None else ''
        marca_a = '<i class="mk a" style="left:%.1f%%"></i>' % pct(na) if na is not None else ''
        nicho = 'Referencia %s–%s%s' % (fmt(nlo), fmt(nhi), u) if nlo is not None and nhi is not None else ''
        pie_ = ' · '.join(x for x in (nicho, inline(nota) if nota else '') if x)
        out += ('<div class="mtr %s"><div class="mth"><span class="mtl">%s</span><span class="mtv">%s%s <s>→</s> %s%s %s</span></div><div class="trk">%s%s<i class="mk d" style="left:%.1f%%"></i></div>%s</div>' %
                (tn('ok' if bueno else 'bad'), inline(nom), fmt(na) if na is not None else '', u if na is not None else '', fmt(nd), u, delta, band, marca_a, pct(nd), '<p class="mn">%s</p>' % pie_ if pie_ else ''))
    return '<div class="card">%s%s</div>' % (titulo(B), out)

def r_comparar(B, c):
    cap = B['pos'][0] if B['pos'] else 'Antes y después'
    a, d = img_uri(B['kw'].get('antes', ''), c.get('base')), img_uri(B['kw'].get('despues', ''), c.get('base'))
    if not a or not d:
        return '<aside class="nt t-bad">%s<div><b class="nh">%s</b><p>No se encontró una de las dos imágenes.</p></div></aside>' % (ic('alert-triangle'), inline(cap))
    return ('<figure class="ab"><figcaption>%s</figcaption><div class="abw"><img src="%s" alt="Antes"><div class="abd"><img src="%s" alt="Después"></div><i></i>'
            '<input type="range" min="0" max="100" value="50" aria-label="Comparar antes y después"></div><div class="abl"><span>Antes</span><span>Después</span></div>%s</figure>' % (inline(cap), a, d, guia_cambio(B['kw'])))

def r_rubrica(B, c):
    kw = B['kw']; ant, nue = num(kw.get('anterior')), num(kw.get('nota')); rows = ''
    for r in B['rows']:
        nom, peso, a, d, mot, ev = (r + [''] * 6)[:6]; na, nd = num(a), num(d)
        if na is not None and nd is not None:
            sc = '%s → <b>%s</b> %s' % (fmt(na), fmt(nd), delta_html(round(nd - na, 1), nd > na) if abs(nd - na) > 1e-9 else '<i class="dl eq">=</i>')
        else: sc = '<b>%s</b>' % fmt(nd) if nd is not None else '—'
        rows += ('<details class="cr"><summary><span class="cn">%s <small>· pesa %s %%</small></span><span class="cs">%s</span><span class="cm">%s</span></summary><div><p>Nivel: %s.</p>%s</div></details>' %
                 (inline(nom), E(peso), sc, inline(mot), nivel(nd), '<p><b>Evidencia:</b> %s</p>' % inline(ev) if ev else ''))
    dl, tono = '', 'n'
    if ant is not None and nue is not None:
        df = round(nue - ant, 1); dl = delta_html(df, df > 0); tono = 'ok' if df > 0 else 'bad' if df < 0 else 'n'
    head = ('<div class="rbh"><div class="rbn"><small>%s</small><b>%s</b></div><span class="arw">→</span><div class="rbn %s"><small>ahora</small><b>%s</b></div>%s</div>' %
            (E(kw.get('tanda', 'anterior')), fmt(ant) if ant is not None else '—', tn(tono), fmt(nue) if nue is not None else '—', dl))
    return ('<div class="rbk">%s%s%s%s<p class="hint">Valoración con una rúbrica fija de %d criterios (no es una métrica de la plataforma). Toque un criterio para ver su evidencia.</p></div>' %
            (titulo(B), head, '<p class="bs">%s</p>' % inline(kw['resumen']) if kw.get('resumen') else '', rows, len(B['rows'])))

def r_html(B, c):
    return '%s<div class="hx">%s</div>' % (titulo(B), sanear(B['md'], c.get('base')))


# ───────────────────────── medios: audio, vídeo, imagen y storyboard (v2.2) ─────────────────────────
# Regla del motor: ningún medio se descarta en silencio. Un audio o un clip se incrusta (el archivo único abre sin conexión);
# un vídeo largo va como enlace (verificado o marcado «sin verificar»); lo que no cabe o no aparece se avisa EN el informe.
# Cada medio queda anotado en medios.json para que el sello cuente reproductores y no solo palabras.
MIMES = {'.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.opus': 'audio/ogg', '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.flac': 'audio/flac',
         '.mp4': 'video/mp4', '.m4v': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime'}
MEDIA_TOPE = 8 << 20          # por archivo incrustado; lo que pese más va como enlace y el sello lo marca
BASES, _MED, _MEDC, _SEQ = [], [], {}, [0]

def kb_(n): return ('%.1f MB' % (n / 1048576)).replace('.', ',') if n >= 1048576 else '%d KB' % max(1, round(n / 1024))
def _nid(p): _SEQ[0] += 1; return '%s%d' % (p, _SEQ[0])
def _si(v): return str(v or '').strip().lower() in ('1', 'si', 'sí', 'true', 'yes')
def _kv(s): return args(s)[1] if s else {}

def hallar(src, base=None):
    """Busca un archivo: ruta absoluta, o relativa a la carpeta del informe, a la de su fuente y, por último, a la actual."""
    p = pathlib.Path(re.sub(r'^file:///', '', str(src).strip()))
    cand = [p] if p.is_absolute() else [pathlib.Path(b) / p for b in ([base] if base else []) + BASES] + [p]
    for q in cand:
        try:
            if q.is_file(): return q
        except OSError: pass
    return None

def medio(src, base, tipo, et=''):
    """Resuelve un audio o un vídeo. modo: incrustado (data URI) · enlace (URL) · pesado (supera el tope) · falta (no hay archivo)."""
    src = (src or '').strip(); k = (hashlib.md5(src.encode('utf8', 'ignore')).hexdigest(), str(base), tipo)
    if k in _MEDC: return _MEDC[k]
    r = {'tipo': tipo, 'etiqueta': et, 'origen': 'incluido en el original' if src.startswith('data:') else src[:240], 'modo': 'falta', 'uri': '', 'md5': '', 'bytes': 0, 'mime': '', 'motivo': ''}
    raw = None
    try:
        if src.startswith('data:'):
            head, _, body = src.partition(','); mime = head[5:].split(';')[0].lower()
            if mime.startswith(tipo + '/'):
                raw = base64.b64decode(re.sub(r'\s+', '', body)) if ';base64' in head else urllib.parse.unquote_to_bytes(body); r['mime'] = mime
            else: r['motivo'] = 'tipo de archivo %s' % mime
        elif re.match(r'^https?://', src, re.I): r.update(modo='enlace', uri=src)
        elif src:
            p = hallar(src, base)
            if not p: r['motivo'] = 'no se encontró el archivo'
            else:
                mime = MIMES.get(p.suffix.lower())
                if mime and mime.startswith(tipo + '/'): raw = p.read_bytes(); r['mime'] = mime
                else: r['motivo'] = 'formato %s no reconocido' % (p.suffix or 'sin extensión')
        else: r['motivo'] = 'sin archivo'
    except Exception as e: r['motivo'] = 'no se pudo leer (%s)' % e.__class__.__name__
    if raw is not None:
        r.update(md5=hashlib.md5(raw).hexdigest(), bytes=len(raw), dur=duracion(raw, '.' + r['mime'].split('/')[-1].replace('mpeg', 'mp3')))
        if len(raw) > MEDIA_TOPE: r.update(modo='pesado', motivo='pesa %s (tope %d MB por archivo)' % (kb_(len(raw)), MEDIA_TOPE >> 20))
        else: r.update(modo='incrustado', uri='data:%s;base64,%s' % (r['mime'], base64.b64encode(raw).decode()))
    _MEDC[k] = r; _MED.append({a: b for a, b in r.items() if a != 'uri' or r['modo'] == 'enlace'}); return r

_DUR = {}
def duracion(raw, ext):
    """Duración real (segundos) de un audio o vídeo, medida con ffprobe; None si no se puede. Así el informe nunca muestra una duración escrita a mano que no es."""
    ff = shutil.which('ffprobe'); k = hashlib.md5(raw).hexdigest()
    if k in _DUR: return _DUR[k]
    d = None
    if ff:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext or '.bin') as tf: tf.write(raw); ruta = tf.name
        try:
            r = subprocess.run([ff, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta], capture_output=True, text=True, timeout=30)
            d = float(r.stdout.strip().split()[0]); d = d if d > 0 else None
        except Exception: d = None
        finally:
            try: pathlib.Path(ruta).unlink()
            except OSError: pass
    _DUR[k] = d; return d

def dur_txt(m, ex):
    if m and m.get('dur'): return '%d:%02d' % divmod(round(m['dur']), 60)
    return ex.get('dur', '')

def aviso_medio(m, tipo):
    nom = 'Audio' if tipo == 'audio' else 'Vídeo'
    msg = 'Pesa demasiado para ir dentro del informe.' if m.get('modo') == 'pesado' else 'No se encontró el archivo.' if m.get('modo') == 'falta' else 'No se pudo cargar.'
    ruta = m.get('origen', '')
    return ('<aside class="nt t-warn">%s<div><b class="nh">%s no incluido</b><p>%s</p>%s</div></aside>' %
            (ic('alert-triangle'), nom, E(msg), '<code class="rp"><bdi>%s</bdi></code>' % E(ruta) if ruta and ruta != 'incluido en el original' else ''))

def tag_audio(m, et='', idd=''):
    return '<audio%s class="ma" controls preload="%s" src="%s" aria-label="%s"></audio>' % (' id="%s"' % idd if idd else '', 'metadata' if m['modo'] == 'incrustado' else 'none', m['uri'] if m['modo'] == 'incrustado' else E(m['uri']), E('Audio: ' + et if et else 'Audio'))

def tag_video(m, et='', poster=None, idd='', loop=False, muted=False):
    return ('<video%s class="mv" controls playsinline preload="metadata"%s%s%s src="%s" aria-label="%s"></video>' %
            (' id="%s"' % idd if idd else '', ' poster="%s"' % poster if poster else '', ' loop' if loop else '', ' muted' if muted else '', m['uri'], E('Vídeo: ' + et if et else 'Vídeo')))

def enlace_video(url, et='', poster=None, vertical=False):
    return ('<a class="mdl%s" href="%s" target="_blank" rel="noopener" aria-label="Abrir el vídeo: %s"><span class="mdpo">%s</span><span class="mdpl">%s</span></a>' %
            (' vert' if vertical else '', E(url), E(et or 'sin título'), '<img src="%s" alt="">' % poster if poster else '', ic('player-play')))

def dims(uri):
    """Ancho y alto de una imagen incrustada (solo la cabecera): con ellos el navegador reserva el hueco y nada salta al cargar."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(base64.b64decode(uri.partition(',')[2]))) as im: return im.width, im.height
    except Exception: return None

def wh(uri):
    d = dims(uri) if uri and uri.startswith('data:') else None
    return ' width="%d" height="%d"' % d if d else ''

def _vertical(src, base):
    """¿La imagen de portada del vídeo es vertical? (un Short se muestra estrecho, no recortado)"""
    try:
        from PIL import Image
        p = hallar(src, base)
        if p:
            with Image.open(p) as im: return im.height > im.width * 1.2
    except Exception: pass
    return False

def _pistas(rows):
    """Las filas de un bloque audio/vídeo: las que empiezan por un minuto son la guía (m:ss | qué | nota); el resto, los archivos."""
    pistas, cues = [], []
    for r in rows:
        r = (r + ['', '', '', ''])[:4]
        (cues if re.match(r'^\d{1,2}(:\d{2}){1,2}$', r[0].strip()) else pistas).append(r)
    return pistas, cues

def guia_cues(cues, para=None, url=None):
    """Guía de revisión: en qué segundos fijarse. Con un enlace de vídeo cada minuto lo abre en ese punto; con un reproductor, salta ahí."""
    if not cues: return ''
    li = ''
    for t, que, nota, _x in cues:
        s = segs(t)
        if s is None: chip = '<span class="tm">%s</span>' % E(t)
        elif url: chip = '<a class="tm tmi" href="%s#t=%d" target="_blank" rel="noopener">%s%s</a>' % (E(url), s, ic('player-play'), E(t))
        elif para: chip = '<button type="button" class="tm tmi" data-seek="%d" data-para="%s">%s%s</button>' % (s, E(para), ic('player-play'), E(t))
        else: chip = '<span class="tm">%s</span>' % E(t)
        li += '<li class="rvi">%s<div>%s%s</div></li>' % (chip, inline(que), '<small>%s</small>' % inline(nota) if nota else '')
    return '<ul class="rvs">%s</ul>' % li

def guia_cambio(kw): return '<p class="mdq"><b>Qué cambió:</b> %s</p>' % inline(kw['cambio']) if kw.get('cambio') else ''
def guia_celular(kw): return '<p class="mdq mdm">%s<span><b>En el celular:</b> %s</span></p>' % (ic('device-mobile'), inline(kw['celular'])) if kw.get('celular') else ''

def _conmutador(n):
    return ('<div class="mdsw"><button type="button" class="btn mini" data-ab-sw>%s<span>Alternar A/B en el mismo punto</span></button><span class="hint" aria-live="polite" data-ab-st></span></div>' % ic('arrows-exchange')) if n else ''

def r_audio(B, c):
    kw, base = B['kw'], c.get('base'); pistas, cues = _pistas(B['rows'])
    if not pistas and kw.get('src'): pistas = [[kw.get('etiqueta', ''), kw['src'], '', '']]
    gid = _nid('au'); ab = _si(kw.get('ab')) and len(pistas) > 1; filas, primero = '', None
    for i, (et, src, nota, extra) in enumerate(pistas):
        ex = dict(kw, **_kv(extra)); m = medio(src, base, 'audio', et); pid = '%s-%d' % (gid, i); primero = primero or pid
        info = ' · '.join(x for x in (dur_txt(m, ex), kb_(m['bytes']) if m['bytes'] else '') if x)
        cuerpo = tag_audio(m, et, pid) if m['modo'] in ('incrustado', 'enlace') else aviso_medio(m, 'audio')
        cab = '<div class="mdh"><b>%s</b>%s</div>' % (inline(et), '<small>%s</small>' % E(info) if info else '') if et or info else ''
        filas += '<div class="mdp%s">%s%s%s</div>' % (' on' if ab and i == 0 else '', cab, cuerpo, '<p class="mn">%s</p>' % inline(nota) if nota else '')
    return '<div class="card mdx"%s>%s%s%s%s%s%s</div>' % (' data-ab' if ab else '', titulo(B), guia_cambio(kw), filas, _conmutador(ab), guia_cues(cues, primero), guia_celular(kw))

def r_video(B, c):
    kw, base = B['kw'], c.get('base'); pistas, cues = _pistas(B['rows'])
    if not pistas and (kw.get('url') or kw.get('clip') or kw.get('src')): pistas = [[kw.get('etiqueta', ''), kw.get('clip') or kw.get('src') or kw.get('url'), '', '']]
    gid = _nid('vi'); filas, para, url_g, embebidos = '', None, None, 0
    base_kw = {k: v for k, v in kw.items() if k in ('poster', 'dur', 'peso', 'md5', 'verificado', 'caduca', 'local', 'url', 'loop', 'muted', 'ar')}
    for i, (et, src, nota, extra) in enumerate(pistas):
        ex = dict(base_kw, **_kv(extra)); m = medio(src, base, 'video', et) if src else None
        url = ex.get('url') or (m['uri'] if m and m['modo'] == 'enlace' else '')
        poster = img_uri(ex['poster'], base, 640) if ex.get('poster') else None; pid = '%s-%d' % (gid, i)
        vert = ex.get('ar', '').replace(' ', '') in ('9:16', 'vertical') or (not ex.get('ar') and bool(ex.get('poster')) and _vertical(ex['poster'], base))
        if m and m['modo'] == 'incrustado':
            rep = tag_video(m, et, poster, pid, loop=_si(ex.get('loop')), muted=_si(ex.get('muted'))); para = para or pid; embebidos += 1
        elif url: rep = enlace_video(url, et, poster, vert); url_g = url_g or url
        else: rep = aviso_medio(m or {'modo': 'falta', 'origen': ''}, 'video')
        estado = ''
        if url:
            ok = _si(ex.get('verificado'))
            estado = '<span class="chip %s">%s%s</span>' % ('t-ok' if ok else 't-warn', ic('circle-check' if ok else 'alert-triangle'), 'Enlace verificado' if ok else 'Enlace sin verificar')
        det = re.sub(r'(\d) (h|min|s|MB|KB)\b', '\\1\u00a0\\2', ' · '.join(x for x in (dur_txt(m, ex), ex.get('peso') or (kb_(m['bytes']) if m and m['bytes'] else ''), ('md5 ' + ex['md5']) if ex.get('md5') else '', ('caduca en ' + ex['caduca']) if ex.get('caduca') else '') if x))
        boton = '<a class="btn p mdb" href="%s" target="_blank" rel="noopener">%s<span>%s</span></a>' % (E(url), ic('external-link'), 'Ver el vídeo completo' if embebidos and m and m['modo'] == 'incrustado' else 'Abrir el vídeo') if url else ''
        local = '<div class="arf"><div class="arh"><b>En su PC</b><button class="btn mini" data-cp>%s<span>Copiar ruta</span></button></div><code class="rp"><bdi>%s</bdi></code></div>' % (ic('copy'), E(ex['local'])) if ex.get('local') else ''
        cab = '<div class="mdh"><b>%s</b>%s</div>' % (inline(et), '<small>%s</small>' % E(det) if det else '') if et or det else ''
        filas += '<div class="mdp mdv%s">%s%s%s%s%s%s</div>' % (' vert' if vert else '', cab, rep, '<p class="mn">%s</p>' % inline(nota) if nota else '', estado, boton, local)
    ab = _si(kw.get('ab')) and embebidos > 1
    if ab: filas = filas.replace('class="mdp mdv', 'class="mdp on mdv', 1)
    return '<div class="card mdx"%s>%s%s%s%s%s%s</div>' % (' data-ab' if ab else '', titulo(B), guia_cambio(kw), filas, _conmutador(ab), guia_cues(cues, para, None if para else url_g), guia_celular(kw))

SB_CLAVES = {'n': 'n', 'nº': 'n', 'cuadro': 'n', 'tramo': 'tramo', 'img': 'img', 'imagen': 'img', 'voz': 'voz', 'entra': 'entra', 'sonido': 'sonido', 'rotulo': 'rotulo', 'rótulo': 'rotulo',
             'medida': 'medida', 'nota': 'nota', 'aprox': 'aprox'}

def cuadros_de(inner):
    """Cuadros de un storyboard: bloques «clave: valor» separados por una línea ---."""
    out, cur, last = [], None, None
    for l in inner:
        s = l.strip()
        if re.match(r'^-{3,}$', s):
            if cur: out.append(cur)
            cur, last = None, None; continue
        if not s: continue
        m = re.match(r'^([A-Za-zÁÉÍÓÚÑáéíóúñº]+)\s*:\s*(.*)$', s); k = SB_CLAVES.get(m.group(1).lower()) if m else None
        if k:
            if cur is None: cur = {}
            cur[k] = m.group(2).strip(); last = k
        elif cur is not None and last: cur[last] += ' ' + s
    if cur: out.append(cur)
    return out

def r_storyboard(B, c):
    cu = B.get('cuadros') or []
    if not cu: return ''
    base = c.get('base'); gid = _nid('sb'); aprox = _si(B['kw'].get('aprox')); tira = cards = ''
    for i, q in enumerate(cu):
        n = q.get('n') or str(i + 1); idc = '%s-%d' % (gid, i); src = q.get('img', '')
        th, im = (img_uri(src, base, 200), img_uri(src, base, 720)) if src else (None, None)
        tira += '<a class="stt" href="#%s" aria-label="Ir al cuadro %s">%s<b>%s</b>%s</a>' % (idc, E(n), '<img src="%s" alt="">' % th if th else '', E(n), ic('arrow-down'))
        ap = aprox or _si(q.get('aprox'))
        cab = '<div class="sth"><span class="stn">%s</span>%s</div>' % (E(n), '<span class="stg">%s%s</span>' % (E(q['tramo']), '<small>aprox.</small>' if ap else '') if q.get('tramo') else '')
        foto = '<img src="%s"%s alt="%s" loading="lazy">' % (im, wh(im), E('Cuadro %s%s' % (n, ': ' + re.sub(r'[«»]', '', q['voz'])[:90] if q.get('voz') else ''))) if im else '<div class="stx">Sin imagen para este cuadro</div>'
        voz = '<blockquote class="stv">%s</blockquote>' % inline(q['voz']) if q.get('voz') else ''
        dl = ''.join('<div><dt>%s</dt><dd>%s</dd></div>' % (lab, inline(q[k])) for k, lab in (('entra', 'Entra'), ('sonido', 'Sonido'), ('rotulo', 'Rótulo'), ('nota', 'Nota')) if q.get(k))
        med = q.get('medida', ''); mt = ''
        if med:
            tono = 'n'
            if '|' in med and med.rsplit('|', 1)[1].strip().lower() in ('ok', 'warn', 'bad', 'info', 'n'): med, tono = med.rsplit('|', 1)[0], med.rsplit('|', 1)[1].strip().lower()
            mt = '<p class="stm %s">%s<span>%s</span></p>' % (tn(tono), ic('circle-check' if tono == 'ok' else 'alert-triangle' if tono in ('warn', 'bad') else 'target-arrow'), inline(med.strip()))
        cards += '<figure class="stf" id="%s">%s%s%s%s%s</figure>' % (idc, cab, foto, voz, ('<dl class="std">%s</dl>' % dl) if dl else '', mt)
    return '<section class="stb">%s<p class="hint">Toque un número para ir a ese cuadro.</p><nav class="stts" aria-label="Cuadros" data-scroll-x>%s</nav><div class="stg2">%s</div></section>' % (titulo(B), tira, cards)

def r_imagen(B, c):
    kw = B['kw']; u = img_uri(kw.get('src', ''), c.get('base'))
    if not u: return '<aside class="nt t-warn">%s<div><b class="nh">Imagen no incluida</b><p>No se encontró el archivo.</p></div></aside>' % ic('alert-triangle')
    return '%s<figure class="imf"><img src="%s"%s alt="%s" loading="lazy">%s</figure>' % (titulo(B), u, wh(u), E(kw.get('alt') or (B['pos'][0] if B['pos'] else '')), '<figcaption>%s</figcaption>' % inline(kw['pie']) if kw.get('pie') else '')

def firma_medios(doc):
    """Huella de los archivos que usa el documento: si cambia un audio o una imagen sin cambiar el texto, el sello anterior deja de valer."""
    h = hashlib.sha256()
    def vals(B):
        for r in B.get('rows', []):
            yield from r
        yield from B.get('kw', {}).values()
        for q in B.get('cuadros', []): yield from q.values()
        for x in B.get('hijos', []): yield from vals(x)
    for s in doc['secciones']:
        for B in s['bloques']:
            for v in vals(B):
                if isinstance(v, str) and 3 < len(v) < 400 and not v.startswith(('http', 'data:')):
                    p = hallar(v)
                    if p:
                        try: st = p.stat(); h.update(('%s:%d:%d' % (p.name, st.st_size, st.st_mtime_ns)).encode())
                        except OSError: pass
    return h.hexdigest()[:12]


def blk(B, c):
    t = B['t']
    if t == 'texto': return md_basic(B['md'])
    if t == 'codigo': return '<pre class="cd">%s</pre>' % E(B['md'])
    if t == 'detalle':
        return '<details class="dt"><summary><span>%s</span><em class="dv a">Ver</em><em class="dv b">Ocultar</em>%s</summary><div class="db">%s</div></details>' % (inline(B['pos'][0] if B['pos'] else 'Detalle'), ic('chevron-down'), ''.join(blk(h, c) for h in B['hijos']))
    f = globals().get('r_' + t)
    return f(B, c) if f else '<aside class="nt t-bad">%s<div><p>Bloque desconocido: %s</p></div></aside>' % (ic('x'), E(t))

def blocks(bl, c): return ''.join(blk(b, c) for b in bl)

# ───────────────────────── auxiliares de vista ─────────────────────────
def walk(bl):
    for b in bl:
        yield b
        if b['t'] == 'detalle': yield from walk(b['hijos'])

def palabras(doc, esencial=False):
    def tx(B):
        md = B.get('md', '')
        if B['t'] == 'html': md = re.sub(r'<[^>]+>', ' ', md)
        s = [md, B.get('h', '')] + B.get('b', []) + B.get('det', []) + B.get('items', []) + [' '.join(r) for r in (B.get('rows', []) if B['t'] not in ('audio', 'video') else [[x[0]] + x[2:3] for x in B['rows'] if x])] + [o[0] for o in B.get('ops', [])] + [v for q in B.get('cuadros', []) for k, v in q.items() if k != 'img']
        return sum(len(re.findall(r'\w+', x)) for x in s)
    n = 0
    for k, s in enumerate(doc['secciones']):
        n += len(re.findall(r'\w+', s['lead'])) + (len(re.findall(r'\w+', s['titulo'])) if esencial else 0)
        if esencial:
            if k == 0: n += sum(tx(b) for b in s['bloques'])
        else: n += sum(tx(b) for b in walk(s['bloques']))
    return n

def decisiones(doc): return [(s, b) for s in doc['secciones'] for b in s['bloques'] if b['t'] == 'decision']

def figura(s):
    if 'fig' in s['kw']:
        a, _, b = s['kw']['fig'].partition('|'); return a, b, s['kw'].get('ft', 'n')
    for b in s['bloques']:
        if b['t'] == 'ranking': return str(len(b['rows'])), 'hallazgos', 'n'
        if b['t'] == 'decision': return str(sum(1 for x in s['bloques'] if x['t'] == 'decision')), 'por decidir', 'warn'
        if b['t'] == 'pasos': return str(len(b['rows'])), 'fases', 'n'
    return '', '', 'n'

def cabecera(doc, vid, tm=False):
    m = doc['meta']; e, tot = palabras(doc, True), palabras(doc)
    r1, r2 = max(1, round(e / 190)), max(2, round(tot / 190))
    btn = ('<button class="ic tm2" id="tema" aria-label="Cambiar entre tema claro y oscuro">%s</button>' % ic('sun')) if tm else ''
    return ('<header class="hd" id="%s-top"><div class="kk"><p class="kick">%s · %s</p>%s</div><h1>%s</h1><p class="sub">%s</p><div class="rd"><span class="chip">%s Rápida %d min · completa %d min</span>'
            '<button class="chip tp" data-todo>%s<span>Abrir todo</span></button></div></header>' %
            (vid, E(m.get('tipo', 'informe').capitalize()), E(m.get('fecha', '')), btn, E(m['titulo']).replace(' · ', ' · '), E(m.get('subtitulo', '')), ic('clock'), r1, r2, ic('chevron-down')))

def ask(doc, vid, destino):
    ds = decisiones(doc)
    if not ds: return ''
    s, b = ds[0]; q = b['pos'][1] if len(b['pos']) > 1 else ''
    n = len(ds); tit = '1 decisión pendiente' if n == 1 else '%d decisiones pendientes' % n
    return ('<button class="ask" data-ir="%s">%s<span><b>%s</b><small>%s%s</small></span>%s</button>' % (destino, ic('checklist'), tit, '' if n == 1 else 'Primera: ', inline(q), ic('arrow-right', 'go')))

FICHA = {'A': ('Briefing', 'Una sola columna en capas: veredicto, evidencia y decisión, con todo el detalle plegado.', ['Mejor para: investigaciones y cierres de etapa.', 'Contra: más desplazamiento vertical.']),
         'B': ('Tablero', 'Cifras arriba y un mosaico de módulos. Cada toque abre una hoja con el detalle sin perder el lugar.', ['Mejor para: estado de varios frentes (proyectos, equipos, métricas).', 'Contra: el detalle queda un toque más lejos.']),
         'C': ('Dossier', 'Cinco pestañas fijas abajo, siempre en el mismo orden: Resumen, Datos, Análisis, Decidir, Fuentes.', ['Mejor para: investigaciones largas, de más de 10 minutos.', 'Contra: oculta contenido detrás de pestañas.'])}
def ficha(v):
    n, d, ul = FICHA[v]
    return '<div class="fi-v" data-v="%s" hidden><b>Propuesta %s · %s</b><p>%s</p><ul>%s</ul></div>' % (v, v, n, d, ''.join('<li>%s</li>' % x for x in ul))

def pie(doc, c):
    sk = doc['meta'].get('skills', '')
    txt = ', '.join(str(s) for s in sk) if isinstance(sk, (list, tuple)) else str(sk)
    if not txt.strip(): return ''
    return '<footer class="foot"><b>Skills cargadas:</b> %s</footer>' % _skills_html(txt)

def _skills_html(txt):
    # Cada palabra se toma ENTERA (entre separadores): si lleva guion y mide hasta 40 caracteres (un slug) viaja entera;
    # el resto del texto fluye normal. Nunca trocear una palabra (el verificador de contenido contaría dos).
    out, i = [], 0
    for m in re.finditer(r'[^\s,;·()\[\]]+', txt):
        out.append(E(txt[i:m.start()]))
        tok = m.group(0)
        out.append('<span class="sk">%s</span>' % E(tok) if '-' in tok and len(tok) <= 40 else E(tok))
        i = m.end()
    out.append(E(txt[i:]))
    return ''.join(out)

# ───────────────────────── vistas ─────────────────────────
def nav_items(doc, vid):
    out = []
    for k, lab, ico in TABS:
        s = next((x for x in doc['secciones'] if x['tab'] == k), None)
        if s: out.append((k, lab, ico, '%s-top' % vid if k == 'resumen' else '%s-%s' % (vid, s['id'])))
    return out

def portada_con(bl, c, extra):
    out = ''
    for b in bl:
        out += blk(b, c)
        if b['t'] == 'veredicto': out += extra
    if extra and not any(b['t'] == 'veredicto' for b in bl): out += extra
    return out

def vista_A(doc, c, show=True):
    c = dict(c, vid='A'); portada, resto = doc['secciones'][0], doc['secciones'][1:]; ds = decisiones(doc)
    dest = '%s-%s' % ('A', ds[0][0]['id']) if ds else ''
    h = cabecera(doc, 'A', c.get('una')) + portada_con(portada['bloques'], c, ask(doc, 'A', dest))
    for k, s in enumerate(resto):
        big, small, tono = figura(s)
        h += ('<details class="cap %s" id="A-%s" data-tab="%s"%s><summary>%s<span class="ct"><b>%s</b><small>%s</small></span><span class="cf"><b>%s</b><small>%s</small></span>%s</summary><div class="cb">%s</div></details>' %
              (tn(tono), s['id'], s['tab'], ' open' if k == 0 else '', ic(s['icono']), inline(s['titulo']), inline(s['lead']), E(big), E(small), ic('chevron-down', 'chev'), blocks(s['bloques'], c)))
    nav = ''.join('<button data-tab="%s" data-ir="%s"%s>%s<span>%s</span></button>' % (k, tid, ' class="on"' if i == 0 else '', ic(ico), lab) for i, (k, lab, ico, tid) in enumerate(nav_items(doc, 'A')))
    return '<div class="vista" id="vista-A"%s><div class="pg"></div>%s<div class="wrap">%s%s</div><nav class="bn" aria-label="Secciones"><div>%s</div></nav></div>' % ('' if show else ' hidden', '', h, pie(doc, c), nav)

def vista_B(doc, c, show=True):
    c = dict(c, vid='B', rib=True); portada, resto = doc['secciones'][0], doc['secciones'][1:]; ds = decisiones(doc)
    malos = [(i, s) for i, s in enumerate(resto) for b in s['bloques'] if b['t'] == 'ranking' for r in b['rows'] if len(r) > 3 and r[3].strip() == 'bad']
    att = ''
    if malos:
        att += '<button class="t-bad" data-sh="%d">%s<span>%s</span>%s</button>' % (malos[0][0], ic('alert-triangle'), ('%d hallazgo crítico' if len(malos) == 1 else '%d hallazgos críticos') % len(malos), ic('arrow-right', 'go'))
    if ds:
        di = next(i for i, s in enumerate(resto) if s is ds[0][0]); att += '<button class="t-warn" data-sh="%d">%s<span>%s</span>%s</button>' % (di, ic('checklist'), ('%d decisión espera su respuesta' if len(ds) == 1 else '%d decisiones esperan su respuesta') % len(ds), ic('arrow-right', 'go'))
    tiles, sheets = '', ''
    for i, s in enumerate(resto):
        big, small, tono = figura(s); last = i == len(resto) - 1 and len(resto) % 2 == 1
        tiles += ('<button class="tile%s %s" data-sh="%d" data-qa>%s<h3>%s</h3><p>%s</p><span class="fg"><b>%s</b><span>%s</span></span><span class="go"><span>Ver detalle</span>%s</span></button>' %
                  (' w' if last else '', tn(tono), i, ic(s['icono']), inline(s['titulo']), inline(re.split(r'(?<=[.!?])\s', s['lead'])[0] if s['lead'] else ''), E(big), E(small), ic('chevron-right')))
        sheets += '<div class="shb" data-t="%s" hidden>%s</div>' % (E(s['titulo']), blocks(s['bloques'], dict(c, rib=False)))
    hoja = ('<div class="sheet" id="hoja" role="dialog" aria-modal="true" aria-label="Detalle"><div class="bk"></div><div class="pn"><div class="gr"></div><header><h2></h2><span class="pos" aria-live="polite"></span>'
            '<button class="cierra" aria-label="Cerrar el detalle">%s<span>Cerrar</span></button></header><div class="bd">%s%s</div>'
            '<nav class="nv" aria-label="Cambiar de detalle"><button class="prev">%s<span class="nl"><small>Anterior</small><b></b></span></button>'
            '<button class="next"><span class="nl"><small>Siguiente</small><b></b></span>%s</button></nav></div></div>' %
            (ic('x'), sheets, pie(doc, c), ic('chevron-right'), ic('chevron-right')))
    body = cabecera(doc, 'B', c.get('una')) + portada_con(portada['bloques'], c, '<div class="att">%s</div>' % att if att else '') + '<p class="tlh">Toque una tarjeta para ver su detalle</p><div class="tl">%s</div>' % tiles
    return '<div class="vista" id="vista-B"%s>%s<div class="wrap">%s</div>%s</div>' % ('' if show else ' hidden', '', body, hoja)

def vista_C(doc, c, show=True):
    c = dict(c, vid='C'); portada = doc['secciones'][0]; pages = {}
    for s in doc['secciones'][1:]: pages.setdefault(s['tab'], []).append(s)
    tabs = [t for t in TABS if t[0] == 'resumen' or t[0] in pages]; ds = decisiones(doc); out = ''
    for i, (k, lab, ico) in enumerate(tabs):
        body = ''
        if k == 'resumen':
            rk = next((b for s in doc['secciones'] for b in s['bloques'] if b['t'] == 'ranking'), None)
            body = portada_con(portada['bloques'], c, ask(doc, 'C', 'C-s%s' % ds[0][0]['id'][1:]) if ds else '')
            if rk: body += '<section class="sec"><div class="sh">%s<h2>Lo más grave</h2></div>%s</section>' % (ic('alert-triangle'), r_ranking(dict(rk, pos=[]), c, rk['rows'][:3]))
        for s in pages.get(k, []):
            body += '<section class="sec" id="C-%s"><div class="sh">%s<h2>%s</h2></div>%s%s</section>' % (s['id'], ic(s['icono']), inline(s['titulo']), '<p class="lead">%s</p>' % inline(s['lead']) if s['lead'] else '', blocks(s['bloques'], c))
        nx = tabs[i + 1] if i + 1 < len(tabs) else None
        if nx: body += '<button class="btn p nx" data-pg="%s">Siguiente: %s %s</button>' % (nx[0], nx[1], ic('arrow-right'))
        else: body += pie(doc, c)
        hd = cabecera(doc, 'C', c.get('una')) if k == 'resumen' else '<div class="cph"><span class="chip">%d de %d</span><h2>%s</h2></div>' % (i + 1, len(tabs), lab)
        out += '<section id="C-pg-%s"%s>%s%s</section>' % (k, ' class="on"' if i == 0 else '', hd, body)
    nav = ''.join('<button data-pg="%s" data-qa%s>%s<span>%s</span></button>' % (k, ' class="on"' if i == 0 else '', ic(ico), lab) for i, (k, lab, ico) in enumerate(tabs))
    return '<div class="vista" id="vista-C"%s>%s<div class="wrap pgs">%s</div><nav class="bn" aria-label="Pestañas"><div>%s</div></nav></div>' % ('' if show else ' hidden', '', out, nav)

# ───────────────────────── documento ─────────────────────────
TEMAS = AQUI / 'temas'
TEMA_POR_DEFECTO = 'neutro'

def ruta_tema(tema=None):
    """Nombre de un tema incluido (neutro, carbon, menta) o ruta a un .css propio con las mismas variables."""
    t = (tema or os.environ.get('INFORME_TEMA') or TEMA_POR_DEFECTO).strip()
    p = pathlib.Path(t)
    if p.suffix.lower() == '.css' and p.is_file(): return p.resolve()
    q = TEMAS / (t.lower() + '.css')
    if q.is_file(): return q
    raise SystemExit('Tema desconocido: %s (incluidos: %s; o una ruta a un .css)' % (t, ', '.join(sorted(f.stem for f in TEMAS.glob('*.css')))))

def pagina_base(titulo_, cuerpo, extra='', tema=None):
    tcss = ruta_tema(tema).read_text(encoding='utf8')
    css = (AQUI / 'estilos.css').read_text(encoding='utf8'); js = (AQUI / 'app.js').read_text(encoding='utf8')
    mbg = re.search(r'--bg:(#[0-9A-Fa-f]{3,8})', tcss); bg = mbg.group(1) if mbg else '#111214'
    f = base64.b64encode((AQUI / 'assets' / 'sora-latin-wght.woff2').read_bytes()).decode()
    ff = "@font-face{font-family:Sora;src:url(data:font/woff2;base64,%s) format('woff2');font-weight:100 800;font-display:swap}" % f
    return ('<!doctype html><html lang="es" data-t="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="dark light">'
            '<meta name="generator" content="informe-movil %s"><meta name="theme-color" content="%s"><title>%s</title><noscript><style>.seg,.ic,.cmp{display:none}</style></noscript><style>%s%s%s</style></head><body>%s%s%s<script>%s</script></body></html>' %
            (VERSION, bg, E(titulo_), ff, tcss, css, sprite(), cuerpo, extra, js))

def construir(doc, modo='una', vista='A', qa=None, base=None, tema=None):
    m = doc['meta']; vs = {'A': vista_A, 'B': vista_B, 'C': vista_C}; c = {'qa': qa, 'una': modo == 'una', 'base': base}
    if doc['secciones'] and not any(b['t'] == 'verificacion' for s in doc['secciones'] for b in walk(s['bloques'])):
        doc['secciones'][-1]['bloques'].append({'t': 'verificacion', 'pos': [], 'kw': {}})
    if modo == 'comparar':
        top = ('<header class="top"><div class="tb"><div class="seg" role="tablist" aria-label="Propuestas">%s</div><button class="ic" id="info" aria-label="Qué es cada propuesta" aria-expanded="false">%s</button><button class="ic" id="tema" aria-label="Cambiar entre tema claro y oscuro">%s</button></div><div class="fi-p" id="fip" hidden>%s</div></header>' %
               (''.join('<button data-v="%s" data-qa role="tab"><b>%s</b><span>%s</span></button>' % (v, v, FICHA[v][0]) for v in 'ABC'), ic('info-circle'), ic('sun'), ''.join(ficha(v) for v in 'ABC')))
        cuerpo = top + ''.join(vs[v](doc, c, v == 'A') for v in 'ABC')
    else:
        cuerpo = vs[vista](doc, c, True)
    cmp_ = ('<div class="cmp" id="cmp" hidden><button class="btn p">%s<span>Copiar respuestas</span></button></div>'
            '<div class="mod" id="mod" role="dialog" aria-modal="true" aria-label="Copiar texto"><div class="card"><div class="mh"><p class="bt">Copiar texto</p><button class="ic mx" aria-label="Cerrar">%s</button></div>'
            '<p class="bs">Toque COPIAR y péguelo donde lo necesite.</p><textarea readonly aria-label="Texto a copiar"></textarea><p class="mfail" hidden>No pude copiar solo. Mantenga pulsado el texto y elija Copiar.</p>'
            '<button class="btn p" id="modc"><span>COPIAR</span></button></div></div>') % (ic('copy'), ic('x'))
    return pagina_base(m.get('titulo', 'Informe'), cuerpo, cmp_, tema)

# ───────────────────────── vista, huella y sello ─────────────────────────
VISTA_POR_TIPO = {'investigacion': 'A', 'investigación': 'A', 'informe': 'A', 'estado': 'B', 'dossier': 'C'}

def elegir_vista(doc, forzada=None):
    if forzada and forzada.upper() in ('A', 'B', 'C'): return forzada.upper()
    m = doc['meta']
    if m.get('vista', '').upper() in ('A', 'B', 'C'): return m['vista'].upper()
    return VISTA_POR_TIPO.get(m.get('tipo', '').lower().strip(), 'A')

def huella(md, vista, modo, extra='', tema=None):
    """Identifica el contenido y el diseño que se midieron: si cambia cualquiera, el sello anterior ya no vale."""
    h = hashlib.sha256()
    for x in (md, vista, modo, extra): h.update(x.encode('utf8'))
    for f in (AQUI / 'estilos.css', AQUI / 'app.js', ruta_tema(tema)): h.update(f.read_bytes())
    return h.hexdigest()[:16]

def ruta_sello(destino): return pathlib.Path(str(destino) + '.sello.json')

def leer_sello(destino, sha):
    f = ruta_sello(destino)
    if not f.exists(): return None
    try: q = json.loads(f.read_text(encoding='utf8'))
    except Exception: return None
    return q if q.get('sha') == sha else None

# Palabras técnicas que, en lo que se lee de corrido, deberían tener entrada en el glosario. Amplíe con INFORME_JERGA="a,b,c".
JERGA = ['API', 'SDK', 'CI', 'CTR', 'CPM', 'KPI', 'MD5', 'fps', 'CTA', 'pipeline', 'QA', 'render', 'endpoint', 'deploy', 'spec', 'prompt', 'commit', 'p95', 'SLA', 'SLO', 'ROI']

def lint_jerga(doc):
    """Palabras técnicas en lo que se lee de corrido (veredicto, KPI, decisiones, listas, avisos) sin entrada en el glosario."""
    jerga = JERGA + [x.strip() for x in os.environ.get('INFORME_JERGA', '').split(',') if x.strip()]
    gl = ' '.join(r[0].lower() for s in doc['secciones'] for b in walk(s['bloques']) if b['t'] == 'glosario' for r in b['rows'])
    partes = []
    for s in doc['secciones']:
        partes += [s['titulo'], s['lead']]
        for b in s['bloques']:
            if b['t'] in ('veredicto',): partes += [b['h']] + b['b']
            elif b['t'] == 'kpis': partes += [c for r in b['rows'] for c in r[:3]]
            elif b['t'] == 'decision': partes += b['pos'][1:] + b['det'] + [o[0] for o in b['ops']]
            elif b['t'] == 'lista': partes += b['items']
            elif b['t'] in ('nota', 'texto'): partes.append(b['md'])
    txt = re.sub(r'<[^>]+>', ' ', ' '.join(partes))
    faltan = [t for t in jerga if t.lower() not in gl and re.search(r'(?<![\w-])' + re.escape(t) + r'(?![\w-])', txt, 0 if t.isupper() else re.I)]
    return 'palabras técnicas fuera del detalle y sin glosario: ' + ', '.join(faltan) if faltan else ''

def generar(fuente, destino, tema=None, vista=None, modo='una', base=None, silencioso=False):
    """Markdown -> un solo HTML. Devuelve dict con doc, medios, sha, vista, avisos y kb. Si existe <destino>.sello.json con la misma huella, el sello se incrusta."""
    src = pathlib.Path(fuente); destino = pathlib.Path(destino)
    _MED.clear(); _MEDC.clear(); _SEQ[0] = 0; BASES[:] = [str(pathlib.Path(x)) for x in (base, src.parent) if x]   # dónde buscar audios, vídeos e imágenes con ruta relativa
    md = src.read_text(encoding='utf8'); avisos = []
    doc = parse(md)
    if not doc['secciones']: raise SystemExit('El archivo no tiene secciones: cada sección empieza con «# Título» (ver references/formato.md).')
    doc['meta'].setdefault('titulo', src.stem)
    vista = elegir_vista(doc, vista); sha = huella(md, vista, modo, firma_medios(doc), tema)
    j = lint_jerga(doc)
    if j: avisos.append(j)
    destino.parent.mkdir(parents=True, exist_ok=True)
    h = construir(doc, modo, vista, leer_sello(destino, sha), destino.parent, tema)
    destino.write_text(h, encoding='utf8')
    medios = list(_MED)
    for m_ in medios:
        if m_['tipo'] in ('audio', 'video') and m_['modo'] in ('pesado', 'falta'): avisos.append('%s no incluido: %s (%s)' % (m_['tipo'], m_.get('motivo', ''), (m_.get('origen') or '')[:80]))
        elif m_['tipo'] == 'imagen' and m_['modo'] == 'falta': avisos.append('imagen no encontrada: %s' % (m_.get('origen') or '')[:80])
    if modo == 'comparar' and any(m_['modo'] == 'incrustado' for m_ in medios): avisos.append('el modo comparar repite los medios en cada propuesta: con audio o vídeo use el modo una')
    kb = destino.stat().st_size // 1024
    if kb > 25 << 10: avisos.append('el archivo pesa %d MB: pesado para abrir en el celular' % (kb >> 10))
    r = {'doc': doc, 'medios': medios, 'sha': sha, 'vista': vista, 'modo': modo, 'avisos': avisos, 'kb': kb, 'destino': destino}
    if not silencioso:
        print('OK %s · %d KB · %d secciones · vista %s · tema %s%s' % (destino, kb, len(doc['secciones']), vista, ruta_tema(tema).stem, (' · avisos: ' + '; '.join(avisos)) if avisos else ''))
    return r

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='informe.py', description='Markdown de bloques -> informe HTML de un solo archivo, pensado para el celular. Con --sellar lo mide a 390 px en Chrome sin pantalla.')
    ap.add_argument('entrada', help='archivo .md con el formato de references/formato.md')
    ap.add_argument('-o', '--salida', help='archivo .html de salida (por defecto, junto a la entrada con extensión .html)')
    ap.add_argument('--tema', help='neutro (por defecto), carbon, menta o ruta a un .css de tema. También: variable INFORME_TEMA')
    ap.add_argument('--vista', choices=['A', 'B', 'C'], help='A Briefing · B Tablero · C Dossier (por defecto, según «tipo:» de la cabecera)')
    ap.add_argument('--modo', default='una', choices=['una', 'comparar'], help='comparar = las tres vistas en un archivo, con selector arriba')
    ap.add_argument('--base', help='carpeta extra donde buscar audios, vídeos e imágenes con ruta relativa')
    ap.add_argument('--sellar', action='store_true', help='mide el HTML (Chrome sin pantalla, 390 px, claro y oscuro, toque a toque) y le incrusta el sello; sale 2 si algo no cumple')
    ap.add_argument('--previo', action='store_true', help='la misma medición que --sellar pero sin estampar: imprime solo lo que falla')
    ap.add_argument('--version', action='version', version='informe-movil ' + VERSION)
    o = ap.parse_args(argv)
    src = pathlib.Path(o.entrada)
    if not src.is_file(): print('No existe:', src); return 1
    destino = pathlib.Path(o.salida) if o.salida else src.with_suffix('.html')
    if o.sellar or o.previo:
        sys.path.insert(0, str(AQUI)); import sellar
        return sellar.sellar(src, destino, tema=o.tema, vista=o.vista, modo=o.modo, base=o.base, estampar=not o.previo)
    generar(src, destino, o.tema, o.vista, o.modo, o.base); return 0

if __name__ == '__main__': sys.exit(main())
