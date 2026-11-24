# Esquema de datos

Tres tipos de archivo en `data/`. Claves en inglés (compatibles con otras herramientas), textos libres
en el idioma del usuario. Fuente de verdad: los archivos por día; `indice.json` es un derivado.

## `data/AAAA-MM-DD.json` — un día

```json
{
  "date": "2026-11-23",
  "meals": [
    {
      "name": "Cena",
      "time": "20:15",
      "kcal": 381.5, "protein": 27.7, "fat": 28.1, "carbs": 4.1,
      "items": ["Omelette con champiñones y queso"],
      "ingredients": [
        { "name": "huevo", "qty": 3.0, "unit": "unidad", "g": 150.0,
          "kcal": 214.5, "protein": 18.8, "fat": 14.3, "carbs": 1.1 }
      ],
      "note": "3 huevos grandes; aceite asumido"
    }
  ],
  "daily_total": { "kcal": 1604.8, "protein": 90.4, "fat": 66.7, "carbs": 166.2 },
  "target": { "kcal": 1800, "protein": 110, "fat": 65, "carbs": 200 }
}
```

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `date` | texto AAAA-MM-DD | sí | igual al nombre del archivo |
| `meals[]` | lista | sí | puede estar vacía |
| `meals[].name` | texto | sí | `Desayuno`, `Almuerzo`, `Cena`, `Snack` u otro |
| `meals[].time` | texto | no | `HH:MM` (se admite `~HH:MM` = aproximada) o vacío |
| `meals[].kcal/protein/fat/carbs` | número ≥ 0 | sí | = Σ de `ingredients` (tolerancia 0,6) |
| `meals[].items[]` | lista de textos | no | descripción visible en el panel |
| `meals[].ingredients[]` | lista | recomendado | desglose; sin él la comida vale lo que diga su total |
| `ingredients[].name` | texto | sí | nombre canónico de la base (o libre si es `--manual`) |
| `ingredients[].qty` | número > 0 | sí | cantidad en `unit` |
| `ingredients[].unit` | texto | sí | `g`, `ml`, o una porción (`unidad`, `taza`, `plato`…) |
| `ingredients[].g` | número | no | gramos equivalentes (lo escribe el script) |
| `ingredients[].kcal/protein/fat/carbs` | número ≥ 0 | sí | valores ya calculados para esa cantidad |
| `ingredients[].fuente` | texto | no | de dónde salen los valores de un ingrediente libre |
| `meals[].note` | texto | no | supuestos declarados |
| `daily_total` | objeto | sí | = Σ de `meals` (tolerancia 0,6) |
| `target` | objeto | no | meta propia de ese día; si falta, el panel usa `config.json → meta` |

Unidades: kcal en kilocalorías; proteína, grasa y carbohidratos en gramos. Redondeo a 1 decimal.

## `data/indice.json` — totales por día (lo lee la vista Semana)

```json
{ "version": 1,
  "fechas": { "2026-11-23": { "kcal": 1604.8, "protein": 90.4, "fat": 66.7, "carbs": 166.2, "comidas": 4 } } }
```

Lo regenera `registro.py` en cada escritura (o `registro.py indice`). `validar_registro.py` falla si
no coincide con los archivos del día: así se evita la gráfica semanal con totales viejos.

## `config.json` — en la raíz del panel

```json
{ "titulo": "Mis comidas", "idioma": "es", "semana_inicia": "lunes",
  "meta": { "kcal": 1800, "protein": 110, "fat": 65, "carbs": 200 } }
```

`idioma`: `es` o `en` (textos del panel). `semana_inicia`: `lunes` o `domingo`.

## `data/alimentos.json` y `data/alimentos_propios.json`

Ver `base-alimentos.md`.

## Validación

`python scripts/validar_registro.py data/` (exit 0/1, `--json` para máquinas). El JSON Schema de un día
está en `esquema-dia.schema.json` por si quieres validar con otra herramienta; la aritmética (sumas,
índice) solo la comprueba el script.
