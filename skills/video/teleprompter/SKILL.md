---
name: teleprompter
description: Usar para grabar a cámara con un teleprompter por voz en el navegador
version: 0.6.0
license: MIT
---

# Teleprompter por voz (v0.6.0-beta, en construcción)

App web que desplaza el guion mientras hablas (Web Speech API), con modo manual a velocidad constante,
ventana "burbuja" siempre al frente en Windows y servidor local. Basada en
[jlecomte/voice-activated-teleprompter](https://github.com/jlecomte/voice-activated-teleprompter) (MIT).

## Cuándo usarla
- El usuario va a grabarse leyendo un guion (YouTube, curso, reel) y quiere que el texto lo siga.
- Hay que preparar un guion "formato teleprompter".

## Cómo levantarla
1. Requisitos: Chrome o Edge; Python 3.9+ para el servidor. `dist/` ya viene compilado: no hace falta Node
   salvo que se modifique el código (`npm ci && npm run build`).
2. Servir: `python server/servidor.py` (añadir `--lan` solo en redes de confianza) y abrir `http://localhost:8000`.
3. Windows, ventana siempre al frente: con el servidor corriendo, `windows\burbuja.cmd`
   (tamaño/posición con `TP_ANCHO`, `TP_ALTO`, `TP_X`, `TP_Y`).
4. En la app: **Editar** → pegar guion → **Editar** → elegir **Voz** o **Manual** → **Iniciar**.

## Preparar el guion para el usuario
- Texto plano, una idea por línea; cada salto de línea es una micro-pausa de lectura.
- Indicaciones de grabación entre corchetes: `[mirar a cámara]`, `[pausa]`. Se ven, pero no se escuchan.
- Nada de tablas, viñetas ni notas técnicas dentro del guion; las notas van aparte.
- Escribir números como se dicen ("veinte por ciento") para que el reconocimiento no se pierda.

## Límites
- Reconocimiento solo en español en esta versión; sin modo espejo (vuelven en la hoja de ruta a 1.0).
- La voz solo funciona en `localhost` o `https://`; por `http://<IP>` de la red, solo modo manual.
- Modo burbuja solo en Windows 10/11.

## Prueba
`python scripts/autoprueba.py` verifica que la app compilada está completa y corre las pruebas del servidor
(sin red ni micrófono).
