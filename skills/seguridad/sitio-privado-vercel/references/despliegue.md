# Despliegue en Vercel

Guía paso a paso para publicar `templates/sitio/` con login real. Todo funciona en el plan gratuito (Hobby).
Los comandos usan la CLI oficial (`npm i -g vercel`, comprobado con la versión 59).

> Antes de nada: `python scripts/autoprueba.py` debe terminar en `OK`. Si cambiaste las funciones o
> `vercel.json`, vuelve a correrla.

## 1. Copiar la plantilla

```bash
cp -r templates/sitio mi-panel
cd mi-panel
```

Pon tus archivos JSON en `data/` (solo `.json`; `api/data.js` rechaza otras extensiones) y adapta
`index.html`, `js/app.js` y `css/estilos.css`. Reglas para no romper la CSP:

- Nada de `<script>` en línea ni `onclick=""`: todo el JavaScript va en archivos de `js/`.
- Nada de `style=""` en el HTML: los estilos van en `css/`.
- Si cargas algo de otro dominio (fuentes, analítica, un CDN), añádelo a la directiva que toque en la
  `Content-Security-Policy` de `vercel.json` (o, mejor, sírvelo desde tu propio dominio).

## 2. Generar la contraseña y el secreto

```bash
node ../scripts/generar_claves.cjs          # pide la contraseña sin mostrarla (mínimo 12 caracteres)
# SITE_PASSWORD_HASH=scrypt$…$…
# SESSION_SECRET=…
```

- Usa una contraseña larga y aleatoria (16+ caracteres de un gestor de contraseñas). El límite de intentos
  es un freno, no un muro: la defensa principal es que la contraseña no se pueda adivinar.
- El hash es scrypt con sal: aunque alguien viera la variable, no tiene la contraseña.
- No pegues estos valores en el chat de un agente, en commits ni en capturas.

Para probar en local antes de subir nada:

```bash
node ../scripts/generar_claves.cjs > .env.local     # .env.local está en .vercelignore y no se publica
node ../scripts/servidor_local.cjs --dir . --port 3000 --env .env.local
# LISTO http://127.0.0.1:3000
```

## 3. Crear el proyecto y cargar las variables

```bash
vercel login
vercel link                                   # crea o vincula el proyecto (carpeta .vercel/, no se publica)
vercel env add SITE_PASSWORD_HASH production --sensitive   # pega el valor cuando lo pida
vercel env add SESSION_SECRET production --sensitive
```

Si también quieres que las vistas previas (`vercel deploy` sin `--prod`) tengan login, añade las mismas
variables al entorno `preview`. Las variables solo se leen al desplegar: tras cambiarlas, **vuelve a desplegar**.

Opcionales: `LOGIN_MAX_ATTEMPTS` (5), `LOGIN_WINDOW_MINUTES` (15), `LOGIN_FAIL_DELAY_MS` (400),
`SESSION_COOKIE_NAME` (`sp_session`).

## 4. Desplegar

```bash
vercel deploy --prod
```

## 5. Verificar con evidencia (no basta con que abra)

```bash
URL=https://<tu-proyecto>.vercel.app
curl -s -o /dev/null -w '%{http_code}\n' "$URL/data/resumen.json"            # 401
curl -sI "$URL/" | grep -iE 'content-security-policy|strict-transport|x-frame|reporting-endpoints'
curl -s -c jar.txt -H 'Content-Type: application/json' \
     -d '{"password":"<tu contraseña>"}' "$URL/api/login"                     # {"ok":true}
curl -s -b jar.txt "$URL/data/resumen.json" | head -c 200                     # tus datos
for p in .env.example .env.local .vercelignore api/_sesion.js; do
  curl -s -o /dev/null -w "$p %{http_code}\n" "$URL/$p"                       # 404 en todos
done
for p in //data/resumen.json /DATA/resumen.json /data%2Fresumen.json; do
  curl -s -o /dev/null -w "$p %{http_code}\n" "$URL$p"                        # nunca 200 sin cookie
done
rm jar.txt
```

Si escribes la contraseña en `curl`, queda en el historial de la terminal: bórrala después o usa
`-d @archivo.json` con un archivo temporal.

En el navegador: abre la consola de DevTools, entra y navega por todo el sitio. No debe aparecer ningún
mensaje «Refused to …» de Content Security Policy.

## 6. Leer el buzón de la CSP

