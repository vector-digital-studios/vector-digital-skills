// desborde3.mjs <html> [hash] : localiza por eliminación el elemento que ensancha el documento (todo desplegado)
import { puppeteer, exe, espera, urlDe, movil } from './comun.mjs';
const [file, hash = ''] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe }); const p = await movil(b, urlDe(file, hash), { dpr: 1 });
await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true)); await espera(600);
const r = await p.evaluate(() => {
  const W = 390, de = document.documentElement, nom = e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ').slice(0, 2).join('.') : '') + (e.id ? '#' + e.id : '');
  const ancho = () => de.scrollWidth; const base = ancho(); if (base <= W + 1) return { base, culpable: null };
  const camino = []; let nodo = document.body;
  for (let prof = 0; prof < 14; prof++) {
    let hallado = null;
    for (const h of [...nodo.children]) {
      const prev = h.style.display; h.style.display = 'none'; const a = ancho(); h.style.display = prev;
      if (a < base) { hallado = { h, a }; break; }
    }
    if (!hallado) break; camino.push(nom(hallado.h) + ' → ' + hallado.a); nodo = hallado.h;
  }
  const cs = getComputedStyle(nodo), r = nodo.getBoundingClientRect();
  return { base, camino, final: nom(nodo), caja: [Math.round(r.left), Math.round(r.right)], scrollW: nodo.scrollWidth, clientW: nodo.clientWidth, overflowX: cs.overflowX, ws: cs.whiteSpace, texto: (nodo.textContent || '').trim().slice(0, 90), html: nodo.outerHTML.slice(0, 320) };
});
console.log(JSON.stringify(r, null, 1)); await b.close();
