// Banco de prueba local: sirve un sitio Vercel con las cabeceras REALES de su vercel.json (routes legacy) y
// recorre sus vistas con Chromium contando violaciones de CSP, errores de consola y texto visible.
// Sirve cuando el preview está protegido por SSO y no hay secreto de bypass. Sin red de datos, sin secretos.
// Uso: NODE_PATH=<repo con @playwright/test>/node_modules PLAYWRIGHT_BROWSERS_PATH=<ms-playwright>
//      node banco_csp_local.cjs <carpeta_sitio> <puerto> <salida_dir> [csp|sin-csp] [vista1,vista2,...]
// Comparar SIEMPRE 'csp' (copia nueva) contra 'sin-csp' (código en producción): un error que ya existía no es regresión.
// Si existe api/login.js lo carga con una clave FALSA local y prueba el límite de intentos (7 fallos → 429).
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('@playwright/test');
const [root, port, out, modo, vistasArg] = process.argv.slice(2);
const conCSP = modo !== 'sin-csp';
const vj = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8'));
const hdrRoutes = vj.routes.filter(r => r.headers && !r.dest);
const tipos = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json', '.woff2': 'font/woff2' };
const violaciones = [];
process.env.VH_PASS_HASH = require('crypto').createHash('sha256').update('clave-de-prueba-local').digest('hex');
process.env.VH_SESSION_SECRET = 'secreto-local-de-prueba';
const login = fs.existsSync(path.resolve(root, 'api/login.js')) ? require(path.resolve(root, 'api/login.js')) : null;
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'); let p = decodeURIComponent(u.pathname);
  if (conCSP) { const r = hdrRoutes.find(r => new RegExp('^' + r.src + '$').test(p)); if (r) for (const [k, v] of Object.entries(r.headers)) res.setHeader(k, v); }
  if (p === '/api/csp-report') { let b = ''; req.on('data', c => b += c); req.on('end', () => { try { const j = JSON.parse(b)['csp-report']; violaciones.push(j['violated-directive'] + ' ← ' + j['blocked-uri']); } catch (e) {} res.statusCode = 204; res.end(); }); return; }
  if (p === '/api/login' && login) {
    res.status = (c) => { res.statusCode = c; return res; }; res.json = (o) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(o)); };
    req.headers['x-forwarded-for'] = req.headers['x-test-ip'] || '1.2.3.4'; return login(req, res);
  }
  if (p === '/') p = '/index.html';
  let f = path.join(root, p); if (!fs.existsSync(f) && fs.existsSync(f + '.html')) f += '.html';
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.statusCode = 404; return res.end('404'); }
  res.setHeader('Content-Type', tipos[path.extname(f)] || 'application/octet-stream'); fs.createReadStream(f).pipe(res);
});
srv.listen(Number(port), async () => {
  const base = `http://127.0.0.1:${port}`;
  const resumen = { csp: conCSP, vistas: {}, login: [] };
  // 1) límite de intentos (código real de api/login.js)
  if (login) for (let i = 0; i < 7; i++) {
    const r = await fetch(base + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"password":"falsa"}' });
    resumen.login.push(r.status + (r.headers.get('retry-after') ? '(Retry-After ' + r.headers.get('retry-after') + 's)' : ''));
  }
  const otraIp = !login ? null : await fetch(base + '/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-test-ip': '9.9.9.9' }, body: '{"password":"clave-de-prueba-local"}' });
  if (otraIp) resumen.login_otra_ip_clave_buena = otraIp.status + ' ' + (otraIp.headers.get('set-cookie') || '').split(';').slice(1).join(';');
  // 2) recorrido de vistas
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  let errores = [];
  page.on('console', m => { if (m.type() === 'error') errores.push(m.text().slice(0, 160)); });
  page.on('pageerror', e => errores.push('JS: ' + String(e.message).slice(0, 160)));
  // vistas = hashes del SPA a recorrer (5.º argumento, separados por comas); sin lista se prueba solo la portada
  const vistas = (vistasArg || 'home').split(',');
  await page.goto(base + '/', { waitUntil: 'load' }); await page.waitForTimeout(2500);
  for (const v of vistas) {
    errores = []; const antes = violaciones.length;
    await page.evaluate(h => { location.hash = h; }, v); await page.waitForTimeout(3500);
    const lleno = await page.evaluate(() => { const s = document.querySelector('.view.active, section.active, [data-view].active') || document.body; return s.innerText.length; });
    const canvas = await page.evaluate(() => document.querySelectorAll('canvas').length);
    await page.screenshot({ path: path.join(out, `${conCSP ? 'csp' : 'base'}_${v}.png`) });
    resumen.vistas[v] = { errores: [...new Set(errores)], violaciones_csp: violaciones.slice(antes), texto: lleno, canvas };
  }
  for (const p of ['/privacy', '/terms']) { const antes = violaciones.length; errores = []; await page.goto(base + p); await page.waitForTimeout(1200); resumen.vistas[p] = { errores: [...new Set(errores)], violaciones_csp: violaciones.slice(antes) }; }
  await browser.close(); srv.close();
  fs.writeFileSync(path.join(out, `resumen_${conCSP ? 'csp' : 'base'}.json`), JSON.stringify(resumen, null, 1));
  console.log(JSON.stringify(resumen, null, 1));
});
