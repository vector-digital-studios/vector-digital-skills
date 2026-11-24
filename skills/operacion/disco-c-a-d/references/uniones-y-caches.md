# Qué mover, cómo, y qué no

## Unión (junction) vs. variable de entorno

| Situación | Mejor opción | Por qué |
|---|---|---|
| Proyecto o carpeta de datos con rutas escritas en scripts, tareas o configuraciones | **Unión** (`disco.py mover`) | La ruta vieja sigue funcionando sin tocar nada |
| Caché de una herramienta que respeta una variable (npm, pip, uv, HF, torch, Playwright, Yarn, NuGet, Gradle, Cargo, Go, conda) | **Variable de usuario** (`disco.py caches`) | Es el mecanismo oficial; sobrevive a reinstalaciones |
| Caché grande que no quieres volver a descargar | Variable **y** `mover` del contenido viejo a la ruta nueva | Ni re-descarga ni ruta rota |
| Carpetas de usuario (Documentos, Vídeos, Descargas) | Propiedades > Ubicación de Windows | Windows lo soporta y actualiza el registro |
| Distribuciones de WSL | `wsl --export` / `wsl --import` | El disco virtual vive en `AppData\Local\Packages`; una unión lo rompe |
| OneDrive | «Liberar espacio» (solo en la nube) | Mover la carpeta sincronizada la desconecta |
| Windows, Program Files, ProgramData | Liberador de espacio / desinstalar | Nunca a mano |

Las uniones no requieren administrador, funcionan para cualquier programa (son transparentes para el sistema de
archivos) y solo enlazan carpetas locales. Eliminar una unión (`rmdir`) no toca el contenido del destino.

## El procedimiento de `mover` (y por qué cada paso)

1. **Validar**: origen existe y no es ya una unión; no es una ruta protegida; destino vacío; hay espacio con
   margen (5 % + 0,5 GB); la terminal no está dentro del origen.
2. **Probar bloqueo**: renombrar y deshacer. Si falla, un programa la tiene abierta: se para antes de copiar.
3. **Copiar** con `robocopy /E /COPY:DAT /DCOPY:DAT /XJ` (o con `copytree` preservando enlaces si hay symlinks
   dentro). Código de robocopy ≥ 8 = errores.
4. **Verificar**: mismo número de archivos, mismos bytes y MD5 idéntico de una muestra (los 5 mayores + 40 al
   azar) o de todo con `--md5-todo`.
5. **Renombrar** el original a `*.__migrando` (si falla aquí, todo sigue como estaba).
6. **Crear la unión** en la ruta original y **leer a través de ella**: el recuento debe coincidir.
7. **Borrar** el original renombrado (o conservarlo con `--conservar-original`).

Cualquier fallo en los pasos 3-6 deshace lo hecho: quita la unión, devuelve el nombre al original y, si la copia
quedó a medias, la limpia. Si el fallo ocurre en el paso 7 (un archivo en uso), **no** se deshace nada: la
migración está completa y solo quedan restos que el usuario borra después.

## Hugging Face y enlaces simbólicos

La caché `hub` de Hugging Face puede guardar los snapshots como enlaces simbólicos a blobs. `robocopy /MOVE`
mueve primero los blobs y luego copia los enlaces colgando como archivos vacíos: el modelo queda «incomplete».
`disco.py mover` detecta enlaces internos y copia con `copytree(symlinks=True)`; crear symlinks en Windows exige
modo desarrollador o administrador. Sin ese permiso, el paso falla y se deshace solo; alternativa limpia: fijar
`HF_HOME` en la otra unidad y volver a descargar los modelos que se usen.

## Variables de caché

`disco.py caches --destino D:\caches` propone una subcarpeta por herramienta y, con `--aplicar`, las escribe en
`HKCU\Environment` (sin administrador) y avisa al sistema (`WM_SETTINGCHANGE`). Las terminales ya abiertas no
las ven. `TEMP`/`TMP` solo con `--incluir-temp`: algunos instaladores esperan el temporal en C:.

Equivalente manual: `setx NOMBRE "D:\caches\subcarpeta"` en una terminal normal.

## Deshacer

`disco.py revertir <ruta_union> --aplicar` copia de vuelta, verifica el recuento y los bytes, sustituye la unión
por la carpeta real y **deja intacta** la copia en la otra unidad (bórrala tú cuando lo compruebes).
