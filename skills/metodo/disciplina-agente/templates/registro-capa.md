# Registro de lecciones (plantilla + ejemplo inventado)

Un archivo por equipo o proyecto. Una entrada `## AC-<n>` por incidente. Antes de investigar un fallo,
busca aquí: si ya ocurrió, la contramedida anterior no bastó.

Valida con: `python scripts/capa.py validar registro-capa.md`

---

## AC-007: La exportación CSV tarda 42 s y da 504
- Qué: el endpoint /export devuelve 504 Gateway Timeout
- Cuándo: con informes de más de 5 000 filas, desde el despliegue v2.14 del 2026-11-03
- Dónde: servicio de exportación, función build_csv
- Impacto: 12 exportaciones fallidas al día y ~30 min diarios de soporte
- Recurrencia: primera vez (búsqueda en el registro y en los changelogs sin coincidencias)

### Porqués
1. La petición supera el tiempo máximo de 30 s del proxy — evidencia: log del proxy, 504 a los 30,0 s
2. build_csv tarda 42 s con 10 000 filas — evidencia: perfil local con el fixture de 10 000 filas
3. Hace una consulta por fila para leer sus items (10 001 consultas) — evidencia: contador de consultas del ORM
4. La v2.14 quitó el prefetch al refactorizar el serializador — evidencia: diff del commit de v2.14, línea 88
5. No hay prueba de rendimiento que cubra la exportación — evidencia: la suite no tiene casos de más de 50 filas

- Causa raíz: el refactor eliminó el prefetch y ninguna prueba mide el número de consultas de la exportación
- Clase: 7
- Validación inversa: con prefetch hay 2 consultas → build_csv tarda 2,8 s → no supera 30 s → no hay 504
- Correctiva: restaurar el prefetch en build_csv y reprocesar las 12 exportaciones del día
- Preventiva: prueba que falla si la exportación de 10 000 filas hace más de 5 consultas
- Detección: alerta si el p95 de /export supera 10 s durante 15 min
- Contra-métrica: exportaciones fallidas al día de 12 a 0, medir el 2026-12-08
- Verificación: suite completa en verde; fixture de 10 000 filas en 2,8 s; 0 errores 504 en 48 h
- Gate: PASS
- Lección: un refactor de serializador puede reintroducir N+1; quedó como advertencia en la guía del servicio

