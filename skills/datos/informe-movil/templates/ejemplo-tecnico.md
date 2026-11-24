---
titulo: Estado de la plataforma · semana 45
subtitulo: API, base de datos, despliegues y costos de una tienda ficticia (datos inventados)
tipo: estado
fecha: 2026-11-09
skills: informe-movil
---

# Resumen {tab=resumen}

::: veredicto tono=warn confianza=media cifra="99,92 %" cifra_l="disponibilidad de la API en 7 días"
Todo estable salvo la base de datos: las consultas lentas se triplicaron desde la migración del martes.
- La API cumplió el objetivo de disponibilidad (99,9 %).
- El tiempo de respuesta p95 subió de 180 a 410 ms en el catálogo.
- Hay una corrección lista para desplegar; falta una decisión.
:::

::: kpis
99,92 % | Disponibilidad API | objetivo 99,9 % | ok
410 ms | p95 catálogo | era 180 ms | bad
14 | Despliegues | 0 revertidos | ok
2.340 € | Nube del mes | +6 % | warn
:::

# API {tab=datos icono=sitemap fig="99,92 %|disponible" ft=ok}
>> Cumple el objetivo; un corte de 4 minutos el jueves.

::: metricas "Respuesta por servicio"
Catálogo | 180 | 410 | 100 | 250 | 600 | ms | bajo | p95 tras la migración
Carrito | 120 | 125 | 100 | 250 | 600 | ms | bajo | sin cambios
Pagos | 300 | 290 | 200 | 400 | 600 | ms | bajo | proveedor externo
:::

::: nota tono=info "Corte del jueves"
4 minutos sin servicio a las 03:12 por un certificado vencido. Ya se renueva solo y avisa 14 días antes.
:::

# Base de datos {tab=analisis icono=search fig="3x|consultas lentas" ft=bad}
>> La migración del martes dejó un índice sin crear.

::: ranking "Consultas más lentas" max=900 unidad=" ms"
Búsqueda por categoría | 840 | Medido: registro de consultas lentas | bad
Listado de ofertas | 520 | Medido: registro de consultas lentas | bad
Historial de pedidos | 210 | Medido: registro de consultas lentas | warn
Ficha de producto | 45 | Medido: registro de consultas lentas | ok
:::

::: codigo
CREATE INDEX CONCURRENTLY idx_producto_categoria
  ON producto (categoria_id, activo);
:::

::: detalle "Por qué falta el índice"
::: texto
La migración renombró la columna `categoria` a `categoria_id`. El índice viejo se borró con la columna y el script nuevo no lo recreó. En la copia de pruebas, el índice baja la búsqueda de 840 a 38 ms.
:::
:::

# Despliegues {tab=datos icono=route fig="14|esta semana" ft=ok}
>> Catorce despliegues, ninguno revertido.

::: grafica "Despliegues por día" sub="semana 45"
x: lun, mar, mié, jue, vie
serie: 3, 4, 2, 4, 1
:::

::: lista "Lo más relevante"
- Nuevo filtro de tallas en el catálogo.
- Pagos: reintento automático cuando el banco tarda.
- Se retiró la versión vieja del carrito.
:::

# Costos {tab=analisis icono=coins fig="2.340 €|nube del mes" ft=warn}
>> Sube un 6 % por los registros guardados de más.

::: pilas "Gasto en la nube"
Octubre | Servidores:1300 | Base de datos:620:in | Registros:290:wa
Noviembre | Servidores:1310 | Base de datos:640:in | Registros:390:wa
:::

::: nota tono=warn "Registros"
Se guardan 90 días de registros de depuración. Con 30 días bastaría y se ahorran unos 200 € al mes.
:::

# Decidir {tab=decidir icono=checklist}
>> Una decisión, con la corrección ya probada.

::: decision D1 "¿Creamos el índice hoy en producción?"
Se crea sin bloquear la tabla; en pruebas tardó 6 minutos.
- Sí, hoy a las 22:00 | D1: sí, hoy 22:00 | *
- El sábado por la mañana | D1: sábado 08:00
:::

::: copiable "Comando para el equipo de guardia"
psql "$DATABASE_URL" -f migraciones/0046_indice_categoria.sql
:::

# Fuentes {tab=fuentes}

::: fuentes
Medido | Monitor de disponibilidad | panel «API pública» | 7 días
Medido | Registro de consultas lentas | umbral 200 ms | 7 días
Leído | Factura de la nube | noviembre parcial | proyección a fin de mes
:::

::: glosario
p95 | El 95 % de las peticiones responde en ese tiempo o menos.
Índice | Estructura que deja buscar en una tabla sin recorrerla entera.
:::
