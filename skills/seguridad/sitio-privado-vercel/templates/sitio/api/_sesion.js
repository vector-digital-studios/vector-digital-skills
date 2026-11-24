// Utilidades compartidas de sesión. Los archivos de api/ que empiezan por "_" no se publican como
// funciones en Vercel: solo se importan desde las demás.
//
// Token de sesión = base64url(JSON {exp, v}) + "." + base64url(HMAC-SHA256(payload, SESSION_SECRET)).
// Sin estado en el servidor: la firma prueba que lo emitimos nosotros y "exp" que sigue vigente.
const crypto = require('crypto');

const COOKIE = process.env.SESSION_COOKIE_NAME || 'sp_session';

function secretos() {
  // SESSION_SECRET firma y verifica. SESSION_SECRET_PREVIOUS (opcional) solo verifica: permite rotar
  // el secreto sin expulsar a nadie de golpe (ver references/despliegue.md).
  return [process.env.SESSION_SECRET || '', process.env.SESSION_SECRET_PREVIOUS || ''].filter((s) => s.length >= 32);
}

function firmar(payload, secreto) {
  return crypto.createHmac('sha256', secreto).update(payload).digest('base64url');
}

function crearToken(segundos) {
  const [secreto] = secretos();
  const payload = Buffer.from(JSON.stringify({ exp: Date.now() + segundos * 1000, v: 1 })).toString('base64url');
  return payload + '.' + firmar(payload, secreto);
}

function iguales(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

function tokenValido(token) {
  if (!token || typeof token !== 'string' || token.length > 512) return false;
  const partes = token.split('.');
  if (partes.length !== 2) return false;
  const [payload, firma] = partes;
  if (!secretos().some((s) => iguales(firma, firmar(payload, s)))) return false;
  try {
    const datos = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return typeof datos.exp === 'number' && datos.exp > Date.now();
  } catch (e) { return false; }
}

function leerCookie(req, nombre) {
  for (const parte of String(req.headers.cookie || '').split(';')) {
    const i = parte.indexOf('=');
    if (i !== -1 && parte.slice(0, i).trim() === nombre) return parte.slice(i + 1).trim();
  }
  return null;
}

function sesionValida(req) {
  return tokenValido(leerCookie(req, COOKIE));
}

function cookieSesion(token, segundos) {
  return COOKIE + '=' + token + '; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=' + segundos;
}

function cookieBorrada() {
  return COOKIE + '=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0';
}

// Hash de la contraseña en SITE_PASSWORD_HASH:
//   scrypt$<sal base64url>$<hash base64url>   (recomendado; lo genera scripts/generar_claves.cjs)
//   <64 hex>                                   (SHA-256 sin sal; compatible, solo con contraseñas aleatorias largas)
function contrasenaCorrecta(pass) {
  const guardado = process.env.SITE_PASSWORD_HASH || '';
  if (!pass) return false;
  if (guardado.startsWith('scrypt$')) {
    const [, sal, hash] = guardado.split('$');
    if (!sal || !hash) return false;
    const esperado = Buffer.from(hash, 'base64url');
    const calculado = crypto.scryptSync(pass, Buffer.from(sal, 'base64url'), esperado.length || 32);
    return esperado.length > 0 && crypto.timingSafeEqual(calculado, esperado);
  }
  if (/^[0-9a-f]{64}$/i.test(guardado)) {
    const a = crypto.createHash('sha256').update(pass).digest();
    return crypto.timingSafeEqual(a, Buffer.from(guardado, 'hex'));
  }
  return false;
}

function configurado() {
  const h = process.env.SITE_PASSWORD_HASH || '';
  return (h.startsWith('scrypt$') || /^[0-9a-f]{64}$/i.test(h)) && (process.env.SESSION_SECRET || '').length >= 32;
}

function json(res, codigo, obj) {
  res.statusCode = codigo;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(obj));
}

module.exports = { COOKIE, crearToken, tokenValido, leerCookie, sesionValida, cookieSesion, cookieBorrada,
  contrasenaCorrecta, configurado, json };
