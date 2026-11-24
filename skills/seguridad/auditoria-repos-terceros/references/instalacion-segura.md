# Instalar lo aprobado sin abrir la puerta

Solo después de un veredicto ADOPTAR (o CON CONDICIONES cumplidas) y de la confirmación explícita de la
persona. Instalar es una acción distinta de evaluar.

## Skills de agente: copia manual de una carpeta auditada

1. **Clonar superficial en una carpeta temporal** (`git clone --depth 1`). Si el repo pesa cientos de MB y
   la skill es una carpeta, descargar solo esa ruta:
   ```bash
   git clone --depth 1 --filter=blob:none --sparse <url> tmp-skill && cd tmp-skill
   git sparse-checkout set <ruta/de/la/skill>
   ```
2. **Una sola copia**: muchos repos repiten la misma skill para varios agentes (`.agents/`, `.claude/`,
   `.cursor/`…). Comparar 2-3 cabeceras y copiar una.
3. **Elegir, no tragar el paquete**: de un repo con decenas de skills, copiar solo las aprobadas. Cada
   descripción cargada compite por la atención del agente en todas las tareas. Registrar qué se excluyó y
   por qué.
4. **Leer scripts y SKILL.md completos** de lo que se copia (el informe de `auditar.py` dice dónde mirar).
5. **Copiar la carpeta** al directorio de skills del agente (`~/.claude/skills/`, `~/.codex/skills/`,
   `~/.hermes/skills/<categoría>/`, o `<proyecto>/.claude/skills/` si es para un solo proyecto).
6. **Registrar la procedencia** junto a la skill: `ORIGEN.txt` (ver `templates/ORIGEN.example.txt`) con repo,
   commit, fecha, licencia y veredicto; conservar `LICENSE` y `NOTICE` del original.
7. **Verificar la carga**: que el agente la liste con la descripción de su frontmatter.
8. **Desactivar autoactualizaciones** silenciosas si la skill las trae: lo auditado es un commit, no una rama.

Evitar instaladores de terceros que escriben en rutas propias sin mostrar qué hacen. Si no queda otra:
ejecutarlos primero en modo simulación (`--dry-run`, `--json` si existe), revisar la ruta de destino y los
perfiles (nunca «todo»; sin hooks si es opcional).

## Herramientas Python o Node: aisladas

- **Nunca** instalar en el Python del agente o del sistema: un paquete puede actualizar dependencias fijadas y
  romper otras herramientas. Usar un entorno propio por herramienta:
  ```bash
  uv tool install <paquete>==<versión>                 # o: uv venv .venv-herramienta && uv pip install ...
  pipx install <paquete>==<versión>
  ```
- Al invocarla desde un shell que tiene otro entorno activo, limpiar `PYTHONPATH` para que no mezcle
  bibliotecas (`env -u PYTHONPATH <herramienta> …`).
- npm: `npm install --ignore-scripts` y revisar los scripts del paquete antes de permitirlos; fijar versión
  exacta y conservar el lockfile.
- Paquete con el mismo nombre que el repo: verificar que su campo `repository` apunta al repo auditado
  (typosquatting).

## Después

- Volver a auditar al actualizar: comparar el commit nuevo con el auditado (`git diff <viejo>..<nuevo>`) y
  correr `auditar.py` otra vez.
- Si algo se instaló sin aprobación: preservar lo hecho fuera del árbol de skills, retirarlo y verificar con
  una búsqueda que no quede rastro. Decirlo, no esconderlo.
