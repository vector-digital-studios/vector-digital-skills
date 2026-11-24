#!/usr/bin/env node
/**
 * grabar.js — graba una demo de interfaz web siguiendo un guion JSON.
 *
 * Lanza Chrome/Chromium en modo headless, se conecta por Chrome DevTools Protocol (CDP) con el
 * WebSocket nativo de Node >= 22 (sin dependencias npm), ejecuta los pasos del guion con un puntero
 * de movimiento humano y captura el screencast real del navegador.
 *
 * Uso:
 *   node scripts/grabar.js <guion.json> [--out <carpeta>] [--chrome <ruta>] [--headful]
 *
 * Chrome se busca en: --chrome, variable CHROME_PATH, y rutas habituales de Windows/macOS/Linux.
 * Las credenciales NUNCA van en el guion: se escriben como "$ENV:NOMBRE" y se leen del entorno.
 *
 * Salida: <out>/frames-<segmento>/f00000.jpg … + frames.json ([{i,x,y,t}]) + eventos.json
 *         ([{t,tipo}] con los clics y escrituras; el montador los usa para el zoom automático).
 * Ver references/guion.md para la lista completa de pasos.
 */
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');

if (typeof WebSocket === 'undefined') {
  console.error('ERROR: se necesita Node 22 o superior (WebSocket global).');
  process.exit(2);
}

// ---------- argumentos ----------
const argv = process.argv.slice(2);
function opt(name, def) { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : def; }
if (argv.includes('--donde-chrome')) { const c = buscarChrome(); console.log(c || ''); process.exit(c ? 0 : 1); }
const guionPath = argv.find(a => !a.startsWith('--') && argv[argv.indexOf(a) - 1] !== '--out' && argv[argv.indexOf(a) - 1] !== '--chrome');
if (!guionPath) { console.error('Uso: node grabar.js <guion.json> [--out dir] [--chrome ruta] [--headful]'); process.exit(2); }
const guion = JSON.parse(fs.readFileSync(guionPath, 'utf8'));
const guionDir = path.dirname(path.resolve(guionPath));
const OUT = path.resolve(opt('--out', guion.out ? path.resolve(guionDir, guion.out) : 'salida-demo'));
const VW = (guion.viewport && guion.viewport.w) || 1600;
const VH = (guion.viewport && guion.viewport.h) || 900;
let ORDEN_INICIADO = false; // la primera escritura reinicia segmentos.json
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const envVal = (v) => (typeof v === 'string' && v.startsWith('$ENV:')) ? (process.env[v.slice(5)] || '') : v;

