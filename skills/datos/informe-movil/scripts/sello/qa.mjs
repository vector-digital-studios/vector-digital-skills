// qa.mjs <html> <carpeta_salida> [--hash=A|A-l] [--tabs=css] [--sin-capturas]
// Sonda determinista de un informe en móvil (390x844 @2x). Solo medición, sin visión.
// Salida: una línea JSON con consola, desborde, tipografía, zonas táctiles, contraste, largo y qué se ve con JavaScript apagado.
// Contraste: el fondo de cada texto es el color sólido más cercano; si hay degradado encima se exige un margen extra (+0,4)
// y si un degradado no tiene color sólido debajo, el texto cuenta como «sin fondo verificable» (el sello lo exige en 0).
import fs from 'fs'; import path from 'path';
import { puppeteer, exe, espera, urlDe, movil } from './comun.mjs';
const args = process.argv.slice(2); const file = args[0], out = args[1];
const opt = k => (args.find(a => a.startsWith('--' + k + '=')) || '').split('=').slice(1).join('=');
const tabsSel = opt('tabs') || '.bn button,.tile'; const sinCap = args.includes('--sin-capturas');
fs.mkdirSync(out, { recursive: true });
const url = urlDe(file, opt('hash')); const b = await puppeteer.launch({ executablePath: exe }); const errs = [];
const medir = () => {
  const lum = c => { const a = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * a[0] + .7152 * a[1] + .0722 * a[2]; };
  const parse = s => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; };
  const paradas = bi => [...bi.matchAll(/rgba?\([^)]+\)/g)].map(m => parse(m[0])).filter(Boolean);
  const fondo = el => {
    // {cand:[rgb,...], grad}: candidatos de fondo (gana el peor caso). null = no verificable (imagen sin color debajo).
    let e = el, grad = false; const pile = [];
    while (e) {
      const cs = getComputedStyle(e), c = parse(cs.backgroundColor), bi = cs.backgroundImage, g = bi && bi !== 'none' && /gradient|url/.test(bi);
      if (g && !(c && c[3] >= .99)) {
        const st = paradas(bi);
        if (!st.length) return null;
        if (st.every(x => x[3] >= .99)) return { cand: st.map(x => x.slice(0, 3)), grad: true };
        grad = true;
      } else if (g) grad = true;
      if (c && c[3] > 0) { pile.push(c); if (c[3] >= .99) break; }
      e = e.parentElement;
    }
    let base = [255, 255, 255]; for (let i = pile.length - 1; i >= 0; i--) { const c = pile[i]; base = [0, 1, 2].map(k => c[k] * c[3] + base[k] * (1 - c[3])); }
    return { cand: [base], grad };
  };
  const vis = el => { const r = el.getClientRects(); if (!r.length) return false; const cs = getComputedStyle(el); return cs.visibility !== 'hidden' && +cs.opacity > 0.05 && cs.display !== 'none'; };
  const fs = {}, sfe = {}; let chars = 0, bajo = 0, sinFondo = 0, charsContr = 0; const malContraste = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = walker.nextNode())) {
    const t = n.textContent.replace(/\s+/g, ' ').trim(); if (!t) continue; const el = n.parentElement;
    if (!el || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName) || !vis(el) || el.closest('svg')) continue;
    const cs = getComputedStyle(el); const px = Math.round(parseFloat(cs.fontSize) * 2) / 2; fs[px] = (fs[px] || 0) + t.length; chars += t.length;
    const clip = cs.webkitBackgroundClip === 'text' || cs.backgroundClip === 'text';
    const fg = parse(cs.color), bg = clip ? fondo(el.parentElement) : fondo(el);
    if (!fg || !bg) { sinFondo += t.length; const k = el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''); sfe[k] = (sfe[k] || 0) + t.length; continue; }
    let fgs = [fg]; if (clip) { const st = paradas(cs.backgroundImage); if (st.length) fgs = st; }
    let cr = 99;
    for (const f0 of fgs) for (const b0 of bg.cand) { const a = f0[3], f = [0, 1, 2].map(k => f0[k] * a + b0[k] * (1 - a)); const L1 = lum(f), L2 = lum(b0); cr = Math.min(cr, (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05)); }
    const grande = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700); charsContr += t.length;
    const lim = (grande ? 3 : 4.5) + (bg.grad ? .4 : 0);
    if (cr < lim) { bajo += t.length; if (malContraste.length < 5) malContraste.push(t.slice(0, 28) + ' ' + cr.toFixed(1) + (el.className ? ' .' + String(el.className).split(' ')[0] : '')); }
  }
  const sel = 'button,summary,[role=button],[role=tab],input,select,textarea,.nx,.op,a[href],audio[controls],video[controls]';
  let tap = 0, tapMal = 0; const malTap = [];
  document.querySelectorAll(sel).forEach(el => { if (!vis(el)) return; const cs = getComputedStyle(el); if (el.tagName === 'A' && cs.display === 'inline') return; const r = el.getBoundingClientRect(); tap++; const m = Math.min(r.width, r.height); if (m < 44) { tapMal++; if (malTap.length < 4) malTap.push(el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : '') + ' «' + (el.textContent || '').trim().slice(0, 16) + '» ' + Math.round(r.width) + 'x' + Math.round(r.height)); } });
  const de = document.documentElement;
  const fueraL = [...document.querySelectorAll('body *')].filter(e => { if (!vis(e) || e.closest('svg,pre,nav,[data-scroll-x],.rib,.bk,.abw,.rp')) return false; const r = e.getBoundingClientRect(); return r.right > innerWidth + 1 || r.left < -1; }); const fuera = fueraL.length;
  const fueraEj = fueraL.slice(0, 4).map(e => { const r = e.getBoundingClientRect(); return e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '') + ' ' + Math.round(r.left) + '→' + Math.round(r.right); });
  const pct = a => chars ? +(100 * a / chars).toFixed(1) : 0; const menor = lim => Object.entries(fs).filter(([k]) => +k < lim).reduce((a, [, v]) => a + v, 0);
  const primera = (() => { let w = 0; const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let x; while ((x = tw.nextNode())) { const el = x.parentElement; if (!el || !vis(el) || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName) || el.closest('svg')) continue; const r = el.getBoundingClientRect(); if (r.top < innerHeight && r.bottom > 0) w += x.textContent.trim().split(/\s+/).filter(Boolean).length; } return w; })();
  return { chars, pct_lt12: pct(menor(12)), pct_lt14: pct(menor(14)), fs_min: Math.min(...Object.keys(fs).map(Number)), contraste_malo_pct: charsContr ? +(100 * bajo / charsContr).toFixed(2) : 0, sin_fondo_pct: chars ? +(100 * sinFondo / chars).toFixed(2) : 0,
    contraste_ejemplos: malContraste, sf_ej: Object.entries(sfe).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k, v]) => k + ':' + v), tap, tap_lt44: tapMal, tap_ejemplos: malTap, ancho_pagina: de.scrollWidth, desborda: de.scrollWidth > 391 || de.scrollWidth > innerWidth + 1, fuera, fuera_ej: fueraEj, pantallas: +(de.scrollHeight / innerHeight).toFixed(1), palabras_primera: primera, nodos: document.querySelectorAll('*').length };
};
const p = await movil(b, url, { errs }); const base = await p.evaluate(medir);
if (!sinCap) { await p.screenshot({ path: path.join(out, 'p0_inicio.png') }); }
const disp = await p.$$eval(tabsSel, els => els.map((e, i) => { e.setAttribute('data-qa-i', i); return { i, t: (e.textContent || '').trim().slice(0, 18), vis: e.getClientRects().length > 0 }; }));
const estados = [{ estado: 'inicio', ...base }];
for (const d of disp.filter(x => x.vis).slice(0, 14)) {
  try { await p.evaluate(i => document.querySelector(`[data-qa-i="${i}"]`).click(), d.i); await espera(380); estados.push({ estado: d.t, ...(await p.evaluate(medir)) }); }
  catch (e) { errs.push('toque ' + d.t + ': ' + e.message); }
}
await p.evaluate(() => { document.querySelectorAll('details').forEach(d => d.open = true); document.querySelectorAll('.sheet.on .cierra').forEach(x => x.click()); }); await espera(350);
const abierto = await p.evaluate(medir); if (!sinCap) await p.screenshot({ path: path.join(out, 'p9_abierto.png'), fullPage: true });
const todos = [...estados, abierto]; const mx = k => Math.max(...todos.map(e => e[k] ?? 0));
const conJS = await p.evaluate(() => document.body.innerText.length); await p.close();
let sinJS = null;
try { const q = await movil(b, url, { js: false }); sinJS = await q.evaluate(() => { const vis = e => e.getClientRects().length > 0; let c = 0; document.querySelectorAll('body *').forEach(e => { if (e.children.length === 0 && vis(e) && !/^(SCRIPT|STYLE)$/.test(e.tagName)) c += (e.textContent || '').trim().length; }); return { texto_visible: c }; }); await q.close(); } catch (e) { sinJS = { error: String(e).slice(0, 80) }; }
await b.close();
console.log(JSON.stringify({
  archivo: path.basename(file), kb: Math.round(fs.statSync(file).size / 1024), estados: estados.length - 1, errores_consola: [...new Set(errs)].slice(0, 6),
  tipografia: { pct_lt12: mx('pct_lt12'), pct_lt14: mx('pct_lt14'), fs_min: Math.min(...todos.map(e => e.fs_min)) },
  tactil: { elementos: mx('tap'), menores_44: mx('tap_lt44'), ejemplos: todos.flatMap(e => e.tap_ejemplos).slice(0, 4) },
  contraste: { pct_bajo_AA: mx('contraste_malo_pct'), pct_sin_fondo: mx('sin_fondo_pct'), ejemplos: [...new Set(todos.flatMap(e => e.contraste_ejemplos))].slice(0, 5), sin_fondo_ejemplos: [...new Set(todos.flatMap(e => e.sf_ej))].slice(0, 6) },
  desborde: { alguno: todos.some(e => e.desborda), ancho_max: mx('ancho_pagina'), fuera: mx('fuera'), ejemplos: [...new Set(todos.flatMap(e => e.fuera_ej || []))].slice(0, 5) }, largo_pantallas: mx('pantallas'), primera_pantalla_palabras: base.palabras_primera, nodos: mx('nodos'), js_apagado: sinJS, texto_con_js: conJS,
}));
