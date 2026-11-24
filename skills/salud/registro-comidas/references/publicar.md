# Publicar el panel

El panel es una carpeta estática: `index.html`, `app.js`, `styles.css`, `sw.js`, `manifest.webmanifest`,
`icons/`, `fonts/`, `config.json` y `data/`. No hay build, ni servidor propio, ni login.

## Antes que nada: privacidad

Lo que comes es un dato de salud. Cualquier hosting estático público deja `data/*.json` legible para
quien conozca (o adivine) la URL. `index.html` lleva `noindex`, pero eso solo evita buscadores, no
protege. Elige una de estas opciones según cuánto te importe:

| Opción | Quién puede ver tus datos |
|---|---|
| Local (`localhost`) | Solo tu equipo |
| Red de casa (`http://IP-del-PC:8000`) | Quien esté en tu red |
| Vercel con *Deployment Protection* / Netlify con contraseña (planes que lo incluyan) / Cloudflare Access | Solo quien inicie sesión |
| GitHub Pages, Vercel o Netlify sin protección | Cualquiera con el enlace |

## 1. Local

```bash
cd <proyecto>
python -m http.server 8000
# abre http://localhost:8000
```

Con doble clic sobre `index.html` no funciona: los navegadores bloquean `fetch()` en `file://` y el
panel lo avisa en pantalla.

## 2. Celular en la misma red + instalar como app

1. `python -m http.server 8000 --bind 0.0.0.0` en el PC.
2. En el celular: `http://<IP-del-PC>:8000`.
3. Para instalarla como app (PWA) el navegador exige HTTPS o `localhost`; en la red local por HTTP se
   puede abrir pero no siempre instalar. Para instalar de verdad usa una de las opciones con HTTPS.

## 3. Vercel (gratis, HTTPS)

```bash
cd <proyecto>
npx vercel --prod          # la primera vez pide iniciar sesión y crea el proyecto
```

Luego, en el panel de Vercel → Settings → Deployment Protection, activa la protección si no quieres
que los datos sean públicos. Cada registro nuevo requiere volver a desplegar (`npx vercel --prod`), o
conectar el repositorio para que cada `git push` despliegue solo.

## 4. GitHub Pages

Sube la carpeta a un repositorio y activa Settings → Pages (rama `main`, carpeta raíz). En cuentas
gratuitas el sitio de Pages es público aunque el repositorio sea privado: úsalo solo con datos que
aceptes publicar (o con datos de demo).

## Flujo diario con despliegue

1. El agente registra y valida (`registro.py agregar …` → `validar_registro.py data/`).
2. Publica: `git add data && git commit -m "comidas AAAA-MM-DD" && git push` (si el hosting despliega
   desde git) o `npx vercel --prod`.
3. Comprueba en vivo que `data/indice.json` trae la fecha nueva. Un "Ready" del hosting no prueba que
   los datos subieron; el contenido servido sí.

## Caché del service worker

La interfaz, `config.json` e `indice.json` se guardan en caché al instalar; cada día que abras con
conexión queda guardado también. Sin conexión ves la interfaz, la semana y esos días. Los datos
siempre se piden a la red primero, así que con conexión ves lo último. Si cambias `index.html`, `app.js` o `styles.css`, sube `VERSION` en
`sw.js` para que los celulares descarguen la versión nueva.