// ---------- localizar Chrome ----------
function buscarChrome() {
  const cand = [opt('--chrome'), process.env.CHROME_PATH];
  if (process.platform === 'win32') {
    const pf = [process.env['PROGRAMFILES'], process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
    for (const b of pf) {
      cand.push(path.join(b, 'Google/Chrome/Application/chrome.exe'));
      cand.push(path.join(b, 'Chromium/Application/chrome.exe'));
      cand.push(path.join(b, 'Microsoft/Edge/Application/msedge.exe'));
    }
  } else if (process.platform === 'darwin') {
    cand.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Chromium.app/Contents/MacOS/Chromium');
  } else {
    for (const n of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
      for (const d of (process.env.PATH || '').split(':')) cand.push(path.join(d, n));
    }
  }
  return cand.find(c => c && fs.existsSync(c));
}

// ---------- pestaña CDP ----------
class Tab {
  constructor(wsUrl, dir, nombre) {
    this.wsUrl = wsUrl; this.dir = dir; this.nombre = nombre;
    this.idc = 0; this.pending = new Map(); this.fi = 0; this.log = []; this.eventos = [];
    this.capturando = false; this.mouse = { x: VW / 2, y: VH / 2 }; this.t0 = Date.now();
  }
  prepararCarpeta() {
    fs.mkdirSync(this.dir, { recursive: true });
    for (const f of fs.readdirSync(this.dir)) if (/\.(jpg|json)$/.test(f)) fs.unlinkSync(path.join(this.dir, f));
  }
  send(method, params = {}) {
    return new Promise((res, rej) => {
      const id = ++this.idc; this.pending.set(id, { res, rej });
      this.sock.send(JSON.stringify({ id, method, params }));
    });
  }
  connect() {
    return new Promise((res, rej) => {
      this.sock = new WebSocket(this.wsUrl);
      this.sock.onopen = () => res();
      this.sock.onerror = () => rej(new Error('no se pudo abrir el WebSocket ' + this.wsUrl));
      this.sock.onmessage = (e) => {
        let m; try { m = JSON.parse(typeof e.data === 'string' ? e.data : e.data.toString()); } catch { return; }
        if (m.id && this.pending.has(m.id)) {
          const p = this.pending.get(m.id); this.pending.delete(m.id);
          m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); return;
        }
        if (m.method === 'Page.screencastFrame') {
          const d = m.params;
          if (this.capturando && d && d.data) {
            fs.writeFileSync(path.join(this.dir, `f${String(this.fi).padStart(5, '0')}.jpg`), Buffer.from(d.data, 'base64'));
            this.log.push({ i: this.fi, x: Math.round(this.mouse.x), y: Math.round(this.mouse.y), t: Date.now() - this.t0 });
            this.fi++;
          }
          this.sock.send(JSON.stringify({ id: ++this.idc, method: 'Page.screencastFrameAck', params: { sessionId: d.sessionId } }));
        }
      };
    });
  }
  async init() {
    await this.send('Page.enable'); await this.send('Runtime.enable');
    await this.send('Emulation.setDeviceMetricsOverride', { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });
    // "Latido" de 1 px casi invisible: fuerza repintados continuos para que el screencast emita frames
    // aunque la página esté quieta (si no, el recorrido del puntero sobre una página estática se pierde).
    const latido = `(() => { if (window.__latido) return; window.__latido = 1;
      const add = () => { const d = document.createElement('div');
        d.style.cssText = 'position:fixed;left:0;bottom:0;width:1px;height:1px;z-index:2147483647;pointer-events:none;background:#000;opacity:.01';
        document.documentElement.appendChild(d); let k = 0;
        (function tick(){ d.style.opacity = (k++ % 2) ? '.01' : '.02'; requestAnimationFrame(tick); })(); };
      if (document.documentElement) add(); else addEventListener('DOMContentLoaded', add); })()`;
    await this.send('Page.addScriptToEvaluateOnNewDocument', { source: latido });
    try { await this.evaluate(latido); } catch (_) {}
  }
  async evaluate(expr) {
    const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    return r && r.result ? r.result.value : undefined;
  }
  async mv(x, y) { this.mouse = { x, y }; await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.round(x), y: Math.round(y) }); }
  marca(tipo) { this.eventos.push({ t: Date.now() - this.t0, tipo }); }
  async empezar() {
    this.prepararCarpeta(); this.fi = 0; this.log = []; this.eventos = []; this.t0 = Date.now();
    await this.send('Page.startScreencast', { format: 'jpeg', quality: 86, maxWidth: VW, maxHeight: VH, everyNthFrame: 1 });
    this.capturando = true;
  }
  async parar() {
    if (!this.capturando) return;
    // Cierre: duplica el último frame con el tiempo actual para conservar la pausa final.
    const ult = path.join(this.dir, `f${String(this.fi - 1).padStart(5, '0')}.jpg`);
    if (this.fi > 0 && fs.existsSync(ult)) {
      fs.copyFileSync(ult, path.join(this.dir, `f${String(this.fi).padStart(5, '0')}.jpg`));
      this.log.push({ i: this.fi, x: Math.round(this.mouse.x), y: Math.round(this.mouse.y), t: Date.now() - this.t0 });
      this.fi++;
    }
    this.capturando = false;
    try { await this.send('Page.stopScreencast'); } catch (_) {}
    fs.writeFileSync(path.join(this.dir, 'frames.json'), JSON.stringify(this.log));
    fs.writeFileSync(path.join(this.dir, 'eventos.json'), JSON.stringify(this.eventos));
    const orden = path.join(OUT, 'segmentos.json'); // orden de montaje
    const lista = fs.existsSync(orden) && ORDEN_INICIADO ? JSON.parse(fs.readFileSync(orden, 'utf8')) : [];
    ORDEN_INICIADO = true;
    if (!lista.includes(this.nombre)) lista.push(this.nombre);
    fs.writeFileSync(orden, JSON.stringify(lista));
    const recorrido = this.log.reduce((s, e, k) => k ? s + Math.hypot(e.x - this.log[k - 1].x, e.y - this.log[k - 1].y) : 0, 0);
    console.log(`segmento ${this.nombre}: ${this.log.length} frames, ${(this.log.length ? this.log[this.log.length - 1].t / 1000 : 0).toFixed(1)} s, recorrido del puntero ${Math.round(recorrido)} px`);
  }
  async resolve(target) {
    if (target && typeof target === 'object' && target.x !== undefined) return { x: target.x, y: target.y };
    const q = (s) => JSON.stringify(String(s));
    let js;
    if (typeof target === 'string') {
      js = `document.querySelector(${q(target.startsWith('css:') ? target.slice(4) : target)})`;
    } else if (target && target.text) {
      js = `[...document.querySelectorAll('button,a,[role=tab],[role=button],input,label,[class*=btn]')].find(e=>(e.innerText||e.value||'').trim()===${q(target.text)})`;
    } else if (target && target.contains) {
      // el elemento MÁS PEQUEÑO que contiene el texto (no su contenedor)
      js = `[...document.querySelectorAll('button,a,[role=tab],h1,h2,h3,h4,li,td,tr,span,p,[class*=title],[class*=card]')].filter(e=>(e.innerText||'').includes(${q(target.contains)})).sort((a,b)=>{const r=a.getBoundingClientRect(),s=b.getBoundingClientRect();return r.width*r.height-s.width*s.height;})[0]`;
    } else throw new Error('target inválido: ' + JSON.stringify(target));
    const out = await this.evaluate(`(() => { try { const el=${js}; if(!el) return null; const r=el.getBoundingClientRect();
      if(r.width===0&&r.height===0) return null; return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,left:r.x,w:r.width}); } catch(e){ return null; } })()`);
    if (!out) throw new Error('target no encontrado: ' + JSON.stringify(target));
    return JSON.parse(out);
  }
  async moveTo(x, y, dur = 450) {
    // Movimiento guiado por reloj: la duración real respeta `dur` aunque CDP responda lento.
    const sx = this.mouse.x, sy = this.mouse.y, t0 = Date.now();
    const ov = Math.min(8, Math.hypot(x - sx, y - sy) * 0.03); // pequeño "overshoot" humano
    for (;;) {
      const u = Math.min(1, (Date.now() - t0) / dur);
      const e = 1 - Math.pow(1 - u, 3);
      await this.mv(sx + (x - sx) * e, sy + (y - sy) * e);
      if (u >= 1) break;
      await sleep(10);
    }
    await this.mv(x + (x - sx > 0 ? ov : -ov) * 0.35, y + (y - sy > 0 ? ov : -ov) * 0.2);
    await sleep(40);
    await this.mv(x, y);
  }
  async click() {
    const x = Math.round(this.mouse.x), y = Math.round(this.mouse.y);
    this.marca('click');
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await sleep(60);
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
  }
}

