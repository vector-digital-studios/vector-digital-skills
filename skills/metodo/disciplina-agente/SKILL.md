---
name: disciplina-agente
description: "Usar para buscar la causa raíz, depurar por pasos y hacer cambios mínimos"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [debugging, root-cause, capa, 5-whys, ishikawa, minimal-diff, agent-discipline, spanish]
  idioma: es
  requiere: "Nada para el método. Python 3 (solo biblioteca estándar; probado con 3.11, 3.12 y 3.14) para scripts/capa.py."
---

# Disciplina del agente

Tres hábitos en un solo ciclo para que un agente de programación no arregle a ciegas:
**(1) encontrar la causa antes de tocar nada, (2) avanzar por pasos medibles, (3) cambiar lo mínimo y
probarlo.** Funciona con cualquier agente que lea SKILL.md (Claude Code, Codex, Hermes Agent).

## Cuándo activarla

Aplica el ciclo completo si se cumple al menos una condición:

- El fallo se repite, o ya hubo 2 intentos de arreglo que no funcionaron.
- Hay 3 o más arreglos posibles para el mismo síntoma y no está claro cuál es.
- Cada prueba es cara (minutos de render, despliegue, suite larga).
- El incidente tiene impacto medible (tiempo, dinero, usuarios, datos).
- Alguien propone «un parche rápido» bajo presión.
- El usuario pide «por pasos», «paso a paso», «causa raíz» o «sin romper nada».

Para un error trivial y evidente (una errata con mensaje claro) basta la regla de cambios mínimos.

## El ciclo (en orden, sin saltarse fases)

1. **Definir el problema.** Qué (observable), cuándo, dónde, impacto con número y unidad.
   «Está lento» no es un problema; «la exportación tarda 42 s con 10 000 filas, antes 3 s» sí.
2. **Contener.** Si hay daño en curso, una acción acotada y reversible que pare el sangrado (desactivar,
   volver a la versión anterior). Contener no es arreglar: queda anotado como provisional.
3. **Checkpoint.** Copia el último estado que funcionaba (commit, rama o copia de archivo) y anota cómo
   volver a él. Sin checkpoint no se toca nada.
4. **¿Es repetido?** Busca el síntoma en el registro de lecciones, el historial y los changelogs. Si ya
   pasó, la contramedida anterior falló: esa es tu primera evidencia, no la repitas.
5. **Reproducir y aislar con la prueba más barata.** Un caso mínimo que falle siempre; una sola variable.
6. **Hipótesis → experimento → medida.** De 3 a 5 hipótesis falsables («si X es la causa, al cambiar Y
   veré Z»), ordenadas por probabilidad y costo de probarlas. Una a la vez. Anota cada paso en la bitácora.
7. **Causa raíz con evidencia.** Cadena de porqués donde cada respuesta cita evidencia (log, línea, dato,
   captura). Si falta evidencia, la cadena se detiene ahí: no se rellena con suposiciones. Valídala en
   reversa: «si corrijo la causa, cada eslabón deja de ocurrir».
8. **Cambio mínimo + prueba.** El diff más pequeño que ataca la causa (no el síntoma), con una prueba que
   fallaba antes y pasa después. Un cambio por vez; si falla, **revertir antes del siguiente**.
9. **CAPA.** Correctiva (lo de hoy), preventiva (lo que impide que vuelva) y detección (el check que avisa
   si la prevención falla), más una contra-métrica con número y fecha de nueva medición.
10. **Verificar eficacia y cerrar.** Prueba integral, un intento adversarial de romperlo (idealmente otro
    agente sin contexto previo) y la lección registrada donde la próxima persona la encontrará.

**Regla de corte:** tras 3 arreglos fallidos seguidos, detente. No intentes un cuarto: el problema es de
diseño o de comprensión, vuelve a la fase 5 o revisa la arquitectura.

## Reglas que no se negocian

- No proponer contramedidas antes de tener una causa con evidencia.
- No apilar parches: cada cambio fallido se revierte.
- No declarar «arreglado» sin la salida real de una prueba (código de salida, log, captura, cifra).
- No ampliar el alcance: lo que no pide la tarea no se reformatea, ni se renombra, ni se «mejora».
- Las cifras se recalculan desde los datos crudos antes de presentarlas.

## Herramienta: `scripts/capa.py`

Valida que un registro de incidente y una bitácora de depuración tengan lo que el método exige.

```bash
python scripts/capa.py nuevo AC-001 "Título corto" > incidente.md   # plantilla vacía
python scripts/capa.py validar incidente.md                         # ¿registro CAPA completo?
python scripts/capa.py bitacora depuracion.md                       # ¿cada paso tiene hipótesis y medida?
python scripts/capa.py validar incidente.md --json                  # salida para otro programa
```

Código de salida: `0` válido, `1` con errores, `2` uso incorrecto. Detecta, entre otros:
`ARREGLO_SIN_CAUSA` (hay contramedidas pero no cadena de porqués), `PORQUE_SIN_EVIDENCIA`,
`IMPACTO_SIN_CIFRA`, `CONTRAMETRICA_SIN_FECHA`, `GATE_SIN_VERIFICACION`, `PASO_NO_REVERTIDO`,
`PASOS_MULTIPLES_CAMBIOS` y el aviso `CORTE_3_FALLOS`.

## Referencias por tema

- [`references/capa.md`](references/capa.md) — cinco porqués, Ishikawa (6M), validación inversa, CAPA,
  contra-métrica, Pareto de recurrencia, taxonomía de fallos, gate adversarial.
- [`references/depuracion-por-pasos.md`](references/depuracion-por-pasos.md) — microobjetivos,
  checkpoint, la prueba más barata, bitácora de pasos, regla de corte.
- [`references/cambios-minimos.md`](references/cambios-minimos.md) — pensar antes de escribir,
  simplicidad, cambios quirúrgicos, criterio de éxito antes de empezar.
- [`references/higiene-de-datos.md`](references/higiene-de-datos.md) — reglas para cualquier cifra
  que respalde una conclusión.
- [`templates/registro-capa.md`](templates/registro-capa.md),
  [`templates/bitacora-depuracion.md`](templates/bitacora-depuracion.md) y
  [`templates/ejemplo-rechazado.md`](templates/ejemplo-rechazado.md) — plantillas y ejemplos inventados
  (uno válido y uno que el validador rechaza).

## Formato de respuesta durante la depuración

Un tramo por mensaje, corto, con el plan visible:

```text
Plan (microobjetivos):
1. [hecho]     Checkpoint creado (rama fix/export-lento, commit a1b2c3d)
2. [hecho]     Reproducido: 42 s con fixture de 10 000 filas
3. [en curso]  H1 consulta N+1 — medir nº de consultas con y sin prefetch
4. [pendiente] Cambio mínimo + prueba de regresión
5. [pendiente] Suite completa + registro AC-007
```
