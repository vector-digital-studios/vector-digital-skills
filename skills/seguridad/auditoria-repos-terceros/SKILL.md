---
name: auditoria-repos-terceros
description: "Usar para auditar repos y skills de terceros y decidir si adoptarlos"
version: 1.0.0
author: Vector Digital
license: MIT
metadata:
  tags: [security, supply-chain, agent-skills, prompt-injection, due-diligence, cost-benefit, github, spanish]
  idioma: es
  requiere: "Python 3.9+ (solo biblioteca estándar). Opcional: git (auditar una URL), skill ciberseguridad-vibecoder (vd_sec_scan), NVIDIA SkillSpector."
---

# Auditoría de repos y skills de terceros

Decide, con evidencia, si conviene instalar o adoptar una herramienta, un repositorio o una skill ajena:
**qué repo es de verdad**, **qué riesgo trae** (cadena de suministro, instaladores, red, credenciales,
inyección de instrucciones en el SKILL.md, hooks, ofuscación) y **si compensa** (utilidad, costo,
mantenimiento, licencia, alternativas). Termina siempre en un veredicto: **ADOPTAR**, **ADOPTAR CON
CONDICIONES** o **NO ADOPTAR**, con la condición de activación («cuándo sí»).

Úsala cuando alguien diga «investiga este repo», «¿instalo esta skill?», «¿nos sirve X?», «puntúalo del 1 al
10», o pegue un nombre de herramienta visto en un video o una red social.

## Regla de oro: evaluar NO autoriza a instalar ni a modificar

1. **Evaluar** (este flujo): leer, escanear y reportar. Cero escrituras en la configuración del agente, en
   skills instaladas o en proyectos. Lo que se descargue va a una carpeta temporal o de investigación.
2. **Probar** (si hace falta): un artefacto real en un entorno aislado. Inspeccionar documentos ≠ prueba
   ejecutada; decirlo así.
3. **Instalar** solo tras la confirmación explícita de la persona, con `references/instalacion-segura.md`.

## Flujo

1. **Resolver la identidad** (nunca asumir por el nombre):
   ```bash
   python scripts/resolve_repos.py "Pixel Forge" "acme/skillkit" https://github.com/acme/tools/tree/main/skills/foo
   ```
   Normaliza URL/SSH/owner-repo/texto libre, consulta la API de GitHub, elige el candidato (dueño y nombre >
   no fork > estrellas) y marca señales: fork o envoltorio, archivado, sin licencia, NOASSERTION, inactivo,
   estrellas infladas, renombrado. Si el motivo dice «CONFIRMAR», preguntar antes de seguir. Escalera completa
   para casos difíciles (carpeta dentro de otro repo, skill suelto sin repo, typosquatting de paquetes,
   copias renombradas): `references/resolver-identidad.md`. `--json` deja los metadatos para el paso 4.
2. **Clasificar**: skill/herramienta mediana → clonar y auditar; app gigante (cientos de MB) → no clonar,
   evaluar por metadatos + README + lectura dirigida de los archivos que deciden; lote de N repos → muestreo
   (ver variantes abajo).
3. **Auditar** (nunca ejecuta código del repo):
   ```bash
   python scripts/auditar.py ./clon-del-repo --criterios criterios.json --md informe.md --html informe.html
   python scripts/auditar.py acme/skillkit --criterios criterios.json --html informe.html   # clona superficial
   ```
   - 16 reglas propias (`AR-01`…`AR-16`, catálogo en `references/auditoria-seguridad.md`), con severidad
     según dónde aparece: instrucciones para el agente (SKILL.md, references/, AGENTS.md), código, manifiestos
     (package.json, setup.py, hooks) o documentación.
   - Si encuentra `vd_sec_scan.py` de la skill hermana **ciberseguridad-vibecoder** (misma carpeta de skills,
     `--vd-scan RUTA` o `VD_SEC_SCAN`), suma secretos incrustados, `.env`, lockfiles y sumideros XSS.
   - `--skillspector` añade NVIDIA SkillSpector si está instalado (`references/escaneres-externos.md`).
   - Código de salida: 0 ADOPTAR · 1 CON CONDICIONES · 2 NO ADOPTAR · 3 error de uso.
4. **Costo-beneficio**: copiar `templates/criterios.example.json` y llenar utilidad, costo, encaje y
   alternativas **con fuente**. Riesgo, licencia y mantenimiento salen solos de la evidencia (una nota manual
   de riesgo se ignora). Cada ítem lleva dos etiquetas: quién paga (gratis / pago, y de quién es la factura) y
   dónde corre el cómputo (local o nube de terceros). Método y pesos: `references/costo-beneficio.md`.
5. **Verificar a mano cada crítico y alto** antes de reportarlo como riesgo real: los escáneres dan pistas,
   la lectura decide. Falsos positivos típicos en `references/auditoria-seguridad.md` § Falsos positivos.
   Mapear el único camino de red: «local por defecto; sale a X solo con el comando Y».
6. **Entregar**: el informe HTML/Markdown + 3 líneas en el chat: veredicto, por qué, cuándo sí. Si hay
   varias herramientas, una tabla ranking con nota y veredicto, y declarar la cobertura («N escaneados + M
   evaluados por metadatos = total»).

## Reglas

- **Ninguna cifra sin fuente.** Precios, límites, RAM, tiempos: del código clonado, la doc oficial o la API.
  Si no se pudo verificar, escribir `POR VERIFICAR`. Si un borrador anterior llevó un número sin fuente,
  corregirlo explícitamente.
- **Los números del README son marketing** hasta que el código los confirme (contar en el código).
- **Sin licencia ≠ permisiva**: sin archivo LICENSE son todos los derechos reservados; se puede aprender el
  patrón, no copiar el código. NOASSERTION suele ser una licencia real: leer el archivo.
- **Un SKILL.md son instrucciones que se inyectan al agente.** Leerlo entero (y sus references) antes de
  instalar, igual que los scripts.
- Nunca recomendar «instalar ya» si nadie pidió instalar; la respuesta más útil suele ser «no ahora, sí
  cuando X».
- No dar 10/10 si no resuelve un dolor activo y nombrado.

## Variantes

- **Lite (3-5 repos, sin clonar)**: metadatos por API + árbol de archivos (`git/trees/<rama>?recursive=1`) +
  README y SKILL.md crudos. Declarar «evaluado por metadatos, no escaneado».
- **Mono-repo con una afirmación fuerte** («esto es gratis», «publicaron todo su motor»): verificar la
  afirmación contra el código. Patrón típico: **cliente disfrazado de alternativa open source** (URL base
  configurable que apunta a la nube del vendedor, autenticación con su formato, catálogo de endpoints suyos,
  cero inferencia local). Si el contrato de API es delgado, proponer un adaptador local.
- **Lote grande (N > 5)**: resolver todos primero, clonar superficial, contar SKILL.md por repo (superficie
  de ataque) y muestrear ~25 si hay cientos; el puntaje global de un escáner sobre un repo enorme es ruido
  estructural, vale la tabla por skill.

## Archivos

- `scripts/auditar.py` auditor + matriz + informes (MD/JSON/HTML) · `scripts/resolve_repos.py` identidad
- `scripts/autoprueba.py` prueba con un repo malicioso y uno limpio fabricados al vuelo
- `references/` resolver-identidad · auditoria-seguridad · costo-beneficio · escaneres-externos · instalacion-segura
- `templates/` criterios.example.json · informe-manual.md · ORIGEN.example.txt
