# Catálogo Escudo VD-44

Formato por control: **qué** · **por qué** (ataque que evita) · **verificar** · **arreglar** · mapeo
(OWASP Top 10:2025 = A01..A10 · ASVS 5.0 = V1..V17 · LLM Top 10 2025 = LLM01..10 · GSF = Game
Security Framework) · `[auto]` si `scripts/vd_sec_scan.py` lo detecta · `[TT]` si estaba en la
checklist de Revolutia.ai.

## SEC · Secretos y claves

- **SEC-01 Claves fuera del navegador** `[auto][TT]` · Toda clave que cueste dinero o dé acceso
  (OpenAI, Anthropic, Stripe secreta, service_role) vive en el servidor; el navegador llama a una
  función propia que la usa. · Por qué: lo que llega al navegador se lee con F12; bots rastrean
  bundles buscando `sk-` y vacían cuotas en horas. · Verificar: escáner sobre `dist/`; buscar en
  DevTools > Sources. · Arreglar: función serverless proxy + variable de entorno. · A04, V13, LLM02.
- **SEC-02 Variables de entorno sanas** `[auto][TT]` · `.env` en `.gitignore`; nada secreto con
  prefijo público (`VITE_`, `NEXT_PUBLIC_`, `EXPO_PUBLIC_`); valores distintos para preview y
  producción. · Por qué: esos prefijos se incrustan en el JS. · A02, V13.
- **SEC-03 Secretos en la historia de Git** `[auto][TT]` · `--history` revisa cada commit. ·
  Por qué: borrar el archivo no borra el commit; GitHub/GitLab públicos se rastrean en minutos. ·
  Arreglar: rotar primero; luego `git filter-repo` si el repo se comparte. · A04, V13.
- **SEC-04 Rotar y revocar** `[TT]` · Inventario de llaves (bóveda local cifrada o gestor de secretos),
  dueño y fecha; procedimiento de rotación probado. · Por qué: una clave filtrada sigue viva hasta
  que se revoca. · A04, V13.

## ACC · Identidad y acceso

- **ACC-01 Autenticación en servidor** `[auto: pista][TT]` · El servidor decide quién entra; un
  candado en JS es decoración. Endpoints privados verifican sesión ANTES de cualquier lógica.
  Login con Google/GitHub (OAuth/OIDC, p. ej. Supabase Auth o Auth.js): flujo con PKCE y `state`,
  URLs de retorno en lista cerrada, validar firma, emisor (`iss`), audiencia (`aud`) y caducidad del
  `id_token`. Tokens JWT: algoritmo fijo en servidor (nunca aceptar `alg: none` ni el que diga el
  token), `exp` corto, secreto fuerte, nunca guardarlos en localStorage si hay alternativa de cookie. · A07, V6, V9, V10.
- **ACC-02 Contraseñas con hash lento** `[TT]` · Argon2id, scrypt o bcrypt con sal por usuario;
  nunca texto plano ni SHA-256 rápido. Excepción aceptable: una sola contraseña de admin de ≥ 16
  caracteres aleatorios comparada en tiempo constante, documentada como tal. · A04, V6, V11.
- **ACC-03 Autorización por recurso y rutas admin** `[TT]` · Denegar por defecto; cada lectura o
  escritura comprueba que el recurso es del usuario (evita IDOR: cambiar `?id=41` por `42`); rutas
  admin con rol verificado en servidor. · A01, V8.
- **ACC-04 Sesión y cookies** `[auto][TT]` · Cookie `HttpOnly; Secure; SameSite=Lax|Strict`,
  caducidad acotada, firmada (HMAC) o token opaco; cerrar sesión la invalida. · A07, V7.
- **ACC-05 Recuperación de cuenta** `[TT]` · Enlaces de un solo uso que caducan (≤ 30-60 min), no
  revelan si el correo existe; MFA en cuentas de admin. · A07, V6.
- **ACC-06 Reglas por fila en la base de datos** `[TT: "protege mi base de datos"]` · Supabase:
  RLS activo en TODA tabla expuesta, políticas por operación con `auth.uid()`; la clave
  `service_role` jamás en cliente. Firebase: reglas sin `allow read, write: if true`. · Por qué: la
  clave pública viaja en la app; sin RLS cualquiera lee todo (CVE-2025-48757: 303 endpoints expuestos en 170 proyectos Lovable). · A01, V8.

## INP · Entradas y salidas

- **INP-01 Validar en servidor** `[TT]` · Esquema (zod/pydantic) con tipos, rangos y listas
  permitidas en cada endpoint; la validación del formulario es solo comodidad. · A05/A06, V2.
- **INP-02 Consultas parametrizadas** `[auto: pista][TT]` · Nunca concatenar texto del usuario en
  SQL/NoSQL; usar parámetros u ORM. · A05, V1.
