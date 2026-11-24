# Base de alimentos

## `data/alimentos.json` (incluida)

102 alimentos genéricos con valores por 100 g tomados de **USDA FoodData Central, conjunto SR Legacy
(abril 2018)**, publicado por el Departamento de Agricultura de EE. UU. (Agricultural Research Service)
en **dominio público (CC0 1.0)**. Cada entrada lleva su `fdc_id`; cualquiera puede verificarla en
`https://fdc.nal.usda.gov/food-details/<fdc_id>/nutrients`.

Se regenera, idéntica, con:

```bash
# descarga única (~6 MB): https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip
python scripts/construir_base_usda.py --csv <carpeta_descomprimida> --out templates/panel/data/alimentos.json
```

La lista de alimentos, sus nombres en español, alias y porciones está en `CATALOGO` dentro del script:
para ampliar la base, agrega una línea con el `fdc_id` y vuelve a generarla.

### Formato de una entrada

```json
"huevo": {
  "categoria": "proteína",
  "por_100g": { "kcal": 143.0, "protein": 12.56, "fat": 9.51, "carbs": 0.72, "fiber": 0.0 },
  "porciones": { "unidad": { "g": 50.0, "fuente": "usda", "usda": "1 large" } },
  "alias": ["huevo entero", "huevo crudo"],
  "fuente": "USDA FoodData Central SR Legacy",
  "fdc_id": 171287,
  "usda_descripcion": "Egg, whole, raw, fresh"
}
```

- `carbs` es "carbohidratos por diferencia" (incluye fibra), como en las etiquetas de EE. UU.
- Porciones `"fuente": "usda"` vienen de la tabla de porciones de USDA; `"estimada"` son referencias
  del proyecto (p. ej., un pan francés de 40 g) y conviene ajustarlas a tu realidad.
- Por qué no se publica la base original del proyecto: se construyó durante el uso diario con
  estimaciones del agente y etiquetas de marcas sin una fuente única verificable. Se reemplazó por
  esta base reducida y trazable.

## `data/alimentos_propios.json` (tuya)

Mismo formato, para lo que no está en USDA: productos con marca, platos de tu zona, recetas tuyas.
`registro.py` la une a la base USDA (si una clave existe en ambas, gana la tuya). `fuente` es
obligatoria por convención: "etiqueta del producto", "receta casera (ingredientes USDA)", "tabla X".

Ejemplo de formato (valores ilustrativos, no medidos):

```json
{ "alimentos": {
  "lomo saltado casero": {
    "categoria": "plato",
    "por_100g": { "kcal": 150, "protein": 10.5, "fat": 7.2, "carbs": 11.0, "fiber": 1.2 },
    "porciones": { "plato": { "g": 350, "fuente": "estimada" } },
    "alias": ["lomo saltado"],
    "fuente": "receta casera estimada por ingredientes USDA"
  } } }
```

### Tablas públicas útiles para ampliar

- USDA FoodData Central (Foundation, SR Legacy, FNDDS): dominio público.
- Tablas nacionales de composición (por ejemplo, las tablas peruanas del INS/CENAN, la BEDCA española
  o la TACO brasileña) son buenas fuentes para platos e insumos regionales: revisa la licencia de cada
  una antes de copiar sus valores a un repositorio público y cítala en `fuente`.
- Para productos empacados, la etiqueta del envase es la mejor fuente. Evita copiar bases de apps
  comerciales: sus datos suelen tener términos de uso restrictivos.
