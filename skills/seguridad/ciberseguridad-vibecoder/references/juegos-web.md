# Juegos web — seguridad proporcional

Para juegos HTML5 (Phaser, PixiJS, Three.js; Vite/TypeScript) publicados en Vercel, itch.io o
portales como CrazyGames.

## Principio: el cliente no es de confianza (OWASP GSF §1.3)
Todo lo que corre en el navegador del jugador se puede leer y cambiar. La pregunta no es «¿se puede
hacer trampa?» (siempre se puede) sino «¿a quién perjudica?»:

| Situación | Riesgo | Qué hacer |
|---|---|---|
| Un jugador, offline | Se hace trampa a sí mismo | Aceptarlo; no gastar en antitrampas |
| Ranking global o logros públicos | Rankings falsos | El servidor valida (repetición de partida, límites físicos, firma de sesión) o no hay ranking |
| Monedas compradas o premios | Fraude económico | Servidor autoritativo + pagos verificados (ABU-02) |
| Multijugador | Trampas contra otros | Servidor autoritativo de movimiento, daño e inventario |

## Controles concretos
- **GAM-02 Guardados**: `try/catch` al parsear, campo `version` con migraciones, validar rangos (vida
  ≤ máximo, nivel existente); si falla, valores por defecto y nunca una pantalla rota. Sin email ni
  nombre real en `localStorage`. Probar con un guardado corrupto en los tests.
- **GAM-03 Ganchos de desarrollo**: trucos, objetos globales de depuración y selectores de nivel por
  URL solo en desarrollo; un chequeo en CI que falle si el build de producción los contiene.
- **GAM-04 Portales**: en tu propio hosting, `frame-ancestors` con la lista exacta de portales donde
  se embebe (o `'none'`); si se usa `postMessage` con el SDK del portal, comprobar `event.origin`.
- **GAM-05 Service worker**: versión en el nombre de la caché, alcance limitado a la carpeta del
  juego, nunca cachear respuestas privadas.
- **GAM-06 SDKs de analítica y anuncios**: solo claves públicas de cliente, versión fija, y revisar la
  política de datos de menores antes de activar analítica en portales con público infantil.
- **Cadena de suministro**: lockfile + `npm audit`; assets y librerías con su licencia registrada.

## Puerta pre-lanzamiento (P3)
1. `vd_sec_scan.py repo <ruta> --history --npm-audit --perfil P3` → 0 críticos/altos.
2. CI en verde, con el chequeo de ganchos de desarrollo.
3. Build de producción sin `.map` públicos ni rutas de depuración.
4. Guardado corrupto probado.
5. Con URL de prueba: `vd_sec_scan.py url <url>`; `frame-ancestors` según el destino.
