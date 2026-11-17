# Glosario para informes (lenguaje llano)

Para informes dirigidos a personas no especialistas. Cada término: qué es + para qué importa.

- **Vibe coding**: programar pidiéndole a la IA lo que quieres sin revisar línea a línea. Rápido, pero la IA omite seguridad si no se le exige.
- **OWASP**: fundación sin fines de lucro que publica los estándares de seguridad web más usados. Su "Top 10" es la lista de los 10 riesgos más graves.
- **ASVS**: lista de verificación de OWASP (versión 5.0, 2025) con cientos de requisitos para comprobar que una app es segura. Es el "examen completo".
- **Superficie de ataque**: todo lo que un extraño puede tocar: páginas, archivos, formularios, APIs.
- **Clave de API / secreto**: contraseña que usa un programa para hablar con un servicio (OpenAI, Stripe). Si se filtra, otro la usa y tú pagas.
- **Variable de entorno**: lugar del servidor donde se guardan los secretos fuera del código.
- **Frontend / bundle**: el código que se descarga al navegador del visitante. Todo lo que está ahí es público.
- **Backend / función serverless**: código que corre en el servidor (en Vercel, carpeta `api/`). El visitante no lo ve.
- **Autenticación**: comprobar quién eres (login). **Autorización**: comprobar qué puedes hacer (ver solo tus datos).
- **Hash de contraseña**: transformar la contraseña en una huella irreversible. Si roban la base, no ven las contraseñas.
- **Cookie de sesión HttpOnly/Secure/SameSite**: la "pulsera" que te identifica tras el login; HttpOnly impide que un script la robe, Secure exige HTTPS, SameSite impide que otra web la use.
- **HTTPS / HSTS**: conexión cifrada / orden al navegador de usar siempre HTTPS.
- **XSS (Cross-Site Scripting)**: meter código malicioso en una página para que se ejecute en el navegador de otros (robar sesión, actuar como ellos).
- **CSRF (Cross-Site Request Forgery)**: una web ajena hace que tu navegador, ya logueado, ejecute acciones sin que lo sepas.
- **CORS**: regla que dice qué otras webs pueden leer las respuestas de tu servidor. `*` = cualquiera.
- **CSP (Content-Security-Policy)**: lista de lugares desde donde la página puede cargar código. Si alguien cuela un script, el navegador lo bloquea.
- **Clickjacking / frame-ancestors**: meter tu web invisible dentro de otra para que el usuario haga clic sin saberlo / la regla que lo impide.
- **Inyección SQL / consultas parametrizadas**: colar órdenes en la base de datos escribiendo texto especial / la técnica que lo hace imposible.
- **IDOR**: cambiar un número en la URL (`?id=42`) y ver datos de otra persona porque el servidor no verificó dueño.
- **RLS (Row Level Security)**: reglas en la base de datos para que cada usuario solo vea sus filas. Sin RLS, la clave pública de la app abre todo.
- **Rate limiting (límite de peticiones)**: tope de intentos por minuto. Frena a quien prueba miles de contraseñas o abusa de tu IA.
- **Webhook firmado**: aviso automático (p. ej. "pago aprobado") con firma que prueba que viene de Stripe y no de un impostor.
- **Source map**: archivo que reconstruye el código original legible a partir del código comprimido.
- **SRI (Subresource Integrity)**: huella que asegura que el script descargado de otro sitio no fue alterado.
- **Cadena de suministro**: las librerías y herramientas de otros que usa tu proyecto. Si una se contamina, tu app también.
- **Slopsquatting**: registrar con malware el nombre de un paquete que la IA "inventa" con frecuencia.
- **npm audit / lockfile**: revisión de librerías con fallos conocidos / archivo que congela las versiones exactas instaladas.
- **Inyección de prompt**: texto escondido (en una web, un PDF, un mensaje) que da órdenes a la IA de tu app.
- **Servidor autoritativo**: en juegos, el servidor decide lo que vale (puntos, daño), no el jugador.
- **Service worker**: programa del navegador que guarda el juego para que funcione sin conexión.
- **Falso positivo**: alarma que parece un fallo pero no lo es (se verifica a mano antes de reportar).
- **Severidad (crítico/alto/medio/bajo)**: cuánto daño causa si se explota y cuán fácil es.
- **Re-test**: volver a probar después de arreglar para confirmar que el fallo ya no existe.
