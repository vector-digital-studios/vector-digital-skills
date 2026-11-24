// aire.mjs <html> [anchos=390,1280] [hash] [json_salida]
// Auditoría de espaciado en todos los estados (página, pestañas, cada hoja cerrada y con todo desplegado):
//   (1) tarjetas pegadas: dos superficies apiladas a menos de 12 px
//   (2) relleno interno: contenido a menos de 12 px del borde de su tarjeta
//   (3) filas de lista a menos de 6 px entre sí
import fs from 'fs';
import { puppeteer, exe, espera, urlDe } from './comun.mjs';
const [file, anchos = '390,1280', hash = '', salida = ''] = process.argv.slice(2);
const K = { entre: 12, relleno: 12, fila: 8 };

function auditar(raiz, k) {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const R = raiz ? document.querySelector(raiz) : document.body;
  if (!R) return null;
  const nom = e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  const superficie = e => {
    const s = getComputedStyle(e), bg = s.backgroundColor;
    const fondo = bg && !/^rgba\(\d+, \d+, \d+, 0\)$|^transparent$/.test(bg);
    const lados = ['Top', 'Right', 'Bottom', 'Left'].filter(x => parseFloat(s['border' + x + 'Width']) > 0 && s['border' + x + 'Style'] !== 'none' && !/^rgba\(\d+, \d+, \d+, 0\)$|^transparent$/.test(s['border' + x + 'Color'])).length;
    return fondo || lados >= 3 || (s.boxShadow && s.boxShadow !== 'none');
  };
  const oculto = e => { const d = e.closest('details:not([open])'); return !!d && e !== d && !e.closest('summary'); };   // lo que hay dentro de un plegable cerrado no está a la vista
  const todos = [...R.querySelectorAll('*')].filter(e => !e.closest('svg') && vis(e) && !oculto(e));
  const sup = todos.filter(e => { const r = e.getBoundingClientRect(); return r.height >= 34 && r.width >= 110 && superficie(e) && !e.closest('.bn, .tb, .bk') && !e.matches('.pn, .sheet, th, td, tr, thead, tbody, table, code, kbd'); });
  const rc = sup.map(e => ({ e, r: e.getBoundingClientRect() })).sort((a, b) => a.r.top - b.r.top);
  const pares = [], seen = new Set();
  for (let i = 0; i < rc.length; i++) for (let j = i + 1; j < rc.length; j++) {
    const A = rc[i], B = rc[j];
    if (B.r.top - A.r.bottom > k.entre + 40) break;
    if (A.e.contains(B.e) || B.e.contains(A.e)) continue;
    const gap = Math.round(B.r.top - A.r.bottom);
    if (gap < -1 || gap >= k.entre) continue;
    const ox = Math.min(A.r.right, B.r.right) - Math.max(A.r.left, B.r.left);
    if (ox < 0.4 * Math.min(A.r.width, B.r.width)) continue;
    const id = nom(A.e) + '>' + nom(B.e) + gap; if (seen.has(id)) continue; seen.add(id);
    pares.push({ a: nom(A.e), b: nom(B.e), gap, y: Math.round(A.r.bottom + scrollY) });
  }
  const contenido = e => {
    const rs = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (!n.nodeValue.trim()) continue; const p = n.parentElement; if (!p || !vis(p)) continue; const g = document.createRange(); g.selectNodeContents(n); for (const r of g.getClientRects()) if (r.width > 0 && r.height > 0) rs.push(r); }
    for (const g of e.querySelectorAll('svg, img, canvas')) if (vis(g)) rs.push(g.getBoundingClientRect());
    return rs;
  };
  const relleno = [], vistos = new Set();
  for (const { e, r } of rc) {
    if (r.height < 40 || r.width < 140 || (e.tagName === 'BUTTON' && r.height < 80) || e.tagName === 'NAV' || e.matches('.mdl')) continue;   // el cartel de un vídeo es una imagen a sangre por diseño
    const rs = contenido(e); if (!rs.length) continue;
    const L = Math.min(...rs.map(x => x.left)) - r.left, Rr = r.right - Math.max(...rs.map(x => x.right)), T = Math.min(...rs.map(x => x.top)) - r.top, B = r.bottom - Math.max(...rs.map(x => x.bottom));
    const m = Math.round(Math.min(L, Rr, T, B));
    if (m < -2 || m >= k.relleno) continue;
    const id = nom(e) + m; if (vistos.has(id)) continue; vistos.add(id);
    relleno.push({ el: nom(e), min: m, L: Math.round(L), R: Math.round(Rr), T: Math.round(T), B: Math.round(B) });
  }
  const filas = [];
  for (const ul of R.querySelectorAll('ul, ol')) {
    if (!vis(ul)) continue;
    const li = [...ul.children].filter(x => x.tagName === 'LI' && vis(x) && !superficie(x));
    for (let i = 0; i + 1 < li.length; i++) { const g = Math.round(li[i + 1].getBoundingClientRect().top - (li[i].getBoundingClientRect().bottom - parseFloat(getComputedStyle(li[i]).paddingBottom || 0))); if (g < k.fila) { filas.push({ ul: nom(ul), gap: g }); break; } }
  }
  return { superficies: sup.length, pares, relleno, filas };
}

