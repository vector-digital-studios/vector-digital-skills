// POST /api/csp-report  →  buzón de violaciones de la CSP.
// Acepta los dos formatos que mandan los navegadores:
//   report-uri  →  application/csp-report    {"csp-report": {...}}
//   report-to   →  application/reports+json  [{"type": "csp-violation", "body": {...}}, ...]
// Solo deja una línea en los registros de la función (`vercel logs`); no guarda nada ni lo reenvía.
// 204 = aceptado · 400 = no es un informe CSP · 405 = método · 413 = demasiado grande.
const MAX_BYTES = 16 * 1024;

function informes(j) {
  if (j && typeof j === 'object' && !Array.isArray(j) && j['csp-report'] && typeof j['csp-report'] === 'object') {
    return [j['csp-report']];
  }
  if (Array.isArray(j)) {
    return j.filter((x) => x && x.type === 'csp-violation' && x.body && typeof x.body === 'object').map((x) => x.body);
  }
  return [];
}

function corto(v) { return String(v == null ? '' : v).split('?')[0].slice(0, 200); }

module.exports = (req, res) => {
  if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); res.statusCode = 405; return res.end(); }
  let cuerpo = '';
  let demasiado = false;
  req.on('data', (c) => {
    if (demasiado) return;
    cuerpo += c;
    if (cuerpo.length > MAX_BYTES) { demasiado = true; res.statusCode = 413; res.end(); }
  });
  req.on('end', () => {
    if (demasiado) return;
    let lista = [];
    try { lista = informes(JSON.parse(cuerpo)); } catch (e) { lista = []; }
    const validos = lista.filter((r) => r['violated-directive'] || r['effective-directive'] || r.effectiveDirective);
    if (!validos.length) { res.statusCode = 400; return res.end(); }
    for (const r of validos.slice(0, 20)) {
      console.warn(JSON.stringify({
        evento: 'csp_violacion',
        directiva: corto(r['effective-directive'] || r.effectiveDirective || r['violated-directive']),
        bloqueado: corto(r['blocked-uri'] || r.blockedURL),
        pagina: corto(r['document-uri'] || r.documentURL),
        linea: Number(r['line-number'] || r.lineNumber) || null
      }));
    }
    res.statusCode = 204;
    res.end();
  });
};
