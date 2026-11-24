# Escáneres externos: cuándo y cómo combinarlos

`auditar.py` funciona solo (biblioteca estándar). Estos escáneres se suman como **segunda opinión**; ninguno
sustituye la lectura manual de los críticos y altos.

## vd_sec_scan (skill hermana `ciberseguridad-vibecoder`)

Escáner pasivo del mismo repositorio, también solo biblioteca estándar. `auditar.py` lo busca en este
orden: `--vd-scan RUTA`, variable `VD_SEC_SCAN`, la carpeta hermana `../ciberseguridad-vibecoder/` (la
estructura del repo y del plugin `seguridad`) y las carpetas de skills habituales del usuario
(`~/.claude/skills`, `~/.codex/skills`, `~/.hermes/skills/seguridad`, `~/.agents/skills`).

Aporta: secretos incrustados con patrones de alta confianza (redactados), `.env` en el árbol o versionado,
`package.json` sin lockfile, sumideros XSS, SQL concatenado, CORS abierto, source maps en build. Se corre
como subproceso (`vd_sec_scan.py repo <carpeta> --out <json>`) y sus hallazgos entran al veredicto con su
propio ID de control (`SEC-02`, `SUP-02`…). El aviso «proyecto sin Git» se omite: una carpeta copiada o un
clon superficial no es un riesgo del tercero.

`--sin-vd` lo desactiva.

## NVIDIA SkillSpector (opcional)

Datos verificados el 24-nov-2026 en el repositorio oficial:

- Repositorio: <https://github.com/NVIDIA/SkillSpector> · licencia **Apache-2.0** (archivo `LICENSE` y
  `pyproject.toml`, `license = "Apache-2.0"`) · requiere Python ≥ 3.12 (`requires-python = ">=3.12,<3.16"`).
- Versión en `main` ese día: 2.12.0. El paquete **aún no estaba publicado en PyPI** (la API de PyPI
  respondía 404 para `skillspector`); el README indica instalarlo desde GitHub.
- Instalación recomendada en su README (aislada, sin tocar el Python de tu agente):
  ```bash
  uv tool install --python 3.13 git+https://github.com/NVIDIA/skillspector.git
  skillspector --version
  ```
  Alternativas que documenta: `pipx install --python python3.13 git+https://github.com/NVIDIA/skillspector.git`,
  o un clon con `make install` dentro de un entorno virtual.
- Uso estático sin costo de API: `skillspector scan ./mi-skill/ --no-llm --format json --output informe.json`
  (`--recursive` para carpetas con varias skills).

Con `auditar.py … --skillspector`, si `skillspector` está en el PATH (o en `SKILLSPECTOR_BIN`), se ejecuta
con `--no-llm --format json`, sin `PYTHONPATH` heredado, y el informe muestra su puntaje, su severidad y
hasta 15 hallazgos (ID, patrón, archivo:línea). **No cambian el veredicto por sí solos**: si SkillSpector
dice CRITICAL o HIGH, se añade la condición de revisarlos a mano. Motivo: su puntaje global es sensible al
volumen (repos grandes y legítimos dan 100/100) y marca instaladores sin versión fija como riesgo de cadena
de suministro. Integración probada con SkillSpector 2.5.0; versiones posteriores pueden cambiar el JSON
(el lector es tolerante, pero no está probado con 2.12.0).

Interpretación (experiencia de uso, no documentación de NVIDIA): el puntaje va de 0 a 100 con etiqueta de
severidad; confiar en la tabla por skill, no en el total del repo; los hallazgos YARA sobre archivos que
DESCRIBEN ataques suelen ser falsos positivos. Para aceptar hallazgos ya revisados, SkillSpector tiene
su propio mecanismo de línea base (ver su README).

## Otros escáneres útiles (no integrados)

| Herramienta | Para qué | Cuándo |
|---|---|---|
| `npm audit` | vulnerabilidades conocidas en dependencias npm (necesita lockfile) | repos con `package-lock.json` |
| OSV-Scanner (Google) | vulnerabilidades conocidas en lockfiles de muchos ecosistemas contra la base OSV | repos con dependencias declaradas |
| Socket | análisis de comportamiento de paquetes npm/PyPI (red, instaladores, typosquatting) | antes de añadir una dependencia nueva |

Ninguno de ellos responde «¿compensa adoptarlo?»: esa parte es la matriz de costo-beneficio.
