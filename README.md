# Vector Digital · Skills para agentes de IA

Skills que usamos de verdad en producción en [Vector Digital Studios](https://github.com/vector-digital-studios), en español.
Cada una se publica solo cuando ha pasado por un proyecto real y tiene una prueba propia que la valida.
Funcionan en Claude Code, Codex, Hermes o cualquier agente que lea `SKILL.md`.

## Catálogo

| Dominio | Skill | Qué hace | Versión |
|---|---|---|---|
| seguridad | [ciberseguridad-vibecoder](skills/seguridad/ciberseguridad-vibecoder/) | Audita y blinda webs, apps, juegos y funciones de IA hechas con agentes: 44 controles, escáner pasivo y puerta antes de publicar | 1.1.0 |

Próximos dominios: `video`, `contenido`, `datos`, `juegos`, `operacion`.

## Instalar

**Claude Code** (como plugin, se actualiza solo):
```
/plugin marketplace add vector-digital-studios/vector-digital-skills
/plugin install seguridad@vector-digital-skills
```
**Cualquier agente**: copia la carpeta de la skill en tu directorio de skills
(`~/.claude/skills/`, `~/.codex/skills/`, `~/.hermes/skills/<categoría>/`).

## Estándar de calidad (lo que exige el CI a cada skill)

1. `SKILL.md` con frontmatter válido (`name`, `description`, `version` semver, `license`).
2. `README.md` y `CHANGELOG.md` propios.
3. Una prueba automática (`scripts/autoprueba.py`) que debe pasar en cada cambio.
4. Saneado: sin rutas personales, correos, claves ni datos de clientes (`tools/validar.py`).
5. Créditos de toda idea ajena, aunque no se haya copiado código.

## Estructura

```
skills/<dominio>/<skill>/   SKILL.md · README.md · CHANGELOG.md · references/ · scripts/ · templates/
tools/validar.py            puerta de calidad (local y CI)
.claude-plugin/             catálogo instalable en Claude Code (un plugin por dominio)
```

## Licencia y uso

MIT. Las herramientas de auditoría son pasivas y están pensadas **solo para activos propios o con
autorización escrita**. Se entregan sin garantía: una auditoría reduce riesgo, no lo elimina.
Para reportar un problema de seguridad en este repo, ver [SECURITY.md](SECURITY.md).
