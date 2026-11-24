---
name: sitio-privado-vercel
description: "Usar para poner login real, datos con sesión y CSP a un sitio estático en Vercel"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [vercel, login, session, cookie, hmac, csp, rate-limit, static-site, serverless, security, spanish]
  idioma: es
  requiere: "Node 18+ (funciones y servidor local; probado con 22). Python 3 solo para la autoprueba (biblioteca estándar). Cuenta de Vercel (plan gratuito) para desplegar."
---

# Sitio privado en Vercel

Plantilla mínima, sin dependencias, para que un sitio estático en Vercel tenga **acceso real**: login que
entrega una cookie `HttpOnly; Secure; SameSite=Strict` firmada con HMAC-SHA256, datos que solo salen por una
función con sesión válida, límite de intentos (429), CSP estricta con buzón de reportes y pruebas que lo
demuestran.

Úsala cuando el usuario quiera publicar un panel, informe o sitio personal en Vercel «con contraseña», cuando
un sitio estático tenga un candado solo en JavaScript (se salta desde DevTools y los JSON quedan públicos) o
cuando haya que añadir CSP y cabeceras de seguridad a un sitio en Vercel.

## Flujo

1. **Copiar la plantilla**: `templates/sitio/` → carpeta del proyecto. Los datos privados van en `data/*.json`;
   el front los pide como `/data/<archivo>.json` (vercel.json los reescribe a `/api/data`).
2. **Adaptar el front sin romper la CSP**: nada de `<script>` en línea, `on*=` ni `style=""`; todo en `js/` y
   `css/`. Recursos de otros dominios → añadirlos a la directiva concreta de la CSP en `vercel.json`.
3. **Generar claves**: `node scripts/generar_claves.cjs` (pide la contraseña sin mostrarla) →
   `SITE_PASSWORD_HASH` (scrypt) y `SESSION_SECRET`. Nunca pedir ni mostrar estos valores en el chat.
4. **Probar en local**: `node scripts/servidor_local.cjs --dir <proyecto> --env <proyecto>/.env.local` y
   `python scripts/autoprueba.py` (debe terminar en `OK`).
5. **Desplegar y verificar** siguiendo `references/despliegue.md` (variables con `vercel env add`, `vercel
   deploy --prod`, comprobaciones con curl: 401 sin cookie, cabeceras, restos en 404).

## Reglas

- Nunca dar por protegido un sitio por un 200 en la portada: comprobar `401` en `/data/...` sin cookie y
  `200` con cookie, en la URL real.
- No guardar datos privados fuera de `data/` ni servirlos con otra ruta: todo lo que esté en la raíz y no
  excluya `.vercelignore` es público.
- La contraseña debe ser larga y aleatoria: el límite de intentos vive en la memoria de cada instancia y es
  un freno, no un muro (ver «Límite de intentos compartido» en la guía).
- Cerrar sesión borra la cookie de ese navegador; para expulsar a todos hay que rotar `SESSION_SECRET`.
- No añadir `'unsafe-inline'` a `script-src` para «arreglar» algo: mover el script a un archivo.

## Archivos

- `templates/sitio/` la plantilla: `index.html`, `js/app.js`, `css/estilos.css`, `api/login.js`,
  `api/data.js`, `api/logout.js`, `api/csp-report.js`, `api/_sesion.js` (común), `vercel.json`,
  `.vercelignore`, `.env.example`, `data/resumen.json` (datos inventados)
- `scripts/servidor_local.cjs` sirve la plantilla imitando `routes`, funciones y `.vercelignore`
- `scripts/generar_claves.cjs` hash scrypt de la contraseña y secreto de sesión
- `scripts/autoprueba.py` 64 comprobaciones (22 de configuración + 42 HTTP)
- `references/despliegue.md` despliegue, variables, verificación, rotación del secreto y protección
