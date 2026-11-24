# Changelog — disco-c-a-d

## 1.0.0 — 2026-11-24

Primera versión pública. Reescritura genérica de las herramientas con las que se auditó y migró un equipo real
(oct-nov 2026: 25 carpetas, 7,2 GB y ~23 000 archivos movidos de C: a D: con unión, sin fallos).

- `auditar`: recorrido único sin seguir uniones; reparto exacto por categoría; archivos de sistema de la raíz;
  separación de archivos «solo en la nube»; cuadre con el espacio usado; filtro `--desde`; JSON + informe HTML.
- Informe HTML autocontenido (sin CDN ni JS), móvil primero, con el porqué de cada carpeta, cachés de
  herramientas, uniones (incluidas las rotas), «lo que NO se debe tocar» y rutas del perfil enmascaradas.
- `mover`: simulación por defecto; confirmación escrita; prueba de bloqueo; robocopy o copia que preserva
  enlaces; verificación por recuento, bytes y MD5; unión verificada leyendo a través de ella; deshacer
  automático ante cualquier fallo; registro JSONL.
- `revertir`, `caches` (13 herramientas: npm, pip, uv, Hugging Face, PyTorch, Playwright, Yarn, NuGet, Gradle,
  Cargo, Go, conda, TEMP opcional) y `verificar`.
- Rechazo de rutas protegidas (Windows, Program Files, raíz de perfil, AppData entero, apps de la Tienda/WSL,
  OneDrive).
- Autoprueba de 57 comprobaciones con fallos inyectados.
- Probada contra un disco real de 476 GiB (1,67 millones de archivos): cuadre del 91 % sin administrador. Se
  corrigió durante esa prueba un doble conteo (enlaces duros de Windows y `pagefile.sys`) que daba un 107 %.
- Mejoras verificables frente a las herramientas originales: sin rutas ni listas de carpetas fijas; el mover de
  cachés original usaba `robocopy /MOVE` (borra el origen mientras copia, sin verificar) y ahora se copia,
  verifica y solo entonces se borra; se añade MD5 a la verificación (antes solo recuento y bytes); los puntos de
  reanálisis de OneDrive ya no se confunden con uniones; nuevos `revertir`, `verificar` e informe HTML.
