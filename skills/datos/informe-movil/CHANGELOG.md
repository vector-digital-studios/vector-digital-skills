# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-24

Primera versión pública. Deriva del motor de informes interno en uso diario desde el 4-nov-2026
(134 informes en 20 días).

### Añadido
- CLI única: `python scripts/informe.py entrada.md -o salida.html [--tema] [--vista] [--modo] [--sellar|--previo]`.
- Temas por variables CSS en `scripts/temas/`: `neutro` (por defecto), `carbon` (carbón/naranja), `menta`
  (la paleta original) y temas propios por ruta (`--tema mi-tema.css` o `INFORME_TEMA`). Los tres pasan el
  sello con los tres ejemplos.
- Detección de Chrome/Chromium/Edge en Windows, macOS y Linux, caché de `@puppeteer/browsers` y `CHROME_PATH`.
- `scripts/autoprueba.py`: construye los 3 ejemplos con los 3 temas, comprueba que son autocontenidos y que
  el contenido está íntegro; sella con Chrome si está disponible y lo salta avisando si no.
- `references/formato.md` (31 bloques) y ejemplos con datos inventados: negocio, técnico e investigación.
- El sello se guarda junto al HTML (`<salida>.sello.json`) y se reutiliza mientras no cambie la huella.

### Cambiado
- El botón de la portada dice «N decisiones pendientes» (antes, en primera persona del agente).
- La cifra grande del veredicto ya no se parte («+18 %» en una línea).
- El separador « · » del título no queda al principio de una línea.
- La prueba de «tabla ordenable» ya no falla cuando los datos vienen ordenados de origen.
- La prueba del botón de decisiones espera un segundo más antes de dar el salto por fallido (fallaba con la máquina cargada).
- Una cifra larga dentro del anillo del veredicto («99,92 %») se achica para no pisar el trazo.
- Línea de enlaces del sello: «Sin enlaces que revisar» cuando no hay ninguno; decimales con coma.

### Quitado (respecto del motor interno)
- Biblioteca de carpetas por día, índice, limpieza y «estrella».
- Conversor de especificaciones JSON antiguas y reenvío al motor clásico.
- Rutas fijas de Windows, textos y paleta de marca propios.
