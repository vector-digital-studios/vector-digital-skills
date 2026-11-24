---
titulo: ¿Qué servicio de correo transaccional usar?
subtitulo: Comparativa de dos proveedores ficticios para los avisos de pedidos (datos inventados)
tipo: dossier
fecha: 2026-11-12
skills: informe-movil
---

# Resumen {tab=resumen}

::: veredicto tono=ok confianza=media cifra="8 / 10" cifra_l="puntuación de Cartero con la rúbrica"
Cartero gana: entrega más rápido y cuesta menos con nuestro volumen; Mensajero solo conviene si se necesita soporte por teléfono.
- Entrega media: 4 s frente a 11 s.
- Costo con 60.000 correos al mes: 38 € frente a 55 €.
- Migrar lleva un día de trabajo.
:::

::: kpis
4 s | Entrega media Cartero | 11 s Mensajero | ok
38 € | Costo mensual Cartero | 55 € Mensajero | ok
1 día | Migración | plantillas ya en HTML | info
:::

# Datos {tab=datos}
>> Pruebas con 2.000 envíos a buzones de prueba.

::: vs "Cartero frente a Mensajero" a=Cartero b=Mensajero
Entrega media | 4 s | 11 s | A | 2.000 envíos de prueba
Llegan a la bandeja de entrada | 97 % | 95 % | A | buzones de prueba de 4 proveedores
Costo con 60.000 al mes | 38 € | 55 € | A | tarifas públicas de noviembre
Soporte | Correo | Teléfono | B | solo en el plan de Mensajero
:::

::: tabla "Precio según volumen" ordenable=1
Correos al mes | Cartero | Mensajero
20.000 | 15 € | 20 €
60.000 | 38 € | 55 €
150.000 | 80 € | 110 €
:::

# Análisis {tab=analisis}
>> El precio importa menos que la entrega rápida: un aviso de pago que tarda, genera consultas.

::: rubrica anterior=5 nota=8 tanda="prueba de noviembre" resumen="Cartero cumple en lo que más pesa"
Velocidad de entrega | 30 | 5 | 9 | 4 s de media | 2.000 envíos
Bandeja de entrada | 30 | 6 | 8 | 97 % | buzones de prueba
Precio | 20 | 6 | 8 | 38 € al mes | tarifa pública
Soporte | 20 | 6 | 6 | solo por correo | contrato tipo
:::

::: nota tono=warn "Riesgo"
Cartero es más nuevo: tiene menos historial de incidentes publicado. Se recomienda mantener Mensajero como respaldo un mes.
:::

# Decidir {tab=decidir}

::: decision D1 "¿Migramos a Cartero?"
Un día de trabajo; Mensajero queda de respaldo durante un mes.
- Sí, este mes | D1: sí, migrar este mes | *
- Esperar a enero | D1: esperar a enero
:::

# Fuentes {tab=fuentes}

::: fuentes
Medido | Prueba de envío propia | 2.000 correos | 4 buzones de prueba
Leído | Tarifas públicas de ambos proveedores | noviembre de 2026 | sin descuentos
:::
