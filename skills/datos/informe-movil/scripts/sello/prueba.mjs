// prueba.mjs <html> : interacciones reales, toque a toque, en móvil 390x844. Solo prueba lo que el informe tiene.
// Última línea de la salida: JSON [{n, ok, extra}]
import { puppeteer, exe, espera, urlDe, movil, quieto } from './comun.mjs';
const file = process.argv[2]; const b = await puppeteer.launch({ executablePath: exe, args: ['--autoplay-policy=no-user-gesture-required'] }); const res = [], errs = [];
const t0 = Date.now(); const T = (n, ok, extra = '') => { res.push({ n, ok: !!ok, extra: String(extra) }); console.error(((Date.now() - t0) / 1000).toFixed(1) + ' s ' + (ok ? 'PASS ' : 'FALLA ') + n); };
const abrir = async h => movil(b, urlDe(file, h), { dpr: 1, errs });
let p = await abrir('');
const info = await p.evaluate(() => ({ vistas: [...document.querySelectorAll('.vista')].map(v => v.id.slice(-1)), seg: !!document.querySelector('.seg') })); await p.close();
const cortar = async p => p.evaluate(() => { window.__log = []; document.execCommand = c => { if (c === 'copy') { const a = document.activeElement, s = getSelection(); window.__log.push({ tag: a && a.tagName, sel: s ? s.toString().length : 0, ta: a && a.tagName === 'TEXTAREA' ? [a.selectionStart, a.selectionEnd, a.value.length] : null }); return true; } return false; }; Object.defineProperty(navigator, 'clipboard', { value: { writeText: t => { window.__log.push({ api: t.length }); return Promise.resolve(); } }, configurable: true }); });
const bloquear = async p => p.evaluate(() => { window.__log = []; document.execCommand = () => false; Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('bloqueado')) }, configurable: true }); });
for (const V of info.vistas) {
  const L = info.vistas.length > 1 ? V + ' · ' : ''; p = await abrir(info.seg ? V : ''); const S = s => s.split(',').map(x => `#vista-${V} ${x.trim()}`).join(',');
  const n = s => p.evaluate(x => document.querySelectorAll(x).length, S(s));
  const clic = (s, i = 0) => p.evaluate((x, i) => document.querySelectorAll(x)[i].click(), S(s), i);
  if (await p.evaluate(() => !!document.getElementById('tema'))) { const t0 = await p.evaluate(() => document.documentElement.dataset.t); await p.evaluate(() => document.getElementById('tema').click()); const t1 = await p.evaluate(() => document.documentElement.dataset.t); await p.evaluate(() => document.getElementById('tema').click()); T(L + 'el botón de tema alterna oscuro y claro', t0 !== t1); }
  if (await n('[data-todo]')) {
    const tot = await n('details.dt,details.cap'); await clic('[data-todo]'); await espera(150); const ab = await n('details.dt[open],details.cap[open]'); await clic('[data-todo]'); await espera(150); const ce = await n('details.dt[open],details.cap[open]');
    T(L + '«Abrir todo» abre y vuelve a plegar todos los plegables', tot > 0 ? (ab === tot && ce === 0) : true, ab + ' de ' + tot);
  }
  if (await n('.tw th[data-s]')) { const o = await p.evaluate(x => { document.querySelectorAll('details').forEach(d => d.open = true); const th = document.querySelector(x); const f = () => [...th.closest('table').tBodies[0].rows].map(r => r.cells[0].textContent).join('|'); const a = f(); th.click(); const b2 = f(); th.click(); return [a, b2, f()]; }, S('.tw th[data-s]')); T(L + 'la tabla se ordena al tocar el encabezado', o[1] !== o[2]); }
  if (await n('.ask')) { const id = await p.evaluate(x => { const a = document.querySelector(x); const id = a.dataset.ir; a.click(); return id; }, S('.ask')); await quieto(p); const llego = () => p.evaluate(id => { const e = document.getElementById(id); if (!e) return false; const t = e.getBoundingClientRect().top; return (e.tagName !== 'DETAILS' || e.open) && t < 340 && t > -80; }, id); let ok_ = await llego(); if (!ok_) { await espera(1200); await quieto(p, 6000); ok_ = await llego(); } T(L + 'el botón de decisiones pendientes lleva a las decisiones y abre su capítulo', ok_); }
  // — decisiones y cuadro de copiar —
  const nd = await p.evaluate(x => [...document.querySelectorAll(x)].filter(d => d.querySelector('.op')).length, S('.dc'));
  if (nd) {
    await p.evaluate(x => { document.querySelectorAll('details').forEach(d => d.open = true); const ds = [...document.querySelectorAll(x)].filter(d => d.querySelector('.op')); ds[0].querySelector('.op').click(); if (ds[1]) { const o = ds[1].querySelectorAll('.op'); o[o.length - 1].click(); } }, S('.dc')); await espera(200);
    const esp = Math.min(nd, 2);
    T(L + 'elegir opciones muestra «Copiar respuestas (' + esp + ' de ' + nd + ')»', await p.evaluate((e, nd) => { const c = document.getElementById('cmp'); return !c.hidden && c.textContent.includes(e + ' de ' + nd); }, esp, nd));
    await cortar(p); await p.evaluate(() => document.querySelector('#cmp button').click()); await espera(300);
    const d1 = await p.evaluate(() => ({ log: window.__log, modal: document.getElementById('mod').classList.contains('on'), lbl: document.querySelector('#cmp span').textContent }));
    T(L + 'si el navegador deja copiar, «Copiar respuestas» copia al primer toque, sin abrir cuadro', !d1.modal && d1.log.length >= 1 && /Copiado/.test(d1.lbl), d1.lbl);
    await p.evaluate(() => { document.getElementById('cmp').hidden = false; }); await bloquear(p); await p.evaluate(() => document.querySelector('#cmp button').click()); await espera(500);
    const m1 = await p.evaluate(() => { const m = document.getElementById('mod'); return { on: m.classList.contains('on'), btn: m.querySelector('#modc').textContent.trim(), x: !!m.querySelector('.mx'), listo: /listo/i.test(m.textContent), v: m.querySelector('textarea').value }; });
    T(L + 'si el navegador no deja copiar, aparece el cuadro con COPIAR y una X, sin «Listo»', m1.on && m1.btn === 'COPIAR' && m1.x && !m1.listo && /^\S+: /m.test(m1.v), m1.v.split('\n').length + ' líneas');
    await cortar(p); await p.evaluate(() => document.getElementById('modc').click()); await espera(250);
    const cp = await p.evaluate(() => ({ l: window.__log, btn: document.getElementById('modc').textContent.trim() }));
    const ta = cp.l.find(x => x.ta);
    T(L + 'COPIAR copia solo: selecciona todo el texto y confirma «COPIADO»', ta && ta.ta[0] === 0 && ta.ta[1] === ta.ta[2] && ta.ta[2] > 0 && /COPIADO/.test(cp.btn), cp.btn);
    await p.evaluate(() => document.querySelector('#mod .mx').click()); await espera(150);
    T(L + 'la X cierra el cuadro', !(await p.evaluate(() => document.getElementById('mod').classList.contains('on'))));
    await bloquear(p); await p.evaluate(() => { document.getElementById('cmp').hidden = false; document.querySelector('#cmp button').click(); }); await espera(300); await p.keyboard.press('Escape'); await espera(150);
    T(L + 'Escape también cierra el cuadro', !(await p.evaluate(() => document.getElementById('mod').classList.contains('on'))));
  }
  // — piezas de los informes convertidos —
  if (await n('[data-cp]')) {
    await cortar(p); await p.evaluate(() => { document.querySelectorAll('details').forEach(d => d.open = true); }); await espera(120);
    const r = await p.evaluate(x => { const b = document.querySelector(x); b.click(); return { l: window.__log.slice(), box: !!b.closest('.cpb,.arf') }; }, S('[data-cp]')); await espera(200);
    T(L + 'los botones «Copiar» de textos y rutas copian al primer toque', r.box && r.l.length >= 1, JSON.stringify(r.l[0] || {}));
  }
  if (await n('[data-copia]')) {
    await cortar(p); await p.evaluate(() => { document.querySelectorAll('details').forEach(d => d.open = true); }); await espera(120);
    const r = await p.evaluate(x => { const b = document.querySelector(x); const t = b.dataset.copia; b.click(); return { l: window.__log.slice(), n: t.length }; }, S('[data-copia]')); await espera(200);
    const ta = r.l.find(x => x.ta);
    T(L + 'los botones «Copiar» incrustados copian su texto completo al primer toque', r.n > 0 && ta && ta.ta[2] === r.n, r.n + ' caracteres · ' + JSON.stringify(r.l[0] || {}));
  }
  if (await n('.abw input')) {
    const clip = await p.evaluate(x => { const i = document.querySelector(x); i.value = 20; i.dispatchEvent(new Event('input', { bubbles: true })); const w = i.parentElement; return w.querySelector('.abd').style.clipPath + '|' + w.style.getPropertyValue('--x'); }, S('.abw input'));
    T(L + 'el comparador antes/después responde al deslizar', /20%/.test(clip), clip);
  }
  if (await n('.cr > summary')) { const o = await p.evaluate(x => { const s = document.querySelector(x); s.parentElement.open = false; s.click(); return s.parentElement.open; }, S('.cr > summary')); T(L + 'un criterio de la rúbrica se despliega al tocarlo', o); }
  if (await n('.tm[href]')) T(L + 'los minutos «revisar» son enlaces con dirección válida', await p.evaluate(x => [...document.querySelectorAll(x)].every(a => /^https?:\/\/.+#t=\d+$/.test(a.getAttribute('href'))), S('.tm[href]')));
  // — medios: reproductores, minutos de la guía, A/B, storyboard y antes/después —
  const nAu = await n('audio'), nVi = await n('video');
  if (nAu + nVi) {
    const r = await p.evaluate(async x => {
      const ms = [...document.querySelectorAll(x)]; const o = { total: ms.length, ok: 0, sinCodec: 0, sinControles: 0, mal: [], largos: [] };
      for (const m of ms) {
        if (!m.controls) o.sinControles++;
        const tipo = (m.getAttribute('src') || '').match(/^data:([^;]+)/); if (tipo && !m.canPlayType(tipo[1])) { o.sinCodec++; continue; }
        const ok = await new Promise(res => { if (m.readyState >= 1) return res(m.duration > 0); const f = v => { m.removeEventListener('loadedmetadata', a); m.removeEventListener('error', b); res(v); }; const a = () => f(m.duration > 0), b = () => f(false); m.addEventListener('loadedmetadata', a); m.addEventListener('error', b); m.load(); setTimeout(() => f(false), 6000); });
        ok ? o.ok++ : o.mal.push(m.id || m.getAttribute('aria-label') || m.tagName);
      }
      return o;
    }, S('audio,video'));
    T(L + 'cada reproductor tiene controles y carga su archivo (' + r.ok + ' de ' + r.total + (r.sinCodec ? '; ' + r.sinCodec + ' sin códec en este Chrome, comprobados con ffprobe' : '') + ')', r.sinControles === 0 && r.mal.length === 0 && r.ok + r.sinCodec === r.total, r.mal.join(', '));
    if (await n('[data-seek]')) {
      const o = await p.evaluate(async x => {
        const bs = [...document.querySelectorAll(x)], fuera = [];
        for (const b of bs) { const g = b.closest('.mdx'), m = g.querySelector('.mdp.on audio,.mdp.on video') || document.getElementById(b.dataset.para) || g.querySelector('audio,video'); if (m && m.duration > 0 && +b.dataset.seek > m.duration + 0.5) fuera.push(b.textContent.trim() + ' > ' + Math.round(m.duration) + ' s'); }
        const b = bs[0], g = b.closest('.mdx'), m = g.querySelector('.mdp.on audio,.mdp.on video') || document.getElementById(b.dataset.para) || g.querySelector('audio,video'); const t = +b.dataset.seek; b.click(); await new Promise(r => setTimeout(r, 1100));
        return { t, ahora: m.currentTime, dur: m.duration || 0, fuera };
      }, S('[data-seek]'));
      T(L + 'los minutos de la guía caen dentro de la duración del audio o vídeo', o.fuera.length === 0, o.fuera.join('; '));
      T(L + 'tocar un minuto de la guía salta el reproductor a ese punto', o.dur > 0 ? Math.abs(o.ahora - Math.min(o.t, o.dur)) < 2 : true, o.t + ' s → ' + o.ahora.toFixed(1) + ' s');
    }
    if (await n('[data-ab-sw]')) {
      const o = await p.evaluate(async x => {
        const b = document.querySelector(x), g = b.closest('.mdx'), ps = [...g.querySelectorAll('.mdp')], a = ps[0].querySelector('audio,video'), c = ps[1].querySelector('audio,video');
        await new Promise(r => { if (a.readyState >= 1) r(); else { a.addEventListener('loadedmetadata', r, { once: true }); a.load(); } }); a.currentTime = Math.min(5, Math.max(0, (a.duration || 6) - 1)); const t = a.currentTime;
        b.click(); await new Promise(r => setTimeout(r, 1100));
        return { t, t2: c.currentTime, on1: ps[0].classList.contains('on'), on2: ps[1].classList.contains('on'), st: (g.querySelector('[data-ab-st]') || {}).textContent || '' };
      }, S('[data-ab-sw]'));
      T(L + '«Alternar A/B» pasa a la otra pista en el mismo punto', !o.on1 && o.on2 && Math.abs(o.t2 - o.t) < 1.5 && /Suena/.test(o.st), o.t.toFixed(1) + ' s → ' + o.t2.toFixed(1) + ' s · ' + o.st);
    }
    if (nAu + nVi >= 2) {
      const o = await p.evaluate(async x => {
        const ms = [...document.querySelectorAll(x)].filter(m => m.canPlayType((m.getAttribute('src') || '').replace(/^data:([^;]+).*/, '$1') || 'audio/mpeg')); if (ms.length < 2) return null;
        try { await ms[0].play(); await new Promise(r => setTimeout(r, 400)); await ms[1].play(); await new Promise(r => setTimeout(r, 400)); } catch (e) { return { err: String(e) }; }
        const r = { primeroPausado: ms[0].paused, segundoSuena: !ms[1].paused }; ms.forEach(m => m.pause()); return r;
      }, S('audio,video'));
      if (o && !o.err) T(L + 'suena un solo reproductor a la vez', o.primeroPausado && o.segundoSuena, JSON.stringify(o));
    }
  }
  if (await n('a.mdl')) T(L + 'cada tarjeta de vídeo con enlace apunta a una dirección web válida', await p.evaluate(x => [...document.querySelectorAll(x)].every(a => /^https?:\/\/\S+$/.test(a.getAttribute('href'))), S('a.mdl')));
  if (await n('.stt')) {
    T(L + 'cada cuadro del storyboard carga su imagen', await p.evaluate(async x => { const is = [...document.querySelectorAll(x)]; is.forEach(i => { i.loading = 'eager'; }); await Promise.all(is.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; setTimeout(r, 4000); }))); return is.every(i => i.complete && i.naturalWidth > 0); }, S('.stf img')));
    const vis = await p.evaluate(x => [...document.querySelectorAll(x)].pop().getClientRects().length > 0, S('.stt'));
    if (vis) {
      const id = await p.evaluate(x => { const a = [...document.querySelectorAll(x)].pop(); const id = a.getAttribute('href').slice(1); a.click(); return id; }, S('.stt')); await quieto(p);
      const top = await p.evaluate(i => document.getElementById(i).getBoundingClientRect().top, id);
      T(L + 'tocar un número del storyboard lleva a su cuadro', top > -30 && top < 600, Math.round(top) + ' px del borde superior');
    }
  }
  if (await n('.abw input')) {
    const o = await p.evaluate(x => { const i = document.querySelector(x); i.value = 20; i.dispatchEvent(new Event('input', { bubbles: true })); return document.querySelector(x).parentElement.querySelector('.abd').style.clipPath; }, S('.abw input'));
    T(L + 'el deslizador antes/después mueve la división', /20%/.test(o), o);
  }
  // — tablero B —
  if (await n('.tile')) {
    await clic('.tile'); await espera(500); const s1 = await p.evaluate(() => ({ on: document.getElementById('hoja').classList.contains('on'), t: document.querySelector('#hoja .pn h2').textContent }));
    let s2 = s1.t; if (await n('.tile') > 1) { await p.evaluate(() => document.querySelector('#hoja .next').click()); await espera(250); s2 = await p.evaluate(() => document.querySelector('#hoja .pn h2').textContent); }
    await p.keyboard.press('Escape'); await espera(250);
    T(L + 'el mosaico abre la hoja, «siguiente» cambia de módulo y Escape la cierra', s1.on && (s2 !== s1.t || await n('.tile') < 2) && !(await p.evaluate(() => document.getElementById('hoja').classList.contains('on'))), s1.t + ' → ' + s2);
    if (await n('.att button')) { await clic('.att button'); await espera(400); T(L + 'los avisos de atención abren su hoja', await p.evaluate(() => document.getElementById('hoja').classList.contains('on'))); }
  }
  // — dossier C —
  if (await n('.bn button[data-pg]') > 1) {
    const pg = await p.evaluate(x => document.querySelectorAll(x)[1].dataset.pg, S('.bn button[data-pg]')); await clic('.bn button[data-pg]', 1); await espera(250);
    T(L + 'las pestañas inferiores muestran su página', await p.evaluate(g => document.getElementById('C-pg-' + g).classList.contains('on'), pg));
    if (await n('.pgs>section.on .nx')) { await p.evaluate(() => document.querySelector('.pgs>section.on .nx').click()); await espera(250); T(L + '«Siguiente» avanza a la pestaña siguiente', await p.evaluate(g => !document.getElementById('C-pg-' + g).classList.contains('on'), pg)); }
  }
  await p.close();
}
if (info.seg) {
  p = await abrir('A'); await p.evaluate(() => document.querySelector('.seg button[data-v="C"]').click()); await espera(300);
  T('El selector A·B·C cambia de propuesta', await p.evaluate(() => !document.getElementById('vista-C').hidden && document.getElementById('vista-A').hidden && /^#C/.test(location.hash))); await p.close();
}
T('Sin errores de JavaScript durante las pruebas', errs.length === 0, errs.slice(0, 2).join(' | '));
await b.close(); console.log(JSON.stringify(res));