- **INP-03 XSS** `[auto: pista][TT]` · Pintar datos con `textContent`, no `innerHTML`; si hay que
  pintar HTML, DOMPurify; CSP como segunda red. · Por qué: el script inyectado roba la sesión o
  actúa como el usuario. Es el fallo n.º 1 del código IA (86 %, Veracode). · A05, V1, V3.
- **INP-04 Subida de archivos** `[TT]` · Tipo por "magic bytes" y lista permitida, tamaño máximo,
  nombre aleatorio, guardado fuera de la web pública o en bucket privado con URL firmada; nunca
  servir SVG/HTML subidos desde tu dominio. · A05/A06, V5.
- **INP-05 SSRF, redirecciones y rutas** · Si el servidor descarga URLs del usuario: lista de
  dominios permitidos y bloqueo de IPs internas/metadata; redirecciones solo a rutas propias; nada
  de `../` en nombres de archivo. · A01/A05, V5, V15.

## WEB · Navegador y transporte

- **WEB-01 HTTPS + HSTS** `[auto][TT]` · Todo por HTTPS, HTTP redirige, HSTS largo (Vercel lo pone). · A04, V12.
- **WEB-02 Cabeceras de seguridad** `[auto][TT]` · CSP (`default-src 'self'`, `object-src 'none'`,
  `frame-ancestors`), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
  Plantilla en `stack-vercel.md`. · A02, V3.
- **WEB-03 CORS restringido** `[auto][TT]` · Nunca `*` en respuestas con datos o credenciales;
  Vercel pone `*` por defecto en estáticos. · A01/A02, V3/V4.
- **WEB-04 CSRF** `[TT]` · Cookies `SameSite=Lax/Strict` + comprobar `Origin` (o token) en
  POST/PUT/DELETE. · Por qué: otra web haría que tu navegador logueado ejecute acciones. · A01, V3.
- **WEB-05 Scripts de CDN con SRI** `[auto]` · `integrity=` + `crossorigin`, o servirlos desde el
  propio dominio. · Por qué: si el CDN cae en manos ajenas, su código corre en tu web. · A03/A08, V3.

## ABU · Abuso y lógica de negocio

- **ABU-01 Límite de peticiones** `[auto: pista en login][TT]` · Login, registro, recuperación, IA
  y endpoints caros: por IP y por cuenta, respuesta 429, bloqueo progresivo. (Vercel Firewall/WAF
  o Upstash ratelimit.) · A06/A07, V2/V6.
- **ABU-02 Precios y pagos en servidor** `[TT]` · El servidor busca el precio por ID; webhooks con
  firma verificada; idempotencia; el estado "pagado" solo lo cambia el webhook. · A06/A08, V2.
- **ABU-03 Lógica autoritativa** · Puntuaciones, monedas, premios, cupos: los calcula o valida el
  servidor. Sin servidor = no hay ranking global creíble. · A06, V2, GSF.
- **ABU-04 Topes de gasto** · Límite diario por usuario y global en APIs pagadas (IA, SMS, correo),
  alertas de facturación. · Por qué: "denial of wallet": un bucle te cuesta cientos de dólares. · LLM10, V2.

## CFG · Configuración y despliegue

- **CFG-01 Producción sin depuración** `[auto][TT]` · Debug apagado, errores genéricos sin stack,
  sin source maps públicos, sin cabeceras de versión. · A02, V13/V16.
- **CFG-02 Archivos expuestos** `[auto][TT]` · `.env`, `.git/`, respaldos `.bak`, notas `.md`
  internas, `data/` sin login, carpetas de herramientas: 404. En Vercel, `.vercelignore`. · A02, V13.
- **CFG-03 Entornos separados y previews protegidos** · Claves distintas por entorno; previews de
  Vercel con Deployment Protection; nada de datos reales en preview. · A02, V13.
- **CFG-04 Fallar cerrado** · Si la verificación lanza error, se deniega (no se deja pasar); todos
  los `catch` de auth devuelven 401/500 sin filtrar detalles. · A10, V16.

## SUP · Cadena de suministro

- **SUP-01 Dependencias vulnerables al día** `[auto][TT]` · `npm audit --omit=dev` sin altas/críticas;
  Dependabot o revisión mensual. · A03, V15.
- **SUP-02 Lockfile, sin paquetes sobrantes, sin paquetes alucinados** `[auto: lockfile][TT]` ·
  Lockfile commiteado; quitar lo no usado (`npx depcheck`); antes de instalar un paquete que sugirió
  la IA, verificar que existe, su dueño, descargas y antigüedad (slopsquatting). · A03, V15.
- **SUP-03 Skills, MCP y plugins de terceros auditados** · Nada se instala sin leer SKILL.md y
  scripts (36 % de skills muestreadas con inyección de prompt, Snyk 2026) → auditoría de terceros (ver `supply-chain-secretos.md`). · A03, LLM03.

