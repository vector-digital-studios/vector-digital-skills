# Auditoría después de cada corrida

Una corrida solo sirve para decidir si pasa esta lista. Si no, se conserva etiquetada como inválida (con
su motivo) y no se compara con nada.

## Validez de la corrida

1. La ventana **efectiva** (la que informa el motor tras el calentamiento) coincide exactamente con el
   intervalo semiabierto aprobado.
2. Los huecos reales siguen visibles en el DataFrame que recibe la estrategia y disparan el reinicio de
   estado pre-registrado (ningún relleno sintético silencioso).
3. Una re-ejecución idéntica produce el mismo libro de operaciones canonizado (mismo hash) y las mismas
   métricas de decisión. Si la aprobación cubría un número finito de corridas, no las gastes en repetir:
   marca la reproducibilidad como **no verificada**.

## Lo que se revisa

- **Estrategia y configuración embebidas** en el artefacto de salida = las congeladas (hash).
- **Mecánica de salida** auditada **antes** de mirar resultados: orden real stop / objetivo / salida
  personalizada en el motor instalado; precio de cierre exportado en casos límite (toque del objetivo,
  salto por encima del objetivo, stop y objetivo en la misma vela, objetivo y luego stop).
- **Riesgo inicial (R)** de cada operación reconstruido desde el stop congelado y el precio de entrada real,
  no desde campos de emergencia del motor.
- **Costos**: si se aplicó deslizamiento a posteriori sobre un libro fijo, etiquétalo como aproximado (con
  otros precios habrían cambiado tamaños y operaciones posteriores).
- **Exportaciones aisladas** por variante: exactamente un resultado en su carpeta; un archivo que aparece
  tarde tras una interrupción es huérfano hasta identificarlo por su contenido.
- **Señales no ejecutadas**: no inventes causas a partir de solapes o heurísticas; reconstruye la
  superficie de ejecución completa o márcalas «sin clasificar».

## Manifiesto inmutable de cada corrida

Hashes de estrategia/configuración/datos; versiones del motor y del lenguaje; instrumentos, marcos y fechas;
ventana efectiva y calentamiento; política de huecos; tramos y corte de la bóveda; parámetros y escenarios
de costo; métricas y referencia; PASA / FALLA / EVIDENCIA_INSUFICIENTE por compuerta; errores e intentos
invalidados. Ejecuta el formateo/lint **antes** de sellar el manifiesto (formatear después deja hashes
viejos). No sobrescribas corridas antiguas.

## Base congelada

Se protege por **hash de código fuente**, no por «los valores por defecto no cambiaron»: añadir parámetros
opcionales a módulos compartidos invalida la congelación. Los experimentos van en módulos o subclases
aisladas. Compara todos los hashes protegidos antes y después de cada trabajo experimental.

## Resúmenes para quien decide

Cada cifra que se comunica cita el documento canónico (y su manifiesto de hashes) **en el mismo mensaje**,
leída del artefacto final, no de memoria. Di explícitamente qué sigue cerrado (tramos, bóveda,
apalancamiento, capital real) mientras no haya autorización expresa.

## Recuperación tras una ejecución prematura

1. Parar y comprobar que no queda ningún proceso corriendo.
2. Decir exactamente qué corrió y qué no.
3. Etiquetar los resultados como exploratorios / inválidos para decidir.
4. Conservar o borrar artefactos según indique el responsable.
5. Tratar los periodos observados como **contaminados** para la reserva estricta (borrar no «des-ve»):
   reservar otro bloque disjunto o datos futuros, y documentar la contaminación.
6. Volver al cuestionario pendiente.
7. Obtener aprobación de la especificación antes de nuevo código o pruebas.
