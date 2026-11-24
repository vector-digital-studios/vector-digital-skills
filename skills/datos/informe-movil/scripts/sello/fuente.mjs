// fuente.mjs <html> [hash] : ¿Sora cubre de verdad mayúsculas, minúsculas y acentos (400 y 700)? ¿algún texto cae en otra fuente?
import { puppeteer, exe, espera, urlDe, movil } from './comun.mjs';
const [file, hash = ''] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe }); const p = await movil(b, urlDe(file, hash), { dpr: 1 });
await p.evaluate(async () => { await Promise.all([400, 600, 700].map(w => document.fonts.load(w + ' 16px Sora').catch(() => 0))); await document.fonts.ready; }); await espera(300);
const r = await p.evaluate(() => {
  const ctx = document.createElement('canvas').getContext('2d'); const W = (t, f) => { ctx.font = f; return ctx.measureText(t).width; };
  // un glifo sale de Sora si su ancho no cambia al variar el respaldo (monospace / serif)
  const cubre = (peso, letras) => [...letras].filter(c => Math.abs(W(c, peso + ' 40px Sora, monospace') - W(c, peso + ' 40px Sora, serif')) > 0.01).map(c => c);
  const MAY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', MIN = 'abcdefghijklmnopqrstuvwxyz', ACC = 'ÁÉÍÓÚÑáéíóúñü¿¡';
  const sinCubrir = (peso, letras) => letras.length - [...letras].filter(c => Math.abs(W(c, peso + ' 40px Sora, monospace') - W(c, peso + ' 40px Sora, serif')) < 0.01).length;
  const falta = (peso, letras) => [...letras].filter(c => Math.abs(W(c, peso + ' 40px Sora, monospace') - W(c, peso + ' 40px Sora, serif')) >= 0.01).join('');
  const out = { caras: [...document.fonts].map(f => f.family.replace(/"/g, '') + ' ' + f.weight + ' ' + f.status) };
  for (const w of [400, 700]) out['peso' + w] = { mayusculas_sin_cubrir: falta(w, MAY), minusculas_sin_cubrir: falta(w, MIN), acentos_sin_cubrir: falta(w, ACC) };
  const raros = {}, ej = {};
  document.querySelectorAll('body *').forEach(e => { if (!e.getClientRects().length) return; if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return; const f = getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim(); if (f !== 'Sora') { const cls = x => x.tagName.toLowerCase() + (typeof x.className === 'string' && x.className ? '.' + x.className.split(' ')[0] : ''); const cad = []; for (let q = e, i = 0; q && q !== document.body && i < 4; q = q.parentElement, i++) cad.push(cls(q)); const k = cad.join(' < ') + ' → ' + f; raros[k] = (raros[k] || 0) + 1; if (!ej[k]) ej[k] = (e.textContent || '').trim().slice(0, 40); } });
  out.textos_en_otra_fuente = raros; out.ejemplos = ej; return out;
});
console.log(JSON.stringify(r)); await b.close();
