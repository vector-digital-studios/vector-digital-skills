#!/usr/bin/env python3
"""sellar.py · mide un informe en un celular simulado y le pone el sello.
Uso normal: python informe.py entrada.md -o salida.html --sellar   (o --previo para medir sin estampar)

Qué hace: construye el HTML, lo abre en Chrome sin pantalla a 390x844 (modo oscuro y claro), prueba cada interacción
toque a toque, comprueba que el contenido de la fuente está íntegro, escribe <salida>.sello.json y reconstruye el HTML
con el sello incrustado; después vuelve a medir lo que el propio sello pudiera alterar («estable tras el sello»).

Requisitos de la medición: Node 22.12+, `npm install` dentro de scripts/sello/ (instala puppeteer-core) y un Chrome o
Chromium. Chrome se busca en CHROME_PATH y en las rutas habituales de Windows, macOS y Linux.
Variables: CHROME_PATH (ruta a Chrome), NODE (ruta a node), INFORME_PAR (Chrome en paralelo, 2 por defecto).
Códigos de salida: 0 todo cumple · 2 algo no cumple · 3 no hay con qué medir (falta Node, puppeteer-core o Chrome).
"""
import json, subprocess, sys, pathlib, re, datetime, shutil, os, html, urllib.request, urllib.error, tempfile
from concurrent.futures import ThreadPoolExecutor

AQUI = pathlib.Path(__file__).resolve().parent; SELLO = AQUI / 'sello'
NODE = os.environ.get('NODE') or shutil.which('node') or 'node'

def correr(cmd, t=600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=t, encoding='utf8', errors='replace', cwd=str(SELLO)); return p.stdout, p.stderr

def disponible():
    """(True, ruta_de_chrome) si se puede medir; (False, motivo) si falta algo. No lanza excepciones."""
    if not (shutil.which(NODE) or pathlib.Path(NODE).is_file()): return False, 'no encuentro Node (instálelo o defina NODE)'
    if not (SELLO / 'node_modules' / 'puppeteer-core').is_dir(): return False, 'falta puppeteer-core: ejecute «npm install» dentro de scripts/sello/'
    try: o, e = correr([NODE, str(SELLO / 'chrome.mjs')], 60)
    except Exception as ex: return False, 'Node no respondió: %s' % ex
    o = o.strip()
    return (True, o) if o and not o.startswith('ERROR') else (False, (o or e).strip()[-200:] or 'no encuentro Chrome (defina CHROME_PATH)')

def ultima_json(par):
    o, e = par
    for l in reversed(o.strip().splitlines()):
        if l.startswith('{') or l.startswith('['): return json.loads(l)
    raise RuntimeError('la medición no devolvió datos: ' + (e or o)[-400:])

def correr_json(cmd, intentos=2):
    """Una medición que no devuelve datos (Chrome sin memoria, un cuelgue puntual) se repite una vez antes de darla por fallida."""
    ultimo = None
    for _ in range(intentos):
        try: return ultima_json(correr(cmd, 420))
        except Exception as e: ultimo = e
    raise ultimo

def medir(h, vistas, qa_dir, con_pruebas=True):
    with ThreadPoolExecutor(max_workers=int(os.environ.get('INFORME_PAR', '2'))) as ex:   # cada Chrome pesa 100-200 MB
        trabajos = {(v, suf): ex.submit(correr_json, [NODE, str(SELLO / 'qa.mjs'), str(h), str(qa_dir / (v + suf)), '--hash=' + v + suf, '--sin-capturas']) for v in vistas for suf in ('', '-l')}
        pr = ex.submit(correr_json, [NODE, str(SELLO / 'prueba.mjs'), str(h)]) if con_pruebas else None
        res = {k: f.result() for k, f in trabajos.items()}
        pruebas = pr.result() if pr else None
    return res, pruebas

def f1(x): return ('%.1f' % x).replace('.', ',')

def enlaces_video(h):
    """Cada tarjeta de vídeo con enlace debe responder (200/206). Es la única medición con red y solo corre si el informe tiene vídeos enlazados."""
    res = []
    for u in dict.fromkeys(re.findall(r'<a class="mdl[^"]*" href="([^"]+)"', h)):
        u = html.unescape(u); ok, det = False, ''
        for metodo, cab in (('HEAD', {}), ('GET', {'Range': 'bytes=0-0'})):
            try:
                with urllib.request.urlopen(urllib.request.Request(u, method=metodo, headers=dict({'User-Agent': 'Mozilla/5.0'}, **cab)), timeout=20) as r:
                    ct = r.headers.get('Content-Type', '').split(';')[0]; ok = r.status in (200, 206); det = '%s %s' % (r.status, ct); break
            except urllib.error.HTTPError as e: det = 'HTTP %d' % e.code
            except Exception as e: det = e.__class__.__name__
        res.append({'url': u, 'ok': ok, 'detalle': det})
    return res

