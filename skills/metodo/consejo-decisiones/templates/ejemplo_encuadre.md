# Decisión: ¿qué hacer con el backend de la aplicación en los próximos dos meses?

EJEMPLO FICTICIO. Una startup de 6 personas (3 desarrolladores) mantiene un backend monolítico de 2019 que sirve
una aplicación de reservas. Decide la directora técnica con el presupuesto y el equipo actuales.

## Objetivo de fondo
Desconocido: no declarado (estabilidad, velocidad para sacar funciones o reducir costos). No se pregunta.

## Opciones
### A · Reescribir el backend completo
- Qué es: construir un backend nuevo desde cero y cambiarlo de una vez cuando esté terminado.
- Costo para quien decide: Estimado: 3 desarrolladores a tiempo completo durante 6 meses, sin funciones nuevas —
  base: el monolito tiene 41 módulos y el equipo tardó 4 semanas en reescribir uno de tamaño medio.
- Evidencia a favor: Medido: 38 % del tiempo de desarrollo del último trimestre se fue en arreglar fallos del
  monolito — fuente: registro de tareas del equipo, trimestre anterior.
- Evidencia en contra: Conocimiento general: las reescrituras completas suelen tardar más de lo previsto y congelan
  el producto mientras duran. Desconocido: cuántas reglas de negocio están solo en el código viejo.
- Plazo natural: 6 meses — cuando se haga el cambio se sabrá si el sistema nuevo falla menos.
- Reversible: parcial — si se abandona a medias, se pierden los meses invertidos.
### B · Migrar por partes
- Qué es: sacar del monolito un módulo cada vez, empezando por pagos, detrás de una capa que reparte las peticiones.
- Costo para quien decide: Estimado: 1 desarrollador a tiempo completo y los otros 2 siguen con el producto —
  base: tamaño del módulo de pagos frente al módulo ya reescrito.
- Evidencia a favor: Medido: el módulo de pagos causó 11 de las 19 incidencias graves del último semestre —
  fuente: historial de incidencias del equipo.
- Evidencia en contra: Estimado: convivir con dos sistemas añade unas 4 horas semanales de mantenimiento — base:
  experiencia del equipo con la capa de reparto en un proyecto anterior. Desconocido: si la base de datos compartida
  impide separar pagos sin tocar otros módulos.
- Plazo natural: 10 semanas — al terminar pagos se sabrá si bajan sus incidencias.
- Reversible: sí — la capa de reparto puede devolver las peticiones al monolito.
### C · No tocarlo y reforzar lo actual
- Qué es: dejar la arquitectura como está y dedicar un día por semana a pruebas automáticas y monitorización.
- Costo para quien decide: Estimado: 0,6 desarrolladores equivalentes por semana — base: un día de cada uno de los
  3 desarrolladores.
- Evidencia a favor: Medido: el monolito cumplió el 99,2 % de disponibilidad en los últimos 90 días — fuente: panel
  de monitorización.
- Evidencia en contra: Medido: el tiempo medio para sacar una función nueva subió de 6 a 11 días en un año —
  fuente: registro de tareas del equipo.
- Plazo natural: 4 semanas — en un mes se ve si bajan los fallos con más pruebas.
- Reversible: sí — se puede pasar a A o B después.

## Restricciones duras
- No contratar personal nuevo este año — Aplica a: todas — Comprobado: presupuesto aprobado por la junta, enero.
- La aplicación no puede estar caída más de 1 hora seguida — Aplica a: todas — Comprobado: contrato con el
  cliente principal, cláusula de servicio.

## Datos comunes
- Medido: 3 desarrolladores, todos con más de 2 años en el código actual — fuente: plantilla del equipo.
- Estimado: el cliente principal pide 2 funciones nuevas antes del verano — base: hoja de ruta comercial.
- Casos parecidos: Conocimiento general: las migraciones por partes son la práctica habitual en sistemas que no
  pueden pararse; las reescrituras completas tienen fama de retrasarse.
- Desconocido: cuántas reglas de negocio no documentadas hay en el monolito (barato de medir: 2 días de lectura).

## Qué está en juego
Dos meses de trabajo de 3 personas, la estabilidad que exige el cliente principal y las 2 funciones prometidas.
Todas las opciones se pueden detener; A pierde más si se detiene a medias.

## Horizonte
Horizonte: 8 semanas (hasta fin del próximo bimestre). Ese día se mira qué avanzó de forma medible.
Señal temprana para A: porcentaje de módulos reescritos y probados frente al plan lineal de 41 módulos en 6 meses.
Señal temprana para B: tráfico de pagos servido por el módulo nuevo e incidencias de pagos frente al semestre anterior.
