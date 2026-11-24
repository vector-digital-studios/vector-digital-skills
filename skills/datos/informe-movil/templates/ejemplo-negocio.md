---
titulo: Cierre de octubre · Tienda Brisa
subtitulo: Ventas, márgenes y qué decidir antes de diciembre (datos inventados)
tipo: informe
fecha: 2026-11-03
skills: informe-movil
---

# Resumen {tab=resumen}

::: veredicto tono=ok confianza=alta cifra="+18 %" cifra_l="ventas frente a septiembre"
Octubre fue el mejor mes del año en ventas, pero el envío gratis bajó el margen y la ganancia bruta quedó casi igual: +236 €.
- Ventas: 48.200 € (septiembre: 40.850 €).
- Margen bruto: 31 % (septiembre: 36 %), por el envío gratis desde 30 €.
- La campaña de correo trajo 1 de cada 4 pedidos nuevos.
:::

::: kpis
48.200 € | Ventas del mes | +18 % frente a septiembre | ok
31 % | Margen bruto | −5 puntos | warn
1.212 | Pedidos | ticket medio 39,8 € | info
2,9 % | Devoluciones | estable | ok
:::

# Datos {tab=datos icono=chart-bar}
>> De dónde vino la subida y quién la pagó.

::: grafica "Ventas por mes" sub="miles de €, 2026"
x: may, jun, jul, ago, sep, oct
serie: 31, 33, 29, 35, 40.9, 48.2
:::

::: ranking "Ventas por categoría" max=20 unidad=" mil €"
Hogar | 17,4 | Medido: tienda online | ok
Cocina | 12,1 | Medido: tienda online | ok
Textil | 9,8 | Medido: tienda online | info
Regalos | 6,2 | Estimado: incluye 40 vales sin canjear | warn
Outlet | 2,7 | Medido: tienda online | bad
:::

::: pilas "Pedidos por canal"
Septiembre | Directo:410 | Correo:180:in | Redes:250:wa | Anuncios:190:vi
Octubre | Directo:430 | Correo:300:in | Redes:270:wa | Anuncios:212:vi
:::

::: tabla "Márgenes por categoría" ordenable=1
Categoría | Ventas | Margen | Tendencia
Hogar | 17.400 € | 34 % | {ok}Sube
Cocina | 12.100 € | 33 % | {ok}Estable
Textil | 9.800 € | 28 % | {warn}Baja
Regalos | 6.200 € | 30 % | {warn}Baja
Outlet | 2.700 € | 12 % | {bad}Pérdida con envío
:::

# Análisis {tab=analisis icono=bulb}
>> El envío gratis funciona para vender, no para ganar.

::: vs "Envío gratis desde 30 € o desde 45 €" a="Desde 30 €" b="Desde 45 €"
Pedidos al mes | 1.212 | 1.050 | A | Simulado con los pedidos reales de octubre
Margen bruto | 31 % | 35 % | B | Menos envíos pagados por la tienda
Ticket medio | 39,8 € | 47,5 € | B | La gente completa el carrito hasta 45 €
Quejas por envío | 6 | 11 | A | Encuesta poscompra
:::

::: matriz "Qué mover primero" x=Esfuerzo y=Impacto
1 | Subir el envío gratis a 45 € | 2 | 8
2 | Sacar el outlet del envío gratis | 1 | 6
3 | Segunda campaña de correo | 4 | 7
4 | Nuevo proveedor textil | 8 | 5
:::

::: nota tono=warn "Ojo con diciembre"
Si el umbral sigue en 30 €, el pico de Navidad repetirá la caída de margen. La simulación estima unos **2.900 €** de margen perdido en diciembre.
:::

::: detalle "Cómo se simuló el umbral de 45 €"
::: texto
Se tomaron los 1.212 pedidos de octubre y se marcó cuáles habrían pagado envío con el umbral nuevo. A esos se les aplicó la tasa de abandono observada en la prueba A/B de agosto (13 %).
:::
::: glosario
Prueba A/B | Mostrar dos versiones a mitades del público y comparar el resultado.
Ticket medio | Ventas divididas entre pedidos.
KPI | Indicador clave: una cifra que resume si algo va bien.
:::
:::

# Decisión {tab=decidir icono=checklist}
>> Dos decisiones para aplicar antes del 15 de noviembre.

::: decision D1 "¿Subimos el envío gratis a 45 €?"
Recupera unos 4 puntos de margen; se pierden unos 160 pedidos al mes, casi todos de ticket bajo.
- Sí, desde el 10 de noviembre | D1: sí, envío gratis desde 45 € | *
- Probarlo dos semanas con la mitad del público | D1: prueba A/B de dos semanas
- No, mantener 30 € hasta enero | D1: no, se mantiene 30 €
:::

::: decision D2 "¿Repetimos la campaña de correo?"
Trajo 300 pedidos con un costo de 410 €.
- Sí, misma lista y un cupón del 10 % | D2: sí, con cupón | *
- Sí, sin cupón | D2: sí, sin cupón
:::

::: pasos "Plan si se aprueba"
1 | Cambiar el umbral en la tienda | Ajuste en la configuración de envíos | 15 min
2 | Avisar en la portada y en el carrito | Banner y texto del carrito | 1 h
3 | Medir dos semanas | Pedidos, margen y abandono del carrito | 14 días
:::

# Fuentes {tab=fuentes icono=link}

::: fuentes
Medido | Panel de ventas de la tienda | export_octubre.csv | 1.212 pedidos
Medido | Plataforma de correo | campaña «Otoño» | 12.400 envíos
Estimado | Simulación del umbral | modelo propio | abandono del 13 % de la prueba de agosto
:::
