// foto.mjs <html> <ancho> <alto> <accion> <png> [hash] [dpr]   accion: - | tile:N | tile:texto | scroll:Y | hoja:texto:Y (abre la hoja y desplaza SU contenido Y px)
import { puppeteer, exe, espera, urlDe } from './comun.mjs';
const [file, w, h, accion = '-', png, hash = '', dpr = '2'] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe });
const p = await b.newPage();
await p.setViewport({ width: +w, height: +h, deviceScaleFactor: +dpr, isMobile: +w < 700, hasTouch: +w < 700 });
await p.goto(urlDe(file, hash), { waitUntil: 'load' }); await espera(800);
if (accion.startsWith('tile:')) {
  const a = accion.slice(5);
  await p.evaluate(a => { const t = [...document.querySelectorAll('.tl .tile')]; const k = /^\d+$/.test(a) ? +a : t.findIndex(x => x.textContent.includes(a)); (t[k] || t[0]).click(); }, a);
  await espera(650);
}
if (accion.startsWith('hoja:')) {
  const [, a, y] = accion.split(':');
  await p.evaluate(a => { const t = [...document.querySelectorAll('.tl .tile')]; const k = /^\d+$/.test(a) ? +a : t.findIndex(x => x.textContent.includes(a)); (t[k] || t[0]).click(); }, a);
  await espera(650);
  await p.evaluate(y => { const c = [...document.querySelectorAll('#hoja *')].find(e => /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 4); if (c) c.scrollTop = y; }, +y);
  await espera(350);
}
if (accion.startsWith('scroll:')) { await p.evaluate(y => window.scrollTo(0, y), +accion.slice(7)); await espera(300); }
await p.screenshot({ path: png, fullPage: accion === 'full' });
await b.close();
