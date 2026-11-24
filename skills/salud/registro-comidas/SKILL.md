---
name: registro-comidas
description: "Usar para registrar comidas por chat o foto y ver calorías en un panel"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [nutrition, calories, macros, food-logging, meal-tracker, pwa, health, usda, spanish]
  idioma: es
  requiere: "agente que lea SKILL.md y ejecute Python 3.8+; visión solo para el registro por foto"
---

# Registro de comidas con agente

El usuario cuenta (o fotografía) lo que comió → tú identificas alimentos y cantidades → `scripts/registro.py`
hace la aritmética con la base de alimentos y escribe `data/AAAA-MM-DD.json` → el panel estático
(`templates/panel/`) muestra el día, la semana, la meta y los macros.

Reparto de trabajo, y es la regla más importante: **tú interpretas, el script calcula**. No sumes calorías
de cabeza ni edites el JSON a mano: los errores de suma y las comas rotas fueron las dos fallas más
repetidas en producción.

## 0. Primera vez (instalación del proyecto del usuario)

1. Copia `templates/panel/` a la carpeta que el usuario elija (será su "proyecto de comidas"). Contiene
   el panel, `config.json`, `data/alimentos.json` (base USDA) y 14 días de demo.
2. Borra los días de demo: `data/AAAA-MM-DD.json` e `data/indice.json` (conserva `alimentos.json`).
3. Pregunta la meta diaria (kcal, proteína, grasa, carbohidratos) y escríbela en `config.json → meta`.
   Si no la sabe, no la inventes: deja la de ejemplo y díselo; la meta la define el usuario o su
   profesional de salud.
4. A partir de aquí, todos los comandos van con `--datos <proyecto>/data` (o exporta
   `REGISTRO_COMIDAS_DATOS`). Los scripts están en la carpeta de esta skill: `scripts/`.

## 1. Antes de escribir

- **Fecha real.** Obtén la fecha del sistema (`date` o `python -c "import datetime;print(datetime.date.today())"`).
  La fecha de la conversación puede no ser la real. Traduce "hoy / ayer / anoche" a AAAA-MM-DD y,
  después de medianoche, confirma si "anoche" es la fecha anterior.
- **Mira lo que ya hay:** `python scripts/registro.py --datos D mostrar --fecha F`.
- **Choque con lo registrado** (misma comida ya cargada con otros alimentos): NO sobrescribas ni
  "corrijas" en silencio. Muestra lo registrado vs. lo nuevo y pregunta: ¿reemplazar, sumar o es otro día?
- **"Más" suma.** "Dos huevos con pan… más un yogur" = todo junto. Declara el total que entendiste.

## 2. De la descripción a cantidades

Para cada alimento decide **nombre de la base + cantidad + unidad**.

1. Busca el nombre: `python scripts/registro.py --datos D buscar "palta"`. Usa SIEMPRE el nombre
   canónico que devuelve (así las consultas por alimento funcionan). Los alias ya resuelven sinónimos
   regionales (palta/aguacate, plátano/banana, frejol/frijol).
2. Cantidad: gramos si el usuario los da; si no, una porción de la base (`unidad`, `taza`, `rebanada`,
   `cucharada`…; `buscar` las lista). `ml` se trata como gramos (densidad ≈ 1; válido para bebidas).
3. **Cuándo preguntar y cuándo asumir:**
   - Pregunta ANTES de registrar si la cantidad es ambigua y mueve cientos de kcal: "unos trocitos de
     pollo", "un poco de arroz", "un par de panes" con relleno, aceite sin cantidad en una fritura.
   - Asume y DECLARA (sin bloquear) si el error posible es pequeño o hay un estándar razonable: una
     fruta, una taza de café, un plato de restaurante con nombre conocido.
   - Lenguaje informal: "cubitos/trocitos" de carne ≈ 30-40 g cada uno, no 100 g. Detalle en
     `references/estimacion.md`.
