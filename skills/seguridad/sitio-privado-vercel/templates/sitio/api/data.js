// GET /api/data?file=<nombre>.json  →  el archivo de data/ solo con una cookie de sesión válida.
// vercel.json reescribe /data/* hacia aquí, así que el navegador pide /data/resumen.json como siempre.
const fs = require('fs');
const path = require('path');
const s = require('./_sesion');

const DIR_DATOS = path.join(process.cwd(), 'data');

function archivoPedido(req) {
  if (req.query && typeof req.query.file === 'string') return req.query.file;
  try { return new URL(req.url, 'http://local').searchParams.get('file') || ''; } catch (e) { return ''; }
}

module.exports = (req, res) => {
  // La sesión se comprueba ANTES que todo lo demás: sin cookie válida no se revela ni qué existe.
  if (!s.sesionValida(req)) return s.json(res, 401, { error: 'unauthorized' });
  if (req.method !== 'GET') { res.setHeader('Allow', 'GET'); return s.json(res, 405, { error: 'method' }); }
  const archivo = String(archivoPedido(req)).replace(/^\/+/, '');
  if (!/^[A-Za-z0-9_-][A-Za-z0-9_./-]*\.json$/.test(archivo) || archivo.includes('..')) {
    return s.json(res, 400, { error: 'bad_file' });
  }
  const abs = path.normalize(path.join(DIR_DATOS, archivo));
  if (!abs.startsWith(DIR_DATOS + path.sep)) return s.json(res, 400, { error: 'bad_file' });
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) return s.json(res, 404, { error: 'not_found' });
  res.statusCode = 200;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(fs.readFileSync(abs));
};
