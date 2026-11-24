// tap.mjs <html> [hash] : zonas táctiles menores de 44 px (todo desplegado y tras tocar cada pestaña), con etiqueta, clase, tamaño y contexto
import { puppeteer, exe, espera, urlDe, movil } from './comun.mjs';
const [file, hash = ''] = process.argv.slice(2);
const b = await puppeteer.launch({ executablePath: exe }); const p = await movil(b, urlDe(file, hash), { dpr: 1 });
const medir = () => p.evaluate(() => {
  const sel = 'button,summary,[role=button],[role=tab],input,select,textarea,.nx,.op,a[href]', out = [];
  document.querySelectorAll(sel).forEach(el => {
    if (!el.getClientRects().length) return; const cs = getComputedStyle(el); if (el.tagName === 'A' && cs.display === 'inline') return;
    const r = el.getBoundingClientRect(); if (Math.min(r.width, r.height) >= 44) return;
    const pa = []; for (let a = el.parentElement; a && pa.length < 3; a = a.parentElement) pa.push(a.tagName.toLowerCase() + (typeof a.className === 'string' && a.className ? '.' + a.className.split(' ')[0] : ''));
    out.push({ el: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ').slice(0, 2).join('.') : '') + ' display=' + cs.display, w: Math.round(r.width), h: Math.round(r.height), t: (el.textContent || '').trim().slice(0, 40), en: pa.join(' < '), html: el.outerHTML.slice(0, 200) });
  });
  return out;
});
await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true)); await espera(400);
console.log(JSON.stringify(await medir(), null, 1));
const tabs = await p.$$('.bn button, .tile'); for (let i = 0; i < Math.min(tabs.length, 12); i++) { await p.evaluate(k => document.querySelectorAll('.bn button, .tile')[k].click(), i); await espera(350); const m = await medir(); if (m.length) console.log('estado', i, JSON.stringify(m)); }
await b.close();