4. **Grasa de cocción:** no la sumes por defecto. Si el método la implica (frito, salteado, "con
   aceite"), agrégala como ingrediente aparte (`aceite vegetal=1 cucharada`) y decláralo.
5. **Platos compuestos caseros** (guisos, salteados, ensaladas): descompón en ingredientes de la base.
6. **Platos de restaurante o productos empacados:** si tienes la etiqueta nutricional (pide foto),
   usa sus valores con `--manual`. Si no, estima por ingredientes y anota el supuesto en `--nota`.
   Porción compartida = `qty 0.5` del plato completo.
7. **Dictado por voz deformado:** interpreta con contexto culinario (nombres de platos y locales se
   deforman fonéticamente) y confirma la interpretación en la respuesta.
8. **Alimento que no está en la base:** agrégalo a `data/alimentos_propios.json` (mismo formato que
   `alimentos.json`, con `fuente` obligatoria: "etiqueta del producto", "USDA fdc_id N", "tabla X") y
   reúsalo. No toques `alimentos.json` (se regenera desde USDA). Formato en `references/base-alimentos.md`.

## 3. Registro por foto

Requiere un modelo con visión. Flujo en `references/estimacion.md` § Fotos:
identifica cada componente → estima su porción con referencias del propio plato (plato llano ≈ 26 cm,
cuchara, mano, envase) → decláralo en una lista corta → registra → ofrece ajustar. Si la foto no
permite distinguir algo que pesa mucho (salsa cremosa vs. vinagreta, arroz frito vs. blanco), pregunta.
Una foto de etiqueta nutricional vale más que cualquier estimación: úsala con `--manual`.

## 4. Registrar

```bash
python scripts/registro.py --datos D agregar --fecha 2026-11-23 --comida Cena --hora 20:15 \
  --item "Omelette con champiñones y queso" \
  --ing "huevo=3 unidad" --ing "champiñones=1 taza" --ing "queso mozzarella=30 g" \
  --ing "aceite vegetal=0.5 cucharada" --nota "3 huevos grandes; aceite asumido"
```

- Comidas estándar: `Desayuno`, `Almuerzo`, `Cena`, `Snack` (el panel marca como "pendiente" las tres
  primeras si faltan). Se admite cualquier otro nombre ("Pre-entreno").
- `--unir` suma ingredientes a una comida ya existente con ese nombre (p. ej., "y también un postre").
- `--simular` calcula y muestra sin escribir: úsalo cuando quieras confirmar antes con el usuario.
- Ingrediente libre (etiqueta o restaurante):
  `--manual '{"name":"ceviche (restaurante)","qty":1,"unit":"plato","kcal":420,"protein":48,"fat":8,"carbs":35,"fuente":"estimación por ingredientes"}'`
- El script crea el día si no existe, recalcula totales y regenera `data/indice.json`. Escribe de
  forma atómica y relee el JSON: nunca deja un archivo a medias.

## 5. Corregir

- Cantidad o alimento mal: `quitar --fecha F --comida C --ingrediente "nombre"` y vuelve a `agregar --unir`.
- Comida entera mal o en otro día: `quitar --fecha F --comida C` y regístrala donde corresponde.
- Comida en el slot equivocado (era Snack, no Almuerzo): quita el ingrediente del original y agrégalo
  con `--comida Snack`.
- Si alguien editó un JSON a mano: `recalcular --fecha F` (o sin `--fecha` para todo) y valida.
- Cambio de meta: edita `config.json → meta`. Si el usuario quiere conservar la meta antigua en días
  pasados, añade a esos días un campo `target` (el panel lo prefiere sobre `config.json`).

## 6. Validar (obligatorio tras escribir)

```bash
python scripts/validar_registro.py D
```

Exit 0 = esquema correcto, comidas = Σ ingredientes, día = Σ comidas, `indice.json` al día. Si falla,
el mensaje dice el comando que lo arregla. No respondas "registrado" con la validación en rojo.
Esquema completo: `references/esquema.md` (+ `references/esquema-dia.schema.json`).

## 7. Responder al usuario

Breve, en este orden: qué registraste → supuestos → cómo va el día.

```
Registrada la cena (20:15): 382 kcal · P 28 g · G 28 g · C 4 g.
Supuse 3 huevos grandes, 1 taza de champiñones, 30 g de mozzarella y media cucharada de aceite.
Día: 1.605 / 1.800 kcal (quedan 195) · proteína 90/110 g · grasa ya en 67/65 g.
```

Sin sermones ni juicios sobre lo que comió. Si el usuario pide análisis, usa los datos (`mostrar`,
`indice.json`), nunca promedios inventados.

## 8. Publicar el panel

Detalle y advertencias de privacidad en `references/publicar.md`. Resumen:
- **Local:** `python -m http.server 8000` dentro del proyecto → `http://localhost:8000`. (Con doble
  clic no funciona: el navegador bloquea `fetch` en `file://`).
- **Celular en la misma red:** igual, abriendo `http://<IP-del-PC>:8000`, e "Instalar app" (PWA).
- **Internet:** Vercel, Netlify o GitHub Pages sirven el panel tal cual. Ojo: son datos de salud;
  cualquier hosting estático lo deja público salvo que actives protección (ver referencia).

## Límites que debes decir si preguntan

- Las cifras son estimaciones (±10-20 % habitual en registro por descripción; más en fotos).
- La base USDA usa alimentos genéricos de EE. UU.; para platos regionales, estima por ingredientes.
- No es consejo médico ni nutricional; no fijes metas por tu cuenta.

## Archivos

- `scripts/registro.py` — buscar / agregar / quitar / mostrar / recalcular / indice (solo stdlib)
- `scripts/validar_registro.py` — validador del esquema y de la aritmética (exit 0/1)
- `scripts/generar_demo.py` — días de demo inventados con el mismo motor
- `scripts/construir_base_usda.py` — regenera `alimentos.json` desde USDA FoodData Central
- `scripts/autoprueba.py` — prueba completa sin red
- `templates/panel/` — panel PWA (HTML + JS + CSS, sin dependencias) + `config.json` + `data/`
- `references/esquema.md`, `references/esquema-dia.schema.json`, `references/estimacion.md`,
  `references/base-alimentos.md`, `references/publicar.md`