def lineas(res, pruebas, par, kb, vistas):
    L = []; vals = list(res.values()); oscuro = [r for (v, s), r in res.items() if s == '']; claro = [r for (v, s), r in res.items() if s == '-l']
    err = sum(len(r['errores_consola']) for r in vals)
    L.append((err == 0, ('Sin errores de consola ni de JavaScript en %s, en modo oscuro y claro.' % ('la vista' if len(vistas) == 1 else 'las %d vistas' % len(vistas)))
              if err == 0 else 'Errores de consola: %d (%s).' % (err, '; '.join(sum((r['errores_consola'] for r in vals), [])[:2]))))
    anch = max(r['desborde']['ancho_max'] for r in vals); des = any(r['desborde']['alguno'] or r['desborde']['fuera'] for r in vals)
    ej = sum((r['desborde'].get('ejemplos') or [] for r in vals), [])[:3]
    L.append((not des, ('Sin desborde horizontal a 390 px: la página mide %d px de ancho.' % anch) if not des else 'Desborde horizontal: la página llega a %d px (fuera de marco: %s).' % (anch, '; '.join(ej) or 'ninguno medible')))
    tap = max(r['tactil']['menores_44'] for r in vals); tn = max(r['tactil']['elementos'] for r in vals)
    L.append((tap == 0, ('Zonas táctiles: 0 de %d bajo 44 px.' % tn) if tap == 0 else 'Zonas táctiles bajo 44 px: %d de %d (%s).' % (tap, tn, ', '.join(sum((r['tactil']['ejemplos'] for r in vals), [])[:2]))))
    co, cl = max(r['contraste']['pct_bajo_AA'] for r in oscuro), max(r['contraste']['pct_bajo_AA'] for r in claro); sf = max(r['contraste']['pct_sin_fondo'] for r in vals)
    L.append((co == 0 and cl == 0 and sf <= 3, 'Contraste AA: %s %% del texto bajo el mínimo en oscuro y %s %% en claro (texto sin fondo verificable: %s %%).' % (f1(co), f1(cl), f1(sf))))
    t14 = max(r['tipografia']['pct_lt14'] for r in vals); mn = min(r['tipografia']['fs_min'] for r in vals)
    L.append((mn >= 12 and t14 <= 20, 'Letra: mínimo %s px; en el peor estado, %s %% del texto bajo 14 px.' % (('%g' % mn).replace('.', ','), f1(t14))))
    pw = max(r['primera_pantalla_palabras'] for r in vals); tope = {'A': 170, 'B': 200, 'C': 170}   # el Tablero muestra una fila por frente: su mínimo natural es mayor
    L.append((all(r['primera_pantalla_palabras'] <= tope.get(v, 170) for (v, _s), r in res.items()), 'Primera pantalla: %d palabras como máximo (tope 170; 200 en el Tablero).' % pw))
    if pruebas is not None:
        ok = sum(1 for p in pruebas if p['ok'])
        L.append((ok == len(pruebas), 'Interacciones probadas toque a toque: %d de %d%s.' % (ok, len(pruebas), '' if ok == len(pruebas) else ' (fallan: ' + '; '.join(p['n'] for p in pruebas if not p['ok'])[:160] + ')')))
    if par is not None:
        L.append((par['pct'] >= 98.5, 'Contenido íntegro: %s %% de las palabras y cifras de la fuente están en el informe.' % f1(par['pct'])))
        L.append((not par['enlaces_mal'], ('Sin enlaces que revisar.' if not par['enlaces'] else '%d enlaces con formato válido (no se comprobó que respondan).' % par['enlaces']) if not par['enlaces_mal'] else 'Enlaces con formato dudoso: %s.' % ', '.join(par['enlaces_mal'][:2])))
        md = par.get('medios')
        if md and sum(md['esperados'].values()):
            e, p = md['esperados'], md['presentes']; compl = all(p[k] >= e[k] for k in e) and not md['huellas_faltan']
            L.append((compl, ('Audio y vídeo: %d de %d audios y %d de %d vídeos de la fuente están en el informe, con su mismo archivo.' % (e['audio'], e['audio'], e['video'], e['video'])) if compl else
                      'Audio y vídeo: faltan %d audios y %d vídeos de la fuente%s.' % (max(0, e['audio'] - p['audio']), max(0, e['video'] - p['video']), (' (archivos distintos: %d)' % len(md['huellas_faltan'])) if md['huellas_faltan'] else '')))
        rp = par.get('reproductores')
        if rp and rp['n']: L.append((not rp['mal'], ('Cada archivo de audio y vídeo se abre: %d de %d con duración medida.' % (rp['n'], rp['n'])) if not rp['mal'] else 'Audio o vídeo que no se abre: %s.' % ', '.join(rp['mal'][:3])))
        if md and md['no_incluidos']: L.append((False, '%d audio o vídeo no se incluyeron (pesan demasiado o no se encontraron): %s.' % (len(md['no_incluidos']), '; '.join(x[1] for x in md['no_incluidos'][:2]))))
        if md and md['imagenes_faltan']: L.append((False, '%d imágenes no se encontraron.' % md['imagenes_faltan']))
        ev = par.get('enlaces_video')
        if ev: L.append((all(x['ok'] for x in ev), ('%d de %d enlaces de vídeo responden (HTTP 200).' % (len(ev), len(ev))) if all(x['ok'] for x in ev) else 'Enlaces de vídeo que no responden: %s.' % '; '.join('%s (%s)' % (x['url'][:60], x['detalle']) for x in ev if not x['ok'])))
    js = res[(vistas[0], '')].get('js_apagado') or {}
    L.append((js.get('texto_visible', 0) > 400, 'Con JavaScript apagado se lee el contenido (%s caracteres visibles).' % js.get('texto_visible')))
    ext = par['externos'] if par else 0
    L.append((ext == 0 and kb < 46000, ('Archivo único de %s, sin recursos externos: abre sin conexión.' % (('%d KB' % kb) if kb < 1024 else ('%.1f MB' % (kb / 1024)).replace('.', ','))) if ext == 0 and kb < 46000 else ('El archivo depende de %d recursos externos.' % ext) if ext else 'El archivo pesa %.1f MB: demasiado para abrirlo cómodo en un celular.' % (kb / 1024)))
    return L

