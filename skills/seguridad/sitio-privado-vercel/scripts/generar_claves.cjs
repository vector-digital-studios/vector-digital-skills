#!/usr/bin/env node
// generar_claves.cjs · crea los valores de SITE_PASSWORD_HASH y SESSION_SECRET sin dependencias.
// La contraseña se lee de la entrada estándar (no como argumento, para que no quede en el historial).
//
//   node scripts/generar_claves.cjs                 # la pide sin mostrarla
//   printf '%s' "$CLAVE" | node scripts/generar_claves.cjs
//   node scripts/generar_claves.cjs --solo-secreto  # solo un SESSION_SECRET nuevo (para rotarlo)
//
// Imprime líneas KEY=valor listas para .env.local o para `vercel env add`. No guarda nada.
'use strict';
const crypto = require('crypto');

function secreto() { return crypto.randomBytes(32).toString('base64url'); }

function hash(clave) {
  const sal = crypto.randomBytes(16);
  const h = crypto.scryptSync(clave, sal, 32);
  return 'scrypt$' + sal.toString('base64url') + '$' + h.toString('base64url');
}

function leerClave() {
  return new Promise((resolve) => {
    const stdin = process.stdin;
    if (!stdin.isTTY) {
      let d = '';
      stdin.setEncoding('utf8');
      stdin.on('data', (c) => { d += c; });
      stdin.on('end', () => resolve(d.replace(/\r?\n$/, '')));
      return;
    }
    process.stderr.write('Contraseña (no se muestra): ');
    stdin.setRawMode(true);
    stdin.setEncoding('utf8');
    let d = '';
    stdin.on('data', function tecla(c) {
      for (const ch of c) {
        if (ch === '\r' || ch === '\n' || ch === '\u0004') {
          stdin.setRawMode(false); stdin.pause(); stdin.removeListener('data', tecla);
          process.stderr.write('\n'); return resolve(d);
        }
        if (ch === '\u0003') { process.stderr.write('\n'); process.exit(130); }
        if (ch === '\u007f' || ch === '\b') d = d.slice(0, -1); else d += ch;
      }
    });
  });
}

(async () => {
  if (process.argv.includes('--solo-secreto')) { console.log('SESSION_SECRET=' + secreto()); return; }
  const clave = await leerClave();
  if (clave.length < 12) {
    console.error('La contraseña debe tener al menos 12 caracteres (mejor 16+ aleatorios).');
    process.exit(2);
  }
  console.log('SITE_PASSWORD_HASH=' + hash(clave));
  console.log('SESSION_SECRET=' + secreto());
})();
