---
name: v-drop
description: Usar para pasar archivos entre celular y PC por tu WiFi, sin nube
version: 2.0.0
license: MIT
---

# V Drop — compartir archivos por tu propia red

Servidor diminuto (solo librería estándar de Python + JavaScript puro) que convierte un PC en un "AirDrop"
casero: desde el celular se abre una URL y los archivos viajan por el WiFi de la casa, sin nube ni cuentas.

## Cuándo usarla
- El usuario quiere pasar fotos, videos o documentos entre el celular y el PC (o entre dos equipos) sin cables.
- No quiere subir los archivos a ninguna nube.

## Cómo levantarla
1. `python server.py` (puerto 8080; otro con `--port N` o la variable `ALFRED_PORT`).
2. El servidor imprime la URL de la red local; abrirla en el celular (mismo WiFi).
3. En Windows, si el celular no conecta, ejecutar `firewall-admin.bat` como administrador una vez.
4. Los archivos recibidos quedan en `uploads/`. El acceso usa un token guardado en `data/token.txt`.

## Límites
- Solo red local de confianza; no exponer el puerto a internet.
- Tope de 10 GB por archivo.

## Prueba
`python scripts/autoprueba.py` levanta el servidor en un puerto libre y corre la prueba de humo completa
(subida, presencia, aceptar/rechazar) sin red externa.