def sellar(src, destino, tema=None, vista=None, modo='una', base=None, estampar=True):
    sys.path.insert(0, str(AQUI)); import informe, paridad
    destino = pathlib.Path(destino).resolve()
    ok_, motivo = disponible()
    if not ok_:
        informe.generar(src, destino, tema, vista, modo, base)
        print('SIN MEDIR: %s. El HTML se generó, pero sin sello.' % motivo); return 3
    print('Chrome:', pathlib.Path(motivo).name, flush=True)
    def construir(): return informe.generar(src, destino, tema, vista, modo, base, silencioso=True)
    qa = pathlib.Path(tempfile.mkdtemp(prefix='informe_qa_'))
    sello = informe.ruta_sello(destino)
    try:
        if estampar and sello.exists(): sello.unlink()        # se mide el HTML sin sello previo
        g = construir(); h = destino
        vistas = sorted(set(re.findall(r'id="vista-([ABC])"', h.read_text(encoding='utf8')))) or ['A']
        par = paridad.verificar(h.read_text(encoding='utf8'), g['doc'], g['medios']); par['enlaces_video'] = ev = enlaces_video(h.read_text(encoding='utf8'))
        res, pruebas = medir(h, vistas, qa)
        L1 = lineas(res, pruebas, par, h.stat().st_size // 1024, vistas)
        if not estampar:
            malos = [t for ok, t in L1 if not ok] + ['prueba fallida: %s · %s' % (p['n'], p['extra'][:80]) for p in (pruebas or []) if not p['ok']]
            for t in malos: print('FALLA', t)
            det = {'%s%s' % k: v['contraste'].get('ejemplos') for k, v in res.items() if v['contraste'].get('ejemplos')}
            if det and malos: print('  contraste, ejemplos:', det)
            print('%d de %d comprobaciones pasan' % (sum(1 for ok, _ in L1 if ok), len(L1)))
            return 0 if not malos else 2
        hoy = datetime.date.today(); fecha = '%d-%d-%d' % (hoy.day, hoy.month, hoy.year)
        sello.write_text(json.dumps({'fecha': fecha, 'sha': g['sha'], 'lineas': L1}, ensure_ascii=False, indent=1), encoding='utf8')
        g2 = construir()
        res2, _ = medir(h, vistas, qa, con_pruebas=False)
        p2 = paridad.verificar(h.read_text(encoding='utf8'), g2['doc'], g2['medios']); p2['enlaces_video'] = ev
        L2 = lineas(res2, pruebas, p2, h.stat().st_size // 1024, vistas)
        estable = [a[0] for a in L1] == [b[0] for b in L2]
        sello.write_text(json.dumps({'fecha': fecha, 'sha': g['sha'], 'lineas': L2, 'estable': estable, 'faltan': par['faltan'], 'pruebas': pruebas,
                                     'vista': g['vista'], 'tema': informe.ruta_tema(tema).stem, 'version': informe.VERSION}, ensure_ascii=False, indent=1), encoding='utf8')
        construir()
    finally:
        shutil.rmtree(qa, ignore_errors=True)
    for ok, t in L2: print('PASS ' if ok else 'FALLA', t)
    todo = all(o for o, _ in L2) and estable
    print('estable tras el sello:', estable, '·', 'TODO EN ORDEN' if todo else 'HAY FALLOS')
    for p in pruebas or []: print('  ', 'PASS' if p['ok'] else 'FALLA', p['n'], ('· ' + p['extra']) if p['extra'] and not p['ok'] else '')
    if par['faltan'] and par['pct'] < 100: print('  palabras que faltan:', par['faltan'][:10])
    print('Sello:', sello.name, '· HTML:', destino.name)
    return 0 if todo else 2

if __name__ == '__main__':
    print(__doc__); sys.exit(2)
