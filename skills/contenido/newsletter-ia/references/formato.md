# Formato de la edición

Un archivo `AAAA-MM-DD.json` por edición (ejemplo completo: `templates/ejemplo-edicion.json`).

```json
{
  "nombre": "Radar IA",
  "fecha": "2026-11-23",
  "generado": "2026-11-24T07:40:00-05:00",
  "titular": "2-3 historias principales separadas por punto y coma",
  "resumen_del_dia": "2-3 oraciones que dan contexto al día",
  "items": [
    {
      "rank": 1,
      "titulo": "Qué pasó y por qué importa, en español",
      "resumen": "80-420 caracteres: qué, quién, cifra, contexto",
      "relevancia": 10,
      "por_que_relevante": "Vínculo con la audiencia en una frase",
      "categorias": ["Agentes y herramientas", "Empresa"],
      "categoria": "Agentes y herramientas",
      "color": "#FF6A00",
      "url": "https://fuente-primaria/articulo",
      "fuente": "Medio — Título original del artículo",
      "fecha_fuente": "2026-11-23",
      "impacto": "Por qué te importa: acción o consecuencia concreta"
    }
  ],
  "meta": { "total_items": 5, "relevancia_media": 8.2, "categoria_principal": "Agentes y herramientas" }
}
```

Reglas que comprueba `scripts/verificar.py`:
- `items` exactamente N (`newsletter.items` del archivo de fuentes o `--items`), `rank` 1..N.
- `relevancia` entera 1-10 y ≥ 6 (`--relevancia-min`).
- `url` http(s) válida y única; `fuente` no vacía; `fecha_fuente` a ≤ 3 días de `fecha` (`--ventana-dias`).
- `categorias` 1-3 sin duplicados de la taxonomía; `categoria == categorias[0]`; `color` = el de esa categoría.
- `resumen` 80-420 caracteres; `impacto` ≥ 60; sin palabras de humo.
- `meta.total_items`, `meta.relevancia_media` (1 decimal) y `meta.categoria_principal` (la más frecuente
  entre todas las `categorias`; empate → la de mejor rank) coinciden con los items.
- Con `--index index.json`: orden descendente, sin fechas repetidas y 1:1 con los archivos de la carpeta.

Salidas de `scripts/generar.py`: `AAAA-MM-DD.md` (Markdown para blog, Notion o GitHub) y
`AAAA-MM-DD.html` (una columna de 600 px con estilos en línea: email y móvil). Con `--index` actualiza
`index.json` (`fecha`, `titular`, `items`, `relevancia_media`).