Cada violación deja una línea en los registros de la función:

```bash
vercel logs <url-del-despliegue> --follow
# {"evento":"csp_violacion","directiva":"img-src","bloqueado":"https://…","pagina":"https://…/","linea":null}
```

- Los navegadores con soporte de `report-to` (cabecera `Reporting-Endpoints`) lo usan e ignoran `report-uri`;
  los que no lo soportan usan `report-uri`. La plantilla declara los dos. Los informes de `report-to` llegan
  en lotes, a veces con segundos o un minuto de retraso.
- `report-to` necesita HTTPS: en `http://127.0.0.1` Chrome no mandó ningún informe en nuestra prueba; detrás
  de HTTPS sí (en Vercel siempre hay HTTPS).
- Una violación que se repite en tu propio sitio = la política bloquea algo que usas: ajusta la directiva.
  Violaciones de extensiones del navegador (`chrome-extension://…`) son ruido normal.

## 7. Rotar el secreto de sesión

Rotar `SESSION_SECRET` invalida todas las sesiones (es la única forma de «cerrar sesión en todos lados»,
porque los tokens no se guardan en el servidor). Dos modos:

**Corte inmediato** (sospechas de filtración):

```bash
node ../scripts/generar_claves.cjs --solo-secreto          # SESSION_SECRET=<nuevo>
vercel env rm SESSION_SECRET production
vercel env add SESSION_SECRET production --sensitive        # pega el nuevo
vercel deploy --prod                                        # todos tendrán que volver a entrar
```

**Rotación suave** (mantenimiento programado):

1. Copia el valor actual a `SESSION_SECRET_PREVIOUS` y pon uno nuevo en `SESSION_SECRET`; despliega.
   Las sesiones viejas siguen valiendo; las nuevas se firman con el secreto nuevo.
2. Pasados 30 días (la vida máxima de una sesión con «recordarme»), borra `SESSION_SECRET_PREVIOUS` y despliega.

Cambiar la contraseña es igual: genera un `SITE_PASSWORD_HASH` nuevo, reemplázalo y despliega. Las sesiones
abiertas siguen vivas hasta que rotes también `SESSION_SECRET`.

## 8. Protección de Vercel (opcional, complementaria)

- **Vista previas**: en *Settings → Deployment Protection*, «Vercel Authentication» (gratis en todos los
  planes) exige una cuenta de Vercel con acceso para ver las URL de cada despliegue. Conviene activarla para
  las vistas previas: así un despliegue a medio configurar nunca queda abierto.
- **Producción**: esta plantilla es la protección. «Password Protection» de Vercel hace algo parecido de
  forma gestionada, pero cuesta 20 USD al mes por proyecto en Pro y no está en Hobby (precios de nov-2026).
- **Acceso de máquinas a vistas previas protegidas** (pruebas automáticas): «Protection Bypass for
  Automation» da un secreto que se envía en la cabecera `x-vercel-protection-bypass`. Guárdalo como cualquier
  otra credencial.

## 9. Límite de intentos compartido (opcional)

El contador de fallos vive en la memoria de cada instancia de la función. Vercel puede atender peticiones
con varias instancias y reiniciarlas, así que un atacante paciente consigue más de 5 intentos por ventana.
Para un tope global sustituye el `Map` de `api/login.js` por un almacén compartido, por ejemplo Redis de
Upstash (integración del Marketplace de Vercel, con capa gratuita) con `INCR` + `EXPIRE` por IP. No viene
incluido para mantener la plantilla sin dependencias ni cuentas extra.

## Por qué `routes` y no `rewrites`

`vercel.json` usa el formato `routes` a propósito: la ruta `/data/(.*)` se evalúa **antes** de servir
archivos estáticos (`"handle": "filesystem"` marca ese punto), así que `data/resumen.json` nunca sale como
archivo público aunque esté en la carpeta; la función lo empaqueta con `includeFiles`. Con `rewrites`, en
cambio, Vercel mira primero el sistema de archivos: si el archivo existe se sirve tal cual y la reescritura
no se aplica. La ruta de cabeceras lleva `"continue": true` para que, tras añadirlas, el enrutado siga.

La documentación actual de Vercel marca `handle` como deprecado (sigue soportado). Es la forma que lleva
en producción el sitio del que sale esta plantilla; si algún día deja de funcionar, la comprobación del
paso 5 (`/data/resumen.json` → 401 sin cookie) lo detecta.
