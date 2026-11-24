# Ejemplo de registro que el validador rechaza (inventado)

Contramedidas sin causa, impacto sin cifra y un PASS sin verificación.
Prueba: `python scripts/capa.py validar templates/ejemplo-rechazado.md` → código 1.

## AC-008: El despliegue falla a veces
- Qué: el despliegue falla a veces
- Cuándo: a veces
- Dónde: CI
- Impacto: mucho
- Recurrencia: no sé
- Correctiva: reintentar el job
- Preventiva: subir el timeout
- Gate: PASS
