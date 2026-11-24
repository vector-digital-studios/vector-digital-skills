#!/usr/bin/env node
// servidor_local.cjs · sirve la plantilla en tu equipo imitando lo que hará Vercel, sin cuenta ni red:
//   - aplica las "routes" de vercel.json (cabeceras, reescrituras /data/* → /api/data, "handle": "filesystem"),
//   - ejecuta las funciones de api/*.js (los archivos que empiezan por "_" no son rutas),
//   - no sirve lo que excluye .vercelignore.
// Es una aproximación para desarrollar y probar; la referencia final es un despliegue de vista previa.
//
// Uso:  node scripts/servidor_local.cjs [--dir templates/sitio] [--port 3000] [--host 127.0.0.1] [--env archivo.env]
// Imprime «LISTO http://host:puerto» cuando acepta conexiones (--port 0 = puerto libre al azar).
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');

function args() {
  const a = { dir: path.join(__dirname, '..', 'templates', 'sitio'), port: 3000, host: '127.0.0.1', env: '' };
  const v = process.argv.slice(2);
  for (let i = 0; i < v.length; i++) {
    const k = v[i].replace(/^--/, '');
    if (k in a) a[k] = v[++i];
  }
  a.port = Number(a.port);
  return a;
}

function cargarEnv(archivo) {
  if (!archivo) return;
  for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

function globARegex(g) {
  let r = '';
  for (let i = 0; i < g.length; i++) {
    const c = g[i];
    if (c === '*' && g[i + 1] === '*') { r += '.*'; i++; }
    else if (c === '*') r += '[^/]*';
    else if (c === '?') r += '[^/]';
    else r += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return r;
}

function reglasIgnorar(dir) {
  const f = path.join(dir, '.vercelignore');
  if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, 'utf8').split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).map((l) => {
    const carpeta = l.endsWith('/');
    const base = l.replace(/^\//, '').replace(/\/$/, '');
    const conBarra = base.includes('/');
    const re = new RegExp('^' + globARegex(base) + (carpeta ? '(/.*)?' : '') + '$');
    return { re, conBarra, carpeta };
  });
}

function ignorado(rel, reglas) {
  const partes = rel.split('/');
  return reglas.some(({ re, conBarra }) => {
    if (conBarra) return re.test(rel) || partes.some((_, i) => re.test(partes.slice(0, i + 1).join('/')));
    return partes.some((_, i) => re.test(partes[i]) || re.test(partes.slice(i).join('/')));
  });
}

const TIPOS = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
  '.webp': 'image/webp', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8' };

function main() {
  const a = args();
  const dir = path.resolve(a.dir);
  cargarEnv(a.env);
  process.chdir(dir); // las funciones leen data/ relativo al directorio del proyecto, como en Vercel
  const vercel = JSON.parse(fs.readFileSync(path.join(dir, 'vercel.json'), 'utf8'));
  const rutas = vercel.routes || [];
  const reglas = reglasIgnorar(dir);
  const funciones = {};

  function funcion(nombre) {
    if (!/^[A-Za-z0-9-][A-Za-z0-9_-]*$/.test(nombre)) return null;
    const f = path.join(dir, 'api', nombre + '.js');
    if (!fs.existsSync(f)) return null;
    if (!funciones[nombre]) funciones[nombre] = require(f);
    return funciones[nombre];
  }

  function ejecutar(fn, req, res, url) {
    req.query = Object.fromEntries(url.searchParams);
    res.status = (c) => { res.statusCode = c; return res; };
    res.json = (o) => { res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.end(JSON.stringify(o)); return res; };
    res.send = (b) => { res.end(b); return res; };
    try { fn(req, res); } catch (e) { console.error(e); if (!res.headersSent) { res.statusCode = 500; res.end(); } }
  }

  function archivo(pathname) {
    let rel = decodeURIComponent(pathname).replace(/^\/+/, '');
    if (rel === '' || rel.endsWith('/')) rel += 'index.html';
    if (rel.split('/').some((p) => p === '..')) return null;
    if (ignorado(rel, reglas)) return null;
    const abs = path.join(dir, rel);
    if (!abs.startsWith(dir + path.sep) || !fs.existsSync(abs) || !fs.statSync(abs).isFile()) return null;
    return abs;
  }

  const srv = http.createServer((req, res) => {
    // En Vercel la plataforma pone x-forwarded-for con la IP del cliente; aquí se respeta la que venga
    // (para simular varias IPs en las pruebas) o se usa la del socket.
    if (!req.headers['x-forwarded-for']) req.headers['x-forwarded-for'] = req.socket.remoteAddress || '';
    let url = new URL(req.url, 'http://local');
    for (const r of rutas) {
      if (r.handle === 'filesystem') break;
      const m = new RegExp('^' + r.src + '$').exec(url.pathname);
      if (!m) continue;
      for (const [k, v] of Object.entries(r.headers || {})) res.setHeader(k, v);
      if (r.status && !r.dest) { res.statusCode = r.status; return res.end(); }
      if (r.dest) {
        const destino = r.dest.replace(/\$(\d+)/g, (_, n) => encodeURIComponent(m[Number(n)] || '').replace(/%2F/gi, '/'));
        url = new URL(destino, 'http://local');
        break;
      }
    }
    // fase "filesystem": funciones de api/ y archivos estáticos
    const api = url.pathname.match(/^\/api\/([^/]+?)(?:\.js)?\/?$/);
    if (api) {
      let fn = null;
      try { fn = funcion(api[1]); } catch (e) { console.error(e); res.statusCode = 500; return res.end('500'); }
      if (fn) return ejecutar(fn, req, res, url);
      res.statusCode = 404; return res.end('404');
    }
    if (url.pathname.startsWith('/api/')) { res.statusCode = 404; return res.end('404'); }
    const f = archivo(url.pathname);
    if (!f) { res.statusCode = 404; return res.end('404'); }
    res.setHeader('Content-Type', TIPOS[path.extname(f)] || 'application/octet-stream');
    if (req.method === 'HEAD') return res.end();
    fs.createReadStream(f).pipe(res);
  });

  srv.listen(a.port, a.host, () => {
    const { port } = srv.address();
    console.log('LISTO http://' + (a.host.includes(':') ? '[' + a.host + ']' : a.host) + ':' + port);
  });
  const cerrar = () => srv.close(() => process.exit(0));
  process.on('SIGINT', cerrar);
  process.on('SIGTERM', cerrar);
}

main();