function resolverUrl(u) {
  if (/^[a-z]+:/i.test(u)) return u;                         // http:, https:, file:, about:
  return pathToFileURL(path.resolve(guionDir, u)).href;      // ruta relativa al guion
}

async function lanzarChrome() {
  const exe = buscarChrome();
  if (!exe) throw new Error('No encontré Chrome/Chromium. Indica la ruta con --chrome o la variable CHROME_PATH.');
  const perfil = fs.mkdtempSync(path.join(process.env.GRABADOR_TMP || os.tmpdir(), 'grabador-perfil-'));
  const args = [argv.includes('--headful') ? '' : '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${perfil}`,
    `--window-size=${VW},${VH}`, '--hide-scrollbars', '--mute-audio', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--force-color-profile=srgb', 'about:blank'].filter(Boolean);
  if (process.platform === 'linux' && process.getuid && process.getuid() === 0) args.unshift('--no-sandbox');
  const proc = spawn(exe, args, { stdio: 'ignore' });
  const archivoPuerto = path.join(perfil, 'DevToolsActivePort');
  for (let k = 0; k < 150 && !fs.existsSync(archivoPuerto); k++) await sleep(100);
  if (!fs.existsSync(archivoPuerto)) { proc.kill(); throw new Error('Chrome no abrió el puerto de depuración.'); }
  await sleep(150);
  const puerto = fs.readFileSync(archivoPuerto, 'utf8').split(/\r?\n/)[0].trim();
  return { proc, perfil, puerto, exe };
}

async function listaPestanas(puerto) { return (await fetch(`http://127.0.0.1:${puerto}/json/list`)).json(); }

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const ch = await lanzarChrome();
  console.log('chrome: ' + path.basename(ch.exe) + ' · puerto ' + ch.puerto + ' · viewport ' + VW + 'x' + VH);
  const cerrar = () => { try { ch.proc.kill(); } catch (_) {} setTimeout(() => { try { fs.rmSync(ch.perfil, { recursive: true, force: true }); } catch (_) {} }, 400); };
  try {
    let pag = null;
    for (let k = 0; k < 50 && !pag; k++) { pag = (await listaPestanas(ch.puerto)).find(t => t.type === 'page'); if (!pag) await sleep(100); }
    let tab = new Tab(pag.webSocketDebuggerUrl, path.join(OUT, 'frames-a'), 'a');
    await tab.connect(); await tab.init();
    const ACCION = new Set(['move', 'hover', 'click', 'type', 'wheel', 'scrollTo', 'dwell']);

    for (const st of guion.steps) {
      const tPaso = Date.now();
      if (ACCION.has(st.op) && !tab.capturando) await tab.empezar(); // captura automática si no se abrió segmento
      switch (st.op) {
        case 'goto': await tab.send('Page.navigate', { url: resolverUrl(st.url) }); await sleep(st.ms || 1000); break;
        case 'wait': {
          const fin = Date.now() + (st.timeout || 15000); let ok = false;
          while (Date.now() < fin && !ok) {
            ok = await tab.evaluate(st.selector ? `!!document.querySelector(${JSON.stringify(st.selector)})` : (st.until || 'true'));
            if (!ok) await sleep(120);
          }
          if (!ok) console.log('AVISO: wait agotado ' + (st.selector || st.until));
          break;
        }
        case 'clearCookies': await tab.send('Network.enable'); await tab.send('Network.clearBrowserCookies'); break;
        case 'segment': {
          await tab.parar();
          tab.dir = path.join(OUT, 'frames-' + st.name); tab.nombre = st.name;
          await tab.empezar(); break;
        }
        case 'attachNewTab': {
          await tab.parar();
          const fin = Date.now() + (st.timeout || 15000); let found = null;
          while (Date.now() < fin && !found) {
            found = (await listaPestanas(ch.puerto)).find(t => t.type === 'page' && (t.url || '').includes(st.match) && t.webSocketDebuggerUrl !== tab.wsUrl);
            if (!found) await sleep(250);
          }
          if (!found) { console.log('AVISO: no apareció la pestaña ' + st.match); break; }
          const seg = st.segment || 'tab2';
          const nueva = new Tab(found.webSocketDebuggerUrl, path.join(OUT, 'frames-' + seg), seg);
          nueva.mouse = { ...tab.mouse };
          await nueva.connect(); await nueva.init();
          for (let k = 0; k < 60; k++) { if (await nueva.evaluate('document.readyState') === 'complete') break; await sleep(250); }
          tab = nueva; await tab.empezar(); break;
        }
        case 'move': { const p = await tab.resolve(st.target); await tab.moveTo(p.x, p.y, st.dur || 450); break; }
        case 'hover': { const p = await tab.resolve(st.target); await tab.moveTo(p.x, p.y, st.dur || 450); await sleep(st.hold || 500); break; }
        case 'click': {
          if (st.target) { const p = await tab.resolve(st.target); await tab.moveTo(p.x, p.y, st.dur || 400); }
          await sleep(st.hold || 150); await tab.click(); break;
        }
        case 'type': {
          const p = await tab.resolve(st.selector || st.target);
          // clic cerca del inicio del campo: el texto escrito queda junto al puntero (y la cámara lo encuadra)
          await tab.moveTo(p.left + Math.min(90, p.w / 2), p.y, st.dur || 400); await tab.click(); await sleep(150);
          tab.marca('type');
          const texto = envVal(st.value) || '';
          if (st.delay === 0) await tab.send('Input.insertText', { text: texto });
          else for (const c of texto) { await tab.send('Input.insertText', { text: c }); await sleep(st.delay || 70); }
          await sleep(st.hold || 400); break;
        }
        case 'wheel': {
          for (let k = 0; k < (st.n || 3); k++) {
            await tab.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: Math.round(tab.mouse.x), y: Math.round(tab.mouse.y), deltaX: 0, deltaY: st.dy || 130 });
            await sleep(st.gap || 40);
          }
          break;
        }
        case 'scrollTo': {
          let yExpr = 'document.documentElement.scrollHeight - innerHeight';
          if (typeof st.y === 'number') yExpr = String(st.y);
          else if (typeof st.y === 'string' && st.y.startsWith('css:')) yExpr = `(document.querySelector(${JSON.stringify(st.y.slice(4))})?.getBoundingClientRect().top+scrollY-40)||0`;
          const total = Math.max(0, Number(await tab.evaluate(yExpr)) || 0);
          const desde = Number(await tab.evaluate('scrollY')) || 0;
          const pasos = st.steps || 8;
          for (let k = 1; k <= pasos; k++) {
            await tab.evaluate(`window.scrollTo({top:${Math.round(desde + (total - desde) * k / pasos)}, behavior:'smooth'})`);
            for (let j = 0; j < (st.paint || 6); j++) await sleep(38);
          }
          await sleep(200); break;
        }
        case 'dwell': await sleep(st.ms || 600); break;
        case 'stop': await tab.parar(); break;
        default: console.log('AVISO: paso desconocido ' + st.op);
      }
      console.log('ok ' + st.op + (st.name ? ' ' + st.name : '') + ' (' + (Date.now() - tPaso) + ' ms)');
    }
    await tab.parar();
    console.log('LISTO ' + OUT);
    cerrar(); setTimeout(() => process.exit(0), 600);
  } catch (e) {
    console.error('ERROR ' + e.message); cerrar(); setTimeout(() => process.exit(1), 600);
  }
})();
