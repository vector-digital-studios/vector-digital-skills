# Tres formas de programar el newsletter

La edición la redacta un agente; lo que se programa es **cuándo** se le pide. Elige una vía.

## A. Cron de Hermes Agent (la vía usada en producción)
Hermes ejecuta un agente con la skill cargada a la hora indicada y entrega el resultado donde digas.
Sintaxis comprobada con `hermes cron create --help`:
```bash
hermes cron create "0 8 * * *" "$(cat templates/programar/prompt-agente.md)" \
  --name "Newsletter IA" --skill newsletter-ia --timezone America/Lima --deliver local
```
- `--deliver`: `local`, `origin`, `telegram`, `discord`… (ver `hermes cron create --help`).
- Para inyectar las candidatas en el prompt sin gastar una herramienta, copia un envoltorio a
  `~/.hermes/scripts/` y añade `--script`: su salida estándar se pega en el prompt en cada ejecución.
  ```bash
  # ~/.hermes/scripts/radar_candidatas.sh
  python ~/.hermes/skills/contenido/newsletter-ia/scripts/recolectar.py \
    --fuentes ~/.hermes/newsletter/fuentes.json --max 20
  ```
- Revisa ejecuciones con `hermes cron runs` y la salud con `hermes cron doctor`.

## B. GitHub Actions
`templates/programar/github-actions.yml` corre la autoprueba y el recolector a diario y guarda
`candidatas.json` como artefacto. El paso de redacción con un agente viene comentado: necesita un
secreto `ANTHROPIC_API_KEY` (crédito de API) y no se ha probado en esta versión. Cópialo a
`.github/workflows/newsletter-ia.yml` del repositorio donde vivan tus ediciones.

## C. Tarea programada del sistema
Programa al agente de terminal que uses (Claude Code, Codex…) con el mismo prompt.

Linux / macOS (`crontab -e`):
```
0 8 * * * cd ~/newsletter && claude -p "$(cat prompt-agente.md)" >> radar.log 2>&1
```
Windows (Programador de tareas, desde PowerShell):
```powershell
schtasks /Create /SC DAILY /ST 08:00 /TN "Newsletter IA" /TR "powershell -NoProfile -File C:\newsletter\radar.ps1"
```
donde `radar.ps1` entra en la carpeta y ejecuta el agente con el prompt. Comprueba la primera
ejecución a mano (`schtasks /Run /TN "Newsletter IA"`) antes de confiar en ella.

## Coste
El recolector, el verificador y el generador no llaman a ninguna API. El único coste es el del modelo
que redacta (búsquedas, lectura de 5-10 fuentes y escritura): mídelo en tu proveedor las primeras semanas.
