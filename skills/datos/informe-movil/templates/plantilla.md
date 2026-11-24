---
titulo: Título del informe
subtitulo: Una línea que diga de qué trata
tipo: informe
fecha: 2026-01-31
---

# Resumen {tab=resumen}

::: veredicto tono=ok confianza=alta cifra="3 / 4" cifra_l="objetivos cumplidos"
La frase que el lector debe llevarse aunque no lea nada más.
- Primer porqué, con su cifra y unidad.
- Segundo porqué.
:::

::: kpis
3 de 4 | Objetivos cumplidos | el cuarto, en marcha | ok
12 días | Plazo restante | hasta el cierre | info
:::

# Datos {tab=datos}
>> Lo que se midió, en una línea.

::: ranking "Avance por objetivo" max=100 unidad=" %"
Objetivo uno | 100 | Medido: panel del proyecto | ok
Objetivo dos | 100 | Medido: panel del proyecto | ok
Objetivo tres | 100 | Medido: panel del proyecto | ok
Objetivo cuatro | 60 | Estimado: según el plan | warn
:::

# Decisión {tab=decidir}
>> Lo que hay que decidir.

::: decision D1 "¿Ampliamos el plazo del objetivo cuatro?"
Con una semana más se completa sin horas extra.
- Sí, una semana | D1: sí, una semana más | *
- No, cerrar con lo que haya | D1: no, cerrar así
:::

# Fuentes {tab=fuentes}

::: fuentes
Medido | Panel del proyecto | tablero interno | actualizado a diario
:::
