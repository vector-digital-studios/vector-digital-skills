# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

Primera versión pública. Deriva del login de un panel personal en Vercel, en producción desde el
5-ago-2026 (límite de intentos y buzón CSP desde el 17-nov-2026).

### Añadido
- Plantilla `templates/sitio/` completa y genérica: página de login, panel de ejemplo con datos inventados,
  funciones `login`, `data`, `logout` y `csp-report`, `vercel.json` con CSP y cabeceras, `.vercelignore`,
  `.env.example`.
- Hash de contraseña con **scrypt y sal** (`scrypt$<sal>$<hash>`); se mantiene compatible el SHA-256 hex.
- `SESSION_SECRET_PREVIOUS` para rotar el secreto de sesión sin expulsar a nadie de golpe.
- `POST /api/logout`.
- CSP con `report-to` + `Reporting-Endpoints` además de `report-uri`; HSTS, `Cross-Origin-Resource-Policy`,
  `X-Robots-Tag: noindex` y `Cache-Control: no-cache` en todo el sitio.
- `scripts/servidor_local.cjs`: sirve la plantilla en local imitando `routes`, funciones y `.vercelignore`.
- `scripts/generar_claves.cjs`: crea el hash y el secreto leyendo la contraseña sin mostrarla.
- `scripts/autoprueba.py`: 64 comprobaciones reales por HTTP contra las funciones (sin red externa).
- `references/despliegue.md`: CLI de Vercel, variables, verificación con curl, rotación, protección.

### Cambiado (respecto del original interno)
- Cookie `SameSite=Strict` (antes `Lax`).
- La ruta de cabeceras de `vercel.json` lleva `"continue": true` (forma documentada) y `/data/*` también
  recibe `nosniff`, `Referrer-Policy` y `X-Robots-Tag`.
- El buzón CSP **rechaza** lo que no es un informe (400) y lo demasiado grande (413); antes respondía 204 a todo.
  Acepta también el formato `application/reports+json` de `report-to`.
- `api/data.js` solo entrega `.json` y responde con `Cache-Control: no-store`.
- Los registros de login ya no incluyen la IP del cliente.
- Variables y cookie con nombres genéricos: `SITE_PASSWORD_HASH`, `SESSION_SECRET`, `sp_session`.
- Límite de intentos, ventana y pausa configurables por variables de entorno.

### Quitado
- Rutas heredadas del proyecto original (alias de archivos fuera de `data/`, páginas sueltas, `scripts/`).
- `cleanUrls`/`trailingSlash` de `vercel.json` (la plantilla no los necesita).
- El candado solo en el navegador de la versión anterior: queda superado por el login en servidor.
