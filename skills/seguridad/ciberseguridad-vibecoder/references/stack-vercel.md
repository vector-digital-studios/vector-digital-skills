# Stack Vercel (estático y serverless)

Receta probada en un panel personal real con login (funciones `api/`, datos privados, gráficos y
un globo 3D), auditado y endurecido en un día.

## Cabeceras base (vercel.json moderno, sin `routes`)
```json
{
  "headers": [{
    "source": "/(.*)",
    "headers": [
      { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests" },
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
      { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=(), payment=()" },
      { "key": "Cross-Origin-Opener-Policy", "value": "same-origin" }
    ]
  }]
}
```
- Si el proyecto usa `routes` (formato antiguo), el bloque `headers` se IGNORA: las cabeceras van
  dentro de una route `{ "src": "/(.*)", "headers": {...} }`, y la primera route de cabeceras que
  coincide es la que se aplica.
- `Access-Control-Allow-Origin: *` lo pone Vercel por defecto en estáticos; si hay JSON con datos,
  sobrescribirlo o moverlos detrás de una función.
- Con `routes`, los `rewrites` modernos no interceptan archivos estáticos: para proteger `/data/*`
  hay que rutearlo explícitamente a una función (`{ "src": "/data/(.*)", "dest": "/api/data?file=$1" }`).

## `.vercelignore` (obligatorio si la carpeta no es solo la web)
```
*.md
!README.md
backups/
*.bak*
scripts/
*.py
*.sh
*.ps1
*.log
.env*
.agents/
.claude/
```
Vercel publica también las carpetas que empiezan por punto. Ojo con las carpetas que crean las
herramientas al ejecutarse dentro del proyecto (p. ej. un `XDG_DATA_HOME` apuntando al proyecto deja
publicada la carpeta de datos del CLI). Verificar con `vd_sec_scan.py all <ruta> <url>`: cada resto da 404.

## Login real con funciones serverless
- `api/login.js`: compara contra un hash en variable de entorno con `crypto.timingSafeEqual`; emite
  cookie `HttpOnly; Secure; SameSite=Lax` con un token `{exp}` firmado con HMAC-SHA256.
- `api/data.js`: verifica la cookie ANTES que el método; lista blanca de archivos, sin `..`. Para
  servir un archivo fuera de `data/` tras el login: un alias explícito en la función + `includeFiles`.
- `/data/*` sin cookie → 401 (esperado).

## Límite de intentos sin servicios externos
Mapa en memoria por IP dentro de la función: 5 fallos en 15 min → 429 + `Retry-After`, 400 ms de
demora por fallo y un `console.warn` por fallo y por bloqueo (quedan en `vercel logs`). Es un freno,
no un muro: Vercel reparte instancias. Para un muro real: Redis gestionado o una regla del firewall de Vercel.

## CSP estricta sin romper la web
1. Sacar los `<script>` en línea a archivos y copiar las librerías de CDN (y sus recursos, p. ej.
   texturas de un globo 3D) al propio dominio. Así basta `script-src 'self'`, sin SRI que mantener.
2. Páginas estáticas con scripts en línea y sin datos (privacidad, términos) pueden llevar en su
   propia route una CSP con `'unsafe-inline'`; el resto, la estricta.
3. `report-uri /api/csp-report` con una función que solo hace `console.warn`: violaciones reales en los logs.
4. Subir la versión de caché del service worker y el `?v=` del JS tocado.
5. Probar con `scripts/banco_csp_local.cjs` (con y sin CSP) antes de publicar.
`style-src 'unsafe-inline'` puede quedarse: los estilos en línea y los que inyectan las librerías de
gráficos son muchos y quitarlos cuesta mucho para lo poco que protege.

## Previews y entornos
- Deployment Protection en previews: las URL de preview redirigen (302) al login de Vercel. Para
  probarlas por script: un secreto de Protection Bypass for Automation, o el banco local.
- Variables distintas para Preview y Production.

## Verificación con curl
```bash
curl -sI https://<dominio>/ | grep -iE 'content-security|x-frame|nosniff|referrer|permissions|strict-transport|access-control'
curl -s -o /dev/null -w '%{http_code}\n' https://<dominio>/.env          # 404
curl -s -o /dev/null -w '%{http_code}\n' https://<dominio>/data/x.json   # 401 si es privado
```
