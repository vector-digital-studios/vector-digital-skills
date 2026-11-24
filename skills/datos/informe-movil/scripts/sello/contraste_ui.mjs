// contraste_ui.mjs <html> : contraste (WCAG) de bordes de controles y de la píldora «n de N» en la hoja de decisión, en oscuro y claro
import { puppeteer, exe, espera, urlDe } from './comun.mjs';
const [file, k = '5'] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe });
for (const [nom, hash] of [['OSCURO', 'B'], ['CLARO', 'B-l']]) {
  const p = await b.newPage(); await p.setViewport({ width: 390, height: 1500, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  await p.goto(urlDe(file, hash), { waitUntil: 'load' }); await espera(700);
  await p.evaluate(x => document.querySelectorAll('.tl .tile')[x].click(), +k); await espera(500);
  const r = await p.evaluate(() => {
    const rgb = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
    const lum = c => { const f = x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }; return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
    const cr = (a, c) => { const A = lum(a), B = lum(c); return (Math.max(A, B) + .05) / (Math.min(A, B) + .05); };
    const fondo = e => { for (let x = e; x; x = x.parentElement) { const c = rgb(getComputedStyle(x).backgroundColor); if (c && c.a > .95) return c; } return { r: 255, g: 255, b: 255, a: 1 }; };
    const fila = (nom, e, prop) => { if (!e) return `${nom}: no encontrado`; const cs = getComputedStyle(e), c = rgb(cs[prop]); const bg = fondo(e.parentElement || e); if (!c) return `${nom}: sin color`; return `${nom}: ${cs[prop]} sobre rgb(${bg.r},${bg.g},${bg.b}) = ${cr(c, bg).toFixed(2)}:1`; };
    const S = document.querySelector('#hoja .shb:not([hidden])') || document;
    const pos = document.querySelector('#hoja .pos'); const pc = pos && rgb(getComputedStyle(pos).color), pbg = pos && fondo(pos);
    return [
      fila('borde de opción', S.querySelector('.op:not(.sel)'), 'borderTopColor'),
      fila('círculo de opción', S.querySelector('.op .ck'), 'borderTopColor'),
      fila('borde «Cerrar»', document.querySelector('#hoja .cierra'), 'borderTopColor'),
      fila('borde Anterior', document.querySelector('#hoja .prev'), 'borderTopColor'),
      fila('borde Siguiente', document.querySelector('#hoja .next'), 'borderTopColor'),
      pos ? `píldora «n de N»: texto ${cr(pc, pbg).toFixed(2)}:1 sobre su fondo` : 'píldora: no encontrada',
      'meta viewport: ' + (document.querySelector('meta[name=viewport]') || {}).content,
      'gap entre opciones: ' + getComputedStyle(S.querySelector('.ops') || document.body).rowGap,
    ]; });
  console.log(`== ${nom} ==\n  ` + r.join('\n  ')); await p.close();
}
await b.close();
