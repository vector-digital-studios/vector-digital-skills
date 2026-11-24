# Higiene de datos

Aplica a cualquier cifra que respalde una conclusión (impacto de un incidente, contra-métrica, «mejoró
un 40 %»).

1. **Reporta lo descartado.** Cada fila o dato excluido, con el motivo.
2. **Declara denominadores y fechas de corte** de cada ratio.
3. **No promedies ratios**: recalcula desde las sumas (la media de porcentajes de grupos de distinto
   tamaño miente).
4. **Revisa las unidades** antes de comparar (ocurrencias vs minutos vs dinero; ms vs s).
5. **Normaliza por exposición** antes de comparar entidades (por usuario, por despliegue, por hora).
6. **Compara contra no hacer nada**: ¿cuánto habría cambiado la métrica sin la intervención?
7. **Separa ruido de tendencia**: compara contra una línea base móvil (p. ej. 8 semanas), no solo contra
   el periodo anterior.
8. **Recalcula la cifra principal desde los datos crudos** justo antes de presentarla. Si no coincide,
   no se entrega: se investiga la diferencia (no se esconde en una nota al pie).