const b = await puppeteer.launch({ executablePath: exe });
const todo = [];
let nPares = 0, nRel = 0, nFilas = 0;
const mostrar = (w, donde, r) => {
  if (!r) { console.log(`${String(w).padStart(4)}px | ${donde.padEnd(26)} | (sin contenedor)`); return; }
  nPares += r.pares.length; nRel += r.relleno.length; nFilas += r.filas.length;
  todo.push({ ancho: w, donde, ...r });
  const ej = [...r.pares.slice(0, 3).map(p => `${p.a}→${p.b} ${p.gap}px`), ...r.relleno.slice(0, 2).map(p => `${p.el} relleno ${p.min}px`), ...r.filas.slice(0, 1).map(p => `${p.ul} filas ${p.gap}px`)];
  console.log(`${String(w).padStart(4)}px | ${donde.padEnd(26)} | sup ${String(r.superficies).padStart(3)} | pegadas ${String(r.pares.length).padStart(2)} | relleno ${String(r.relleno.length).padStart(2)} | filas ${r.filas.length}${ej.length ? ' | ' + ej.join('; ') : ''}`);
};
for (const w of anchos.split(',').map(Number)) {
  const p = await b.newPage();
  await p.setViewport({ width: w, height: w >= 700 ? 854 : 844, deviceScaleFactor: 1, isMobile: w < 700, hasTouch: w < 700 });
  const aplanar = () => p.evaluate(() => { const pn = document.querySelector('#hoja .pn'), bd = document.querySelector('#hoja .bd'); if (pn && bd) { pn.style.cssText += ';position:relative;top:auto;bottom:auto;height:auto;display:block'; bd.style.cssText += ';overflow:visible;flex:none'; } });
  const abrir = raiz => p.evaluate(r => (document.querySelector(r) || document).querySelectorAll('details').forEach(d => { d.open = true; }), raiz);
  const cargar = async () => { await p.goto(urlDe(file, hash), { waitUntil: 'load' }); await espera(700); };
  await cargar();
  mostrar(w, 'página', await p.evaluate(auditar, null, K));
  await abrir('body'); await espera(300);
  mostrar(w, 'página (todo abierto)', await p.evaluate(auditar, null, K));
  const nav = await p.evaluate(() => document.querySelectorAll('.bn button').length);
  for (let i = 0; i < nav; i++) {
    await cargar(); await p.evaluate(x => document.querySelectorAll('.bn button')[x].click(), i); await espera(350); await abrir('body'); await espera(250);
    mostrar(w, 'pestaña ' + (i + 1), await p.evaluate(auditar, null, K));
  }
  const nt = await p.evaluate(() => document.querySelectorAll('.tl .tile').length);
  for (let i = 0; i < nt; i++) {
    await cargar(); await p.evaluate(x => document.querySelectorAll('.tl .tile')[x].click(), i); await espera(550); await aplanar();
    const tit = await p.evaluate(() => ((document.querySelector('#hoja header h2') || {}).textContent || '').trim().slice(0, 18));
    mostrar(w, `hoja ${i + 1} ${tit}`, await p.evaluate(auditar, '#hoja', K));
    await abrir('#hoja'); await espera(250);
    mostrar(w, `hoja ${i + 1} abierta`, await p.evaluate(auditar, '#hoja', K));
  }
  await p.close();
}
await b.close();
console.log(`TOTAL | tarjetas pegadas (<${K.entre}px): ${nPares} | relleno corto (<${K.relleno}px): ${nRel} | filas pegadas (<${K.fila}px): ${nFilas}`);
if (salida) fs.writeFileSync(salida, JSON.stringify(todo, null, 1));
