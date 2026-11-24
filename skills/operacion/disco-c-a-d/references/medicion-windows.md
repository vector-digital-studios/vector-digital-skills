# Medir bien un disco en Windows

Lo que sigue salió de auditar y migrar un equipo real. Cada punto evita un error que ya ocurrió.

## Fuentes de verdad

| Qué | Fuente buena | Fuente mala |
|---|---|---|
| Espacio libre de una unidad | `shutil.disk_usage` / `Win32_LogicalDisk.FreeSpace` | `df -h` de Git Bash: tras borrar cientos de GB puede seguir mostrando el valor previo |
| Tamaño de un árbol | suma de bytes con `os.scandir` (lo que hace `disco.py`) | `du -sm` (MiB, no MB: infla ~2,4 % si se etiqueta como GB) |
| Duplicados | MD5 idéntico | mismo nombre y mismo tamaño |

## Lo que un escaneo de carpetas no ve

- `pagefile.sys`, `hiberfil.sys`, `swapfile.sys` en la raíz: pueden sumar decenas de GB. `auditar` los mide aparte.
- Instantáneas de volumen y puntos de restauración (`System Volume Information`): sin permiso de lectura.
- Carpetas de otros usuarios o del sistema sin permiso: se cuentan como «sin permiso» en el resumen.

Por eso el informe muestra el **cuadre**: lo medido frente a lo usado. Si queda por debajo del 90 %, el
diagnóstico está incompleto; repetir como administrador o medir esas zonas por otra vía antes de opinar.

## Uniones, enlaces y nube

- Una unión (junction) o un enlace simbólico apuntan a otro sitio: si el recorrido los sigue, cuenta dos veces lo
  que ya se movió. `disco.py` no los sigue y los lista aparte (y marca los ROTOS).
- Las carpetas de OneDrive son puntos de reanálisis de otro tipo (nube): sí se recorren, pero los archivos
  marcados «solo en línea» (`OFFLINE`, `RECALL_ON_DATA_ACCESS`) no ocupan disco y se suman aparte.
- Se distingue por la etiqueta de reanálisis (`IO_REPARSE_TAG_MOUNT_POINT` = unión, `IO_REPARSE_TAG_SYMLINK`),
  no por el atributo genérico: así una unión rota también se reconoce como unión.

## Errores de diagnóstico frecuentes

- **Salida vacía no es «pesa poco».** Un `find`/`du` profundo que se cuelga devuelve nada; si se interpreta como
  cero, desaparecen ramas enteras del análisis. Toda medición debe devolver contenido o repetirse.
- **Un solo archivo puede parecer una carpeta entera**: una grabación gigante mal cerrada. Cuenta archivos.
- **La fecha del padre no dice nada de los hijos**: mide la última actividad de cada candidato por separado.
- **Rutas con acentos** pasadas por varias capas de shell pueden corromperse y medir otra carpeta con nombre
  parecido. Lista con un patrón amplio y confirma la ruta real.
- **«No se usa» se comprueba en los artefactos.** Buscar referencias solo en scripts y skills dio una vez «nadie
  usa esta biblioteca» cuando los manifiestos de los proyectos tenían cientos de referencias vivas.

## Lo que el informe responde

1. ¿Cuánto queda libre y en qué unidad?
2. ¿Qué lo llena, por tipo (dona) y por carpeta (las que de verdad explican el espacio, sin dobles conteos)?
3. ¿Por qué está ahí cada cosa y qué se puede hacer con ella?
4. ¿Qué cachés de herramientas viven aún en C:?
5. ¿Qué se movió ya (uniones) y si alguna está rota?
6. ¿Qué NO se debe tocar?
