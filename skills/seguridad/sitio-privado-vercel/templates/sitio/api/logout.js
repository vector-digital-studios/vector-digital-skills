// POST /api/logout  →  borra la cookie de sesión en este navegador.
// Cabecera que emite:  Set-Cookie: sp_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0
// El token no tiene estado en el servidor: para invalidar TODAS las sesiones, rota SESSION_SECRET.
const s = require('./_sesion');

module.exports = (req, res) => {
  if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); return s.json(res, 405, { error: 'method' }); }
  res.setHeader('Set-Cookie', s.cookieBorrada());
  s.json(res, 200, { ok: true });
};
