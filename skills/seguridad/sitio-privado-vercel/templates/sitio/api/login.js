// POST /api/login  {password, remember}  →  200 + cookie de sesión HttpOnly firmada (HMAC-SHA256)
//                                         →  401 contraseña mala · 429 demasiados intentos · 500 sin configurar
// Cabecera que emite (ver _sesion.js):  Set-Cookie: sp_session=<token>; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200
const s = require('./_sesion');

// Límite de intentos por IP. Vive en la memoria de la instancia: frena la fuerza bruta casual sin
// servicios externos, pero Vercel puede repartir peticiones entre instancias y reiniciarlas, así que es
// un freno, no un muro. Para un tope global usa un almacén compartido (ver references/despliegue.md).
const MAX_FALLOS = Number(process.env.LOGIN_MAX_ATTEMPTS) || 5;
const VENTANA_MS = (Number(process.env.LOGIN_WINDOW_MINUTES) || 15) * 60 * 1000;
const PAUSA_MS = process.env.LOGIN_FAIL_DELAY_MS !== undefined ? Number(process.env.LOGIN_FAIL_DELAY_MS) : 400;
const fallos = new Map(); // ip -> { n, desde }

function ipDe(req) {
  // En Vercel la plataforma reescribe x-forwarded-for con la IP real del cliente. En otro proxy, revisa
  // que no se pueda falsificar antes de confiar en esta cabecera.
  const xf = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  return xf || String(req.headers['x-real-ip'] || '') || 'desconocida';
}

function esperaRestante(ip, ahora) {
  const f = fallos.get(ip);
  if (!f) return 0;
  if (ahora - f.desde > VENTANA_MS) { fallos.delete(ip); return 0; }
  return f.n >= MAX_FALLOS ? Math.max(1, Math.ceil((f.desde + VENTANA_MS - ahora) / 1000)) : 0;
}

function registrarFallo(ip, ahora) {
  const f = fallos.get(ip);
  if (!f || ahora - f.desde > VENTANA_MS) fallos.set(ip, { n: 1, desde: ahora });
  else f.n += 1;
  if (fallos.size > 5000) fallos.clear(); // tope de memoria ante barridos de muchas IPs
  return fallos.get(ip).n;
}

module.exports = (req, res) => {
  if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); return s.json(res, 405, { error: 'method' }); }
  if (!s.configurado()) return s.json(res, 500, { error: 'server_misconfigured' });
  const ip = ipDe(req);
  const espera = esperaRestante(ip, Date.now());
  if (espera) {
    console.warn(JSON.stringify({ evento: 'login_bloqueado', espera_s: espera }));
    res.setHeader('Retry-After', String(espera));
    return s.json(res, 429, { error: 'too_many_attempts', retry_after: espera });
  }
  let cuerpo = '';
  let demasiado = false;
  req.on('data', (c) => {
    if (demasiado) return;
    cuerpo += c;
    if (cuerpo.length > 4096) { demasiado = true; s.json(res, 413, { error: 'too_large' }); }
  });
  req.on('end', () => {
    if (demasiado) return;
    let pass = '', recordar = false;
    try { const j = JSON.parse(cuerpo || '{}'); pass = String(j.password || ''); recordar = j.remember === true; } catch (e) { /* cuerpo inválido = contraseña vacía */ }
    if (!s.contrasenaCorrecta(pass)) {
      const n = registrarFallo(ip, Date.now());
      console.warn(JSON.stringify({ evento: 'login_fallido', intentos: n }));
      return setTimeout(() => s.json(res, 401, { error: 'invalid' }), PAUSA_MS);
    }
    fallos.delete(ip);
    const segundos = recordar ? 30 * 24 * 3600 : 12 * 3600; // 30 días con «recordarme», 12 h sin él
    res.setHeader('Set-Cookie', s.cookieSesion(s.crearToken(segundos), segundos));
    s.json(res, 200, { ok: true });
  });
};
