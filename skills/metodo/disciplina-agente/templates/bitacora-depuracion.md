# Bitácora: la exportación CSV tarda 42 s con 10 000 filas
Checkpoint: rama fix/export-lento desde el commit a1b2c3d (sha256 del build_csv original anotado)

### Paso 1
- Hipótesis: el cuello está en escribir el CSV a disco
- Cambio: escribir en memoria con io.StringIO en lugar de archivo temporal
- Medida: 42,1 s → 41,8 s con el fixture de 10 000 filas
- Resultado: refuta
- Revertido: sí

### Paso 2
- Hipótesis: la consulta hace una lectura por fila (N+1)
- Cambio: añadir prefetch de items en la consulta de build_csv
- Medida: consultas 10 001 → 2; tiempo 42,1 s → 2,8 s
- Resultado: confirma
- Revertido: n.a.

### Paso 3
- Hipótesis: el arreglo no rompe otros formatos de exportación
- Cambio: ninguno (solo correr la suite de exportación completa)
- Medida: 148 pruebas, 148 en verde
- Resultado: confirma
- Revertido: n.a.
