// clicables.mjs <html> [ancho=390] [hash]
// Inventario de lo que se puede tocar (página y cada hoja) y de la señal visible que lo delata.
// ✓ = trae señal de acción: flecha/chevron/más/copiar en su icono, texto visible de acción (Ver, Abrir, Copiar…), radio, o botón-icono con nombre.
import { puppeteer, exe, espera, urlDe } from './comun.mjs';
const [file, ancho = '390', hash = ''] = process.argv.slice(2);
const w = Number(ancho);
const b = await puppeteer.launch({ executablePath: exe });
function inventario(soloHoja) {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const nom = e => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '');
  const R = soloHoja ? document.querySelector('#hoja') : document;
  const SEL = 'button, a[href], summary, [role=button], [role=tab], [data-sh], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  const c = new Set([...R.querySelectorAll(SEL)]);
  for (const e of R.querySelectorAll('*')) if (getComputedStyle(e).cursor === 'pointer') c.add(e);
  const out = [];
  for (const e of c) {
    if (!vis(e) || e.closest('[hidden]')) continue;
    if (!soloHoja && e.closest('#hoja')) continue;
    if (e.parentElement && c.has(e.parentElement) && e.tagName !== 'SUMMARY') continue;
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    const visible = (e.innerText || e.value || '').replace(/\s+/g, ' ').trim();
    const nombre = (visible || e.getAttribute('aria-label') || '').slice(0, 34);
    const usos = [...e.querySelectorAll('use')].map(u => u.getAttribute('href') || '').join(' ') + ' ';
    const sen = [];
    if (/#i-(chevron-[a-z]+|arrow-[a-z-]+|arrows-[a-z]+|external-link|player-play|plus|minus|copy|x)\s/.test(usos)) sen.push('icono-acción'); else if (e.querySelector('svg')) sen.push('icono-deco');
    if (/\b(ver|abrir|copiar|cerrar|siguiente|anterior|ocultar|plegar|elegir|ordenar|alternar|reproducir)\b/i.test(visible)) sen.push('texto-acción');
    if (e.matches('.op') && e.querySelector('.ck')) sen.push('radio');
    if (e.tagName === 'BUTTON' && !visible && e.getAttribute('aria-label') && sen.includes('icono-deco')) sen.push('botón-icono');
    out.push({ k: nom(e), t: nombre, w: Math.round(r.width), h: Math.round(r.height), s: sen, accion: sen.some(x => /icono-acción|texto-acción|radio|botón-icono/.test(x)), vacio: sen.length === 0 });
  }
  return out;
}
function huella() {
  const f = sel => { const e = document.querySelector(sel); if (!e || !e.getClientRects().length) return null; const s = getComputedStyle(e); return `${sel}: radio ${s.borderTopLeftRadius}, fondo ${s.backgroundColor.slice(0, 22)}${s.backgroundImage !== 'none' ? '+degradado' : ''}, sombra ${s.boxShadow === 'none' ? 'no' : 'sí'}, cursor ${s.cursor}, pie «${(e.querySelector('.go') || {}).innerText || '-'}»`; };
  return ['.tile', '.k', '.card', '.nt'].map(f).filter(Boolean);
}
const p = await b.newPage();
await p.setViewport({ width: w, height: w >= 700 ? 854 : 844, deviceScaleFactor: 1, isMobile: w < 700, hasTouch: w < 700 });
const cargar = async () => { await p.goto(urlDe(file, hash), { waitUntil: 'load' }); await espera(700); await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true)); await espera(250); };   // con todo desplegado: lo plegado también se toca
let sin = 0, total = 0;
const listar = (donde, lst) => {
  const g = new Map();
  for (const x of lst) { const key = `${x.k}|${x.s.join('+')}|${x.h}`; const e = g.get(key) || { ...x, n: 0, ej: [] }; e.n++; if (e.ej.length < 2) e.ej.push(x.t); g.set(key, e); }
  console.log(`-- ${donde}: ${lst.length} tocables`);
  for (const e of g.values()) { total += e.n; if (!e.accion) sin += e.n; console.log(`   ${e.accion ? '✓' : '✗'} ${String(e.n).padStart(2)}× ${e.k.padEnd(16)} ${String(e.w).padStart(4)}×${String(e.h).padEnd(3)} ${(e.s.join('+') || 'NINGUNA').padEnd(34)} «${e.ej.join('» «')}»`); }
};
await cargar();
console.log('== HUELLA: tarjetas que se tocan frente a las que no =='); (await p.evaluate(huella)).forEach(x => console.log('   ' + x));
console.log('\n== INVENTARIO a ' + w + ' px (✓ trae señal de acción · ✗ solo parece tarjeta) ==');
listar('página', await p.evaluate(inventario, false));
const nt = await p.evaluate(() => document.querySelectorAll('.tl .tile').length);
for (let i = 0; i < nt; i++) {
  await cargar(); await p.evaluate(x => document.querySelectorAll('.tl .tile')[x].click(), i); await espera(500);
  await p.evaluate(() => document.querySelectorAll('#hoja details').forEach(d => { d.open = true; })); await espera(200);
  const tit = await p.evaluate(() => ((document.querySelector('#hoja header h2') || {}).textContent || '').trim().slice(0, 26));
  listar(`hoja ${i + 1} «${tit}»`, await p.evaluate(inventario, true));
}
console.log(`\nTOTAL tocables ${total} | sin señal de acción ${sin}`);
await b.close();
