# Auditoría de seguridad de repos y skills ajenos

Una skill de agente es a la vez **código** (scripts que el agente ejecuta) e **instrucciones** (el SKILL.md
y sus references se inyectan en el contexto del agente con la confianza del usuario). Por eso se audita
como software y como texto. Según el README de NVIDIA SkillSpector, en su conjunto analizado de 31 132
skills el 26,1 % tenía vulnerabilidades y el 5,2 % mostraba intención probablemente maliciosa.

## Contextos (deciden la severidad)

| Contexto | Archivos | Por qué |
|---|---|---|
| instrucciones | `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `references/`, `templates/`, prompts | el agente los obedece |
| código | `.py`, `.js`, `.ts`, `.sh`, `.ps1`… | el agente los ejecuta |
| manifiesto | `package.json`, `setup.py`, `pyproject.toml`, `requirements*`, hooks, `settings.json` | corren solos al instalar o en eventos |
| documentación | `README`, `CHANGELOG`, `docs/`, `examples/` | lo lee una persona; mencionar no es ejecutar |

Si una regla aparece en instrucciones pero la línea es claramente una **cita o advertencia** (va entre
comillas o backticks, es una fila de tabla, o dice «por ejemplo», «nunca», «detectar», «patrón»…), baja dos niveles y queda
`por_validar`. Un atacante también puede citar: por eso no desaparece, queda para lectura manual.

## Catálogo de reglas de `auditar.py`

| ID | Qué busca | Severidad típica |
|---|---|---|
| AR-01 | descarga y ejecución remota: salida de curl/wget o Invoke-WebRequest entubada a un intérprete, `exec` sobre lo que devuelve `urlopen`, `eval` del texto de un `fetch` | crítico (medio en docs) |
| AR-02 | inyección de instrucciones: pedir al agente que descarte lo que se le indicó antes, que oculte algo a la persona, que actúe sin consultarla o que revele su prompt de sistema (inglés y español) | crítico en SKILL.md |
| AR-03 | texto oculto: caracteres de ancho cero, controles bidireccionales (trojan source), comentarios HTML con órdenes dentro del Markdown | alto |
| AR-04 | acceso a credenciales: carpeta de llaves SSH, credenciales de nubes, `.netrc`, `.npmrc`, `.env`, volcado completo del entorno, llavero del sistema | alto; crítico en un hook de instalación |
| AR-05 | envío de datos por red (POST/PUT, subida de archivos, shells inversas) | medio, por validar |
| AR-06 | destinos típicos de exfiltración o C2: webhooks de chat, túneles, servicios de pegado, IP cruda | alto |
| AR-07 | AR-04 + AR-05/06 en el mismo archivo | crítico |
| AR-08 | código que corre al instalar: `preinstall`/`install`/`postinstall` de npm, `setup.py` con red o procesos o `cmdclass`, archivos `.pth` | alto |
| AR-09 | hooks del agente que corren solos (`PreToolUse`, `SessionStart`…), hooks de git, permisos amplios en `settings.json` | medio/alto |
| AR-10 | ofuscación: decodificar (base64/zlib/marshal) y ejecutar; bloques base64 enormes; `fromCharCode` encadenado; hex escapado | crítico / por validar |
| AR-11 | acciones destructivas, persistencia (tareas programadas, rc del shell, registro) o saltarse permisos del agente | alto |
| AR-12 | binarios sin fuente (`.exe`, `.dll`, `.so`, `.pyc`, `.jar`, `.wasm`…) | alto |
| AR-13 | instalaciones sin versión fija (`npx`, `uvx`, `pip install` sin `==`, `git+https` sin commit) | bajo |
| AR-14 | licencia ausente o restrictiva | medio |
| AR-15 | frontmatter de SKILL.md ausente o `allowed-tools` con shell libre | medio/bajo |
| AR-16 | enlace simbólico que apunta fuera del repo | alto |

Los archivos minificados o de `dist/`, `vendor/`, `build/` solo pasan por reglas de alta señal (AR-01,
AR-02, AR-06, AR-10 de decodificar y ejecutar): los patrones genéricos en código empaquetado son falsos
positivos garantizados. Escanear el código fuente, no el paquete compilado.

## Veredicto automático

- Algún **crítico**, o 3+ **altos**, o costo-beneficio < 5, o utilidad ≤ 3 → **NO ADOPTAR**.
- Algún alto o medio, licencia ausente, SkillSpector en CRITICAL/HIGH, costo-beneficio entre 5 y 7, o
  costo-beneficio sin completar → **ADOPTAR CON CONDICIONES** (cada condición queda listada).
- Nada de lo anterior y costo-beneficio ≥ 7 → **ADOPTAR**.

El veredicto automático es el punto de partida. La lectura manual de cada crítico y alto lo confirma o lo
corrige; si se corrige, decir por qué en el informe.

## Falsos positivos frecuentes (verificar antes de alarmar)

| Pista | Suele ser | Cómo confirmarlo |
|---|---|---|
| `exec(compile(` | `re.compile(...)` mal leído, o `exec` de código que el propio paquete genera en `tests/` | leer la línea; preocupa solo en código de ejecución con entrada externa |
| llamada a `eval` | `ast.literal_eval`, `redis.eval`, `.exec()` de una expresión regular | leer el contexto |
| `os.environ.get("…_API_KEY")` | proveedor de LLM estándar | ¿lee UNA variable que necesita o vuelca todo el entorno? |
| «webhook» en un SKILL.md | documentación de una integración | ¿hay un destino concreto y datos que salen? |
| `npm install`/`pip install` sin versión | instrucción documentada para una persona | no se ejecuta sola; igual conviene fijar versiones |
| descarga entubada a intérprete en un README | instalador oficial del proyecto | ¿el dominio es el del propio proyecto? aun así: descargar, leer, ejecutar |
| `fromCharCode`, `exec(` en `dist/*.js` | jQuery u otra biblioteca minificada | leer la cabecera `/*! … */` del archivo |
| servidor local con CORS abierto | relé local (Socket.IO) que no sale a internet | buscar `fetch`/`requests` a dominios remotos en el código fuente |
| puntaje 100/100 en un repo con cientos de skills | ruido estructural por volumen (le pasa también a repos oficiales) | mirar la tabla por skill, no el total |
| «tool poisoning» en un .md de defensa | texto que DESCRIBE el ataque | ¿lo describe o lo instruye? |

**Señales reales**: decodificar y ejecutar, envío a dominios ajenos al proyecto, descarga y ejecución en
tiempo de ejecución, lectura de credenciales que la herramienta no necesita, instrucciones para ocultar
cosas al usuario, hooks de instalación que nadie pidió.

## Mapear la superficie de red

El informe lista todos los dominios citados. Para cada uno: ¿es el servicio propio del proyecto (su API,
su CDN, su documentación) o un tercero? Reportar en una frase: «local por defecto; sale a X solo con el
comando Y y una clave propia». Una URL al dominio del propio proyecto es aceptable; un webhook de chat no.

## Lo que no ve un análisis estático

- Lo que el repo descarga en tiempo de ejecución (por eso AR-01 pesa tanto).
- Dependencias transitivas: usar `npm audit`, OSV-Scanner u otro escáner de dependencias sobre el lockfile.
- Typosquatting de paquetes: se descubre comparando dueño del paquete y dueño del repo (ver
  `resolver-identidad.md`), no leyendo el código.
- Cambios futuros: fijar el commit auditado y volver a auditar al actualizar.
