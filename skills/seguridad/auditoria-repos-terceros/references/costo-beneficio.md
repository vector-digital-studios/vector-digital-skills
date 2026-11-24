# Costo-beneficio: ¿compensa adoptarlo?

Un repo puede estar limpio y aun así no convenir. La pregunta no es «¿es bueno?» sino «¿resuelve un dolor
real nuestro mejor que lo que ya tenemos, a un costo y riesgo aceptables?». La respuesta más útil casi
siempre es condicional: **«no ahora; sí cuando X»**.

## La matriz de `auditar.py`

| Criterio | Peso | De dónde sale |
|---|---:|---|
| Utilidad: dolor real, nombrado, que resuelve | 30 % | `criterios.json` (persona) |
| Riesgo de seguridad | 25 % | automático: 10 − 3×altos − 1×medios − 0,25×bajos; 0 si hay un crítico |
| Costo total: dinero, horas de integración, cómputo | 15 % | `criterios.json` (10 = casi nulo) |
| Mantenimiento | 10 % | automático: fecha del último cambio (≤ 90 días 9 · ≤ 180 7 · ≤ 365 5 · más 3 · archivado 1) |
| Licencia | 10 % | automática: permisivas 10 · MPL/LGPL 7 · GPL 5 · AGPL/no comercial 3 · SSPL/BUSL 2 · ninguna 1 |
| Encaje con lo que ya se usa | 10 % | `criterios.json` |

- El total es la media ponderada de los criterios con dato. **Sin «utilidad» no hay total**: el informe
  dice «incompleto» y el veredicto no puede ser ADOPTAR.
- Riesgo y licencia **no se pueden sobrescribir** desde `criterios.json`: salen de la evidencia. Si alguien
  pone «riesgo: 10» a mano, el informe lo marca como ignorado.
- Mantenimiento se toma, por orden: `criterios.repo.pushed_at` (salida de `resolve_repos.py --json`),
  `criterios.ultimo_cambio`, o el último commit del clon.

## Cómo puntuar los criterios manuales

| Nota | Utilidad | Costo | Encaje |
|---|---|---|---|
| 9-10 | resuelve un dolor activo que hoy cuesta horas o dinero cada semana | gratis, local, < 1 h de integración | se enchufa sin tocar nada |
| 6-8 | mejora clara de algo que ya funciona | gratis con límites o pago bajo; horas de integración | adaptadores pequeños |
| 3-5 | «podría servir» algún día | pago recurrente o días de integración | duplica algo existente o cambia hábitos |
| 0-2 | no resuelve nada que duela hoy | caro, nube obligatoria, dependencia del vendedor | choca con decisiones ya tomadas |

No dar 10 a la utilidad si el dolor no está nombrado. Separar el **patrón** de fondo (que puede valer y
copiarse) del **producto** concreto (que puede no aplicar).

## Dos etiquetas obligatorias en cada ítem

1. **Costo**: gratis / pago y **de quién es la factura** (créditos del vendedor, cupo de un servicio, tu
   suscripción). Si no se verificó: `POR VERIFICAR`, nunca una estimación de memoria.
2. **Dónde corre el cómputo**: local (costo marginal casi nulo) o nube de terceros (se paga por uso). Un
   mismo producto puede mezclar ambos: la interfaz local y la generación en la nube. Decirlo por capa.

En `criterios.json` van en `"etiquetas": {"costo": "...", "computo": "..."}`.

## Alternativas

Siempre al menos dos: **lo que ya se tiene** (no hacer nada también es una opción) y la alternativa
conocida más cercana. Para cada una: costo, nota y por qué. Si lo que ya se tiene cubre el 80 %, decirlo.

## Escenarios de costo (cuando el ahorro depende del volumen)

| Escenario | Ahorro o gasto mensual | ¿Vale la pena? |
|---|---:|---|
| Volumen actual | (calcular con datos reales) | |
| Si el volumen se multiplica por 10 | | |

El cálculo va con su fuente (factura, panel de uso, medición). Lo estimado se rotula «estimado» con margen.

## Veredicto y «cuándo sí»

- **ADOPTAR**: resuelve un dolor activo, sin riesgos abiertos, total ≥ 7.
- **ADOPTAR CON CONDICIONES**: cada condición es verificable («fijar el commit», «instalar sin scripts»,
  «solo como referencia por falta de licencia», «cuando el volumen supere X»).
- **NO ADOPTAR**: bloqueo de seguridad, o no compensa. Igual se registra con su motivo y su condición de
  reapertura, para no volver a evaluarlo desde cero.

Lo que queda en espera va a un **backlog de herramientas** con: condición de activación, costo, pasos de
migración, alternativas y riesgo. Así la próxima evaluación parte de ahí.

## Tono del informe

Directo y con opinión: la persona paga por criterio, no por resúmenes neutros. Tablas para datos, viñetas
para razones, no más de dos párrafos de prosa. No resumir el README: la persona puede leerlo.
