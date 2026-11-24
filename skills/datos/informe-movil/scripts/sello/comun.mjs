// comun.mjs · Chrome sin pantalla + puppeteer-core para las mediciones del sello.
// Chrome: variable CHROME_PATH, o se busca en las rutas habituales de Windows, macOS y Linux,
// en la caché de @puppeteer/browsers (~/.cache/puppeteer) y en el PATH.
import { createRequire } from 'module'; import fs from 'fs'; import path from 'path'; import os from 'os'; import { pathToFileURL } from 'url'; import { execSync } from 'child_process';
const require = createRequire(import.meta.url);
export const puppeteer = require('puppeteer-core');
function enCache(base, nombres) {
  // ~/.cache/puppeteer/<producto>/<plataforma-version>/<carpeta>/<ejecutable>: la versión más nueva primero
  if (!fs.existsSync(base)) return null;
  for (const v of fs.readdirSync(base).sort().reverse()) {
    const d = path.join(base, v); if (!fs.statSync(d).isDirectory()) continue;
    for (const s of fs.readdirSync(d)) for (const n of nombres) { const e = path.join(d, s, n); if (fs.existsSync(e)) return e; }
  }
  return null;
}
export function buscarChrome() {
  if (process.env.CHROME_PATH) { if (fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH; throw new Error('CHROME_PATH no existe: ' + process.env.CHROME_PATH); }
  const h = os.homedir(), P = process.env;
  const fijas = {
    win32: [`${P['PROGRAMFILES'] || 'C:/Program Files'}/Google/Chrome/Application/chrome.exe`, `${P['PROGRAMFILES(X86)'] || 'C:/Program Files (x86)'}/Google/Chrome/Application/chrome.exe`,
            `${P['LOCALAPPDATA'] || ''}/Google/Chrome/Application/chrome.exe`, `${P['PROGRAMFILES'] || 'C:/Program Files'}/Chromium/Application/chrome.exe`,
            `${P['PROGRAMFILES(X86)'] || 'C:/Program Files (x86)'}/Microsoft/Edge/Application/msedge.exe`, `${P['PROGRAMFILES'] || 'C:/Program Files'}/Microsoft/Edge/Application/msedge.exe`],
    darwin: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'],
    linux: ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium', '/usr/bin/microsoft-edge'],
  }[process.platform] || [];
  for (const e of fijas) if (e && fs.existsSync(e)) return e;
  const exes = process.platform === 'win32' ? ['chrome-headless-shell.exe', 'chrome.exe'] : ['chrome-headless-shell', 'chrome', 'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'];
  for (const prod of ['chrome-headless-shell', 'chrome']) { const e = enCache(path.join(h, '.cache', 'puppeteer', prod), exes); if (e) return e; }
  if (process.platform !== 'win32') for (const n of ['google-chrome', 'chromium', 'chromium-browser']) { try { const e = execSync('command -v ' + n, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); if (e) return e; } catch { } }
  throw new Error('No encuentro Chrome ni Chromium: instálelo o defina CHROME_PATH');
}
let _exe = null; try { _exe = buscarChrome(); } catch (e) { _exe = null; }
export const exe = _exe;
if (!exe && !process.argv[1]?.endsWith('chrome.mjs')) { console.error('No encuentro Chrome ni Chromium: instálelo o defina CHROME_PATH'); process.exit(3); }
export const espera = ms => new Promise(r => setTimeout(r, ms));
export const urlDe = (f, hash = '') => pathToFileURL(path.resolve(f)).href + (hash ? '#' + hash : '');
export async function movil(b, url, { w = 390, h = 844, dpr = 2, js = true, errs = null } = {}) {
  const p = await b.newPage(); await p.setViewport({ width: w, height: h, deviceScaleFactor: dpr, isMobile: true, hasTouch: true });
  await p.setJavaScriptEnabled(js);
  if (errs) { p.on('console', m => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); }); p.on('pageerror', e => errs.push(String(e))); }
  await p.goto(url, { waitUntil: 'load' }); await espera(700); return p;
}
// espera a que el desplazamiento suave termine (tres lecturas iguales seguidas)
export async function quieto(p, max = 4000) {
  let last = -1, n = 0; const t0 = Date.now();
  while (Date.now() - t0 < max) { const y = await p.evaluate(() => scrollY); if (Math.abs(y - last) < 1) { if (++n >= 3) return; } else n = 0; last = y; await espera(90); }
}