## MON · Vigilancia y respuesta

- **MON-01 Registro de actividad sospechosa** `[TT]` · Logins fallidos, ráfagas de 401/403/429,
  cambios de rol; sin registrar contraseñas, tokens ni datos personales. · A09, V16.
- **MON-02 Alertas y plan de incidente** · Quién se entera y qué hace: rotar claves, invalidar
  sesiones, redesplegar, avisar. Una página. · A09, V16.
- **MON-03 Probar y reportar** `[TT]` · Re-test de cada arreglo e informe "encontrado → arreglado →
  probado → pendiente". Sin re-test no se cierra. · ASVS como lista de verificación.

## IA · IA dentro de la app (solo si la app usa un modelo)

- **IA-01 Inyección de prompt** · El texto de usuarios, webs o archivos es dato, nunca instrucción;
  herramientas del agente con mínimo privilegio y confirmación humana para acciones con efecto. · LLM01/LLM06.
- **IA-02 Salida del modelo no confiable** · No pintar como HTML ni ejecutar lo que devuelve el
  modelo sin validar/sanitizar; esquemas para salidas estructuradas. · LLM05.
- **IA-03 Nada sensible en el prompt de sistema** · Asumir que el prompt se filtrará; sin claves,
  sin reglas de autorización ahí; minimizar datos personales enviados. · LLM02/LLM07.

## GAM · Juegos web

- **GAM-01 Decidir qué es autoritativo** · Un juego para un jugador sin servidor acepta que el
  jugador puede hacerse trampa a sí mismo; NO se publica ranking global, economía real ni premios
  sin validación en servidor. · GSF §1.3, A06.
- **GAM-02 Guardados robustos** · Al cargar, validar versión y esquema; datos corruptos o editados
  no rompen el juego (valores por defecto); sin datos personales en localStorage. · GSF, V2/V14.
- **GAM-03 Ganchos de desarrollo fuera de producción** · Trucos, objetos de depuración globales (`window.__DEBUG__`), niveles de
  prueba: solo en dev/e2e (un chequeo en CI que falle si el build de producción los contiene). · A02, GSF.
- **GAM-04 Embebido en portales** · `frame-ancestors` con la lista exacta de portales (itch.io,
  CrazyGames) en vez de `*` o `'none'`; `postMessage` con `origin` verificado. · A02, V3.
- **GAM-05 Service worker** · Alcance mínimo, sin cachear respuestas privadas, versión para forzar
  actualización (un SW roto deja a los jugadores con un build viejo). · A08, V3.
- **GAM-06 SDKs de analítica y anuncios** · Solo claves públicas de cliente; consentimiento donde
  aplique; cuidado con datos de menores (COPPA/RGPD); SDK desde fuente oficial con versión fija. · A03, V14.

## PRI · Privacidad

- **PRI-01 Minimizar y proteger datos personales** · Salud, GPS, finanzas o "contexto de vida" solo
  tras login; nada personal en notas, respaldos o JSON públicos; retención definida. · A01/A02, V14.

## Automatización (qué cubre el escáner)

Directo (16 de 44 = 36 %): SEC-01, SEC-02, SEC-03, ACC-01 (pista), ACC-04, INP-02 (pista),
INP-03 (pista), WEB-01, WEB-02 (incluye anti-clickjacking, base de GAM-04), WEB-03, WEB-05,
ABU-01 (pista), CFG-01, CFG-02 (+ restos desplegados con `all`), SUP-01, SUP-02 (lockfile).
El resto (64 %) es revisión manual guiada por este catálogo: lógica de negocio, reglas de BD,
pagos, IA y diseño no se detectan con patrones.

## Trazabilidad con la checklist de Revolutia.ai (27 pedidos)

Autenticación→ACC-01 · claves API fuera del navegador→SEC-01 · base de datos→ACC-06 · HTTPS→WEB-01 ·
hash→ACC-02 · validación en servidor→INP-01 · XSS→INP-03 · actividad sospechosa→MON-01 · rutas
admin→ACC-03 · consultas parametrizadas→INP-02 · variables de entorno→SEC-02 · límite de
peticiones→ABU-01 · CORS→WEB-03 · cabeceras→WEB-02 · cookies→ACC-04 · CSRF→WEB-04 · enlaces de
recuperación→ACC-05 · archivos subidos→INP-04 · precios y pagos→ABU-02 · debug→CFG-01 ·
dependencias→SUP-01 · paquetes sin uso→SUP-02 · archivos expuestos→CFG-02 · secretos en Git→SEC-03 ·
rotar claves→SEC-04 · revisión a fondo→Paso 3 · probar e informar→MON-03. 27/27.
