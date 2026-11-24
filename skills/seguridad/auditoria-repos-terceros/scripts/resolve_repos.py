#!/usr/bin/env python
"""resolve_repos.py — resolver qué repositorio es REALMENTE el que alguien menciona (solo biblioteca estándar).

Uso:
  python resolve_repos.py "Pixel Forge" "acme/skillkit" https://github.com/acme/tools/tree/main/skills/foo
  python resolve_repos.py --offline "git@github.com:Acme/Repo.git"      # solo normaliza, sin red
  python resolve_repos.py --json "acme/skillkit" > metadatos.json        # salida para auditar.py --criterios

Para cada nombre: normaliza la etiqueta (URL, SSH, owner/repo, texto libre), consulta GET /repos/{owner}/{repo}
y, si no existe o la etiqueta es texto libre, busca con /search/repositories y elige el candidato que mejor
calza (nombre exacto > no fork > más estrellas). Reporta señales de riesgo: fork o envoltorio, archivado,
sin licencia, licencia NOASSERTION (verificar el archivo LICENSE), inactividad, estrellas desproporcionadas.

Red: solo api.github.com. Sin token: 60 consultas/h y 10 búsquedas/min (se espera SEARCH_SLEEP s entre
búsquedas). Con la variable GITHUB_TOKEN el límite sube; el token nunca se imprime.
Código de salida: 0 = todo resuelto, 1 = alguno sin resolver, 2 = error de uso.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
SEARCH_SLEEP = float(os.environ.get("RESOLVE_SEARCH_SLEEP", "8"))
_ultima_busqueda = [0.0]

_GH_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/(?:tree|blob)/([^/\s]+)(?:/(.+?))?|/[^\s?#]*)?/?(?:[?#].*)?$", re.I)
_SSH = re.compile(r"^git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", re.I)
_RAW = re.compile(r"^(?:https?://)?raw\.githubusercontent\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/([^/]+)/(.+)$", re.I)
_SLUG = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def normalizar(etiqueta):
    """Convierte lo que escribió una persona en {tipo, owner, repo, rama, subruta, consulta}.

    tipo: 'github' (owner/repo identificable), 'texto' (hay que buscar) o 'externo' (URL que no es GitHub).
    owner y repo se devuelven en minúsculas para comparar; la consulta de búsqueda conserva las palabras.
    """
    s = (etiqueta or "").strip().strip("\"'<>")
    out = {"etiqueta": etiqueta, "tipo": "texto", "owner": None, "repo": None, "rama": None,
           "subruta": None, "consulta": None}
    for rx in (_GH_URL, _SSH):
        m = rx.match(s)
        if m:
            g = m.groups()
            out.update(tipo="github", owner=g[0].lower(), repo=g[1].lower())
            if len(g) > 2:
                out["rama"], out["subruta"] = g[2], (g[3].rstrip("/") if g[3] else None)
            return out
    m = _RAW.match(s)
    if m:
        out.update(tipo="github", owner=m.group(1).lower(), repo=m.group(2).lower(), rama=m.group(3),
                   subruta=os.path.dirname(m.group(4)) or None)
        return out
    if re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        out.update(tipo="externo", consulta=s)
        return out
    m = _SLUG.match(s)
    if m and " " not in s:
        out.update(tipo="github", owner=m.group(1).lower(), repo=m.group(2).lower())
        return out
    # Texto libre: "Pixel Forge", "forja-pixel (la de diseño)" -> palabras para la búsqueda
    q = re.sub(r"\([^)]*\)", " ", s)
    q = re.sub(r"[^\w\s.-]", " ", q)
    out["consulta"] = re.sub(r"\s+", " ", q).strip()
    return out


def _compacto(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def elegir(candidatos, etiqueta):
    """Elige el candidato que mejor calza con la etiqueta. Devuelve (elegido, motivo, alternativas)."""
    if not candidatos:
        return None, "sin candidatos", []
    n = normalizar(etiqueta)
    objetivo = _compacto(n["repo"] or n["consulta"] or etiqueta)
    objetivo_owner = n["owner"]

    def clave(c):
        nombre = _compacto(c.get("name"))
        dueno = (c.get("owner") or {}).get("login", "").lower() if isinstance(c.get("owner"), dict) else ""
        return (
            1 if objetivo_owner and dueno == objetivo_owner else 0,
            1 if nombre == objetivo else 0,
            1 if objetivo and objetivo in nombre else 0,
            0 if c.get("fork") else 1,
            0 if c.get("archived") else 1,
            c.get("stargazers_count") or 0,
        )

    orden = sorted(candidatos, key=clave, reverse=True)
    k = clave(orden[0])
    motivo = ("dueño y nombre coinciden" if k[0] and k[1] else "nombre exacto" if k[1] else
              "nombre parecido" if k[2] else "solo por relevancia de la búsqueda: CONFIRMAR con la persona")
    return orden[0], motivo, [c.get("full_name") for c in orden[1:4]]


def senales(info, ahora=None):
    """Señales de riesgo/identidad a partir de los metadatos de la API de GitHub (dict)."""
    ahora = ahora or datetime.now(timezone.utc)
    s = []
    if info.get("fork"):
        padre = (info.get("parent") or {}).get("full_name")
        s.append(f"FORK de {padre}" if padre else "FORK (original desconocido)")
    if info.get("archived"):
        s.append("ARCHIVADO: sin mantenimiento")
    lic = (info.get("license") or {}).get("spdx_id") if info.get("license") else None
    if not lic:
        s.append("SIN LICENCIA: todos los derechos reservados (no copiar código)")
    elif lic == "NOASSERTION":
        s.append("licencia NOASSERTION: leer el archivo LICENSE (suele ser una licencia real con cabecera propia)")
    pushed = info.get("pushed_at")
    if pushed:
        try:
            dias = (ahora - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days
            if dias > 365:
                s.append(f"inactivo: último push hace {dias} días")
            elif dias > 90:
                s.append(f"poco activo: último push hace {dias} días")
        except ValueError:
            pass
    est, mir = info.get("stargazers_count") or 0, info.get("subscribers_count")
    joven = False
    try:
        joven = (ahora - datetime.fromisoformat(str(info.get("created_at")).replace("Z", "+00:00"))).days < 365
    except ValueError:
        pass
    de_persona = (info.get("owner") or {}).get("type", "User") == "User"
    if mir and est >= 1000 and est / max(mir, 1) > 50 and joven and de_persona:
        # Solo cuenta junto con: repo de menos de un año y de una cuenta personal (las organizaciones
        # grandes atraen estrellas de golpe en un lanzamiento sin que nadie las infle).
        s.append(f"estrellas/observadores = {est // max(mir, 1)}:1 (lo normal es 10-30:1) en un repo personal de menos "
                 "de un año: posible inflado")
    if info.get("_renombrado_de"):
        s.append(f"renombrado: se pidió {info['_renombrado_de']}")
    return s


def _gh(ruta):
    cab = {"Accept": "application/vnd.github+json", "User-Agent": "auditoria-repos-terceros"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        cab["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(API + ruta, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            datos = json.loads(r.read().decode("utf-8"))
            if r.geturl().rstrip("/") != (API + ruta).rstrip("/"):
                datos["_redirigido"] = True
            return datos
    except urllib.error.HTTPError as e:
        return {"_error": e.code}
    except Exception as e:  # noqa: BLE001 — red caída, DNS, tiempo
        return {"_error": type(e).__name__}


def _buscar(q):
    espera = SEARCH_SLEEP - (time.time() - _ultima_busqueda[0])
    if espera > 0 and _ultima_busqueda[0]:
        time.sleep(espera)
    _ultima_busqueda[0] = time.time()
    r = _gh("/search/repositories?q=" + urllib.parse.quote(q) + "&per_page=5")
    if r.get("_error") == 403:  # límite de búsqueda: reintentar una vez
        time.sleep(SEARCH_SLEEP * 2)
        r = _gh("/search/repositories?q=" + urllib.parse.quote(q) + "&per_page=5")
    return r.get("items", []) if not r.get("_error") else []


def resolver(etiqueta):
    n = normalizar(etiqueta)
    res = {"etiqueta": etiqueta, "normalizado": n, "metodo": None, "repo": None, "alternativas": [],
           "senales": []}
    info = None
    if n["tipo"] == "github":
        info = _gh(f"/repos/{n['owner']}/{n['repo']}")
        if info.get("_error"):
            res["error_directo"] = info["_error"]
            info = None
        else:
            res["metodo"] = "directo"
            if info.get("full_name", "").lower() != f"{n['owner']}/{n['repo']}":
                info["_renombrado_de"] = f"{n['owner']}/{n['repo']}"
            if n["subruta"]:
                c = _gh(f"/repos/{info['full_name']}/contents/{urllib.parse.quote(n['subruta'])}")
                res["subruta_existe"] = not c.get("_error") if isinstance(c, dict) else True
    if info is None and n["tipo"] != "externo":
        q = n["consulta"] or (n["repo"] or "")
        hits = _buscar(q)
        elegido, motivo, alt = elegir(hits, etiqueta)
        if elegido:
            res["metodo"] = f"búsqueda '{q}': {motivo}"
            res["alternativas"] = alt
            full = _gh("/repos/" + elegido["full_name"])  # trae parent y subscribers_count
            info = elegido if full.get("_error") else full
    if info is None:
        res["metodo"] = res["metodo"] or ("URL externa: no es GitHub" if n["tipo"] == "externo" else "sin resultados")
        return res
    lic = (info.get("license") or {}).get("spdx_id") if info.get("license") else None
    res["repo"] = {
        "full_name": info.get("full_name"), "url": info.get("html_url"), "descripcion": info.get("description"),
        "estrellas": info.get("stargazers_count"), "forks": info.get("forks_count"),
        "observadores": info.get("subscribers_count"), "lenguaje": info.get("language"),
        "licencia": lic or "NINGUNA", "creado": (info.get("created_at") or "")[:10],
        "pushed_at": (info.get("pushed_at") or "")[:10], "archivado": bool(info.get("archived")),
        "fork": bool(info.get("fork")), "padre": (info.get("parent") or {}).get("full_name"),
        "tamano_kb": info.get("size"),
    }
    res["senales"] = senales(info)
    return res


def imprimir(r):
    rep = r["repo"]
    if not rep:
        print(f"### {r['etiqueta']} | NO RESUELTO ({r['metodo']})")
        return
    print(f"### {r['etiqueta']} -> {rep['full_name']}  [{r['metodo']}]")
    print(f"    {rep['estrellas']}★ · {rep['lenguaje']} · licencia {rep['licencia']} · último push {rep['pushed_at']}"
          f" · {rep['tamano_kb']} KB")
    if rep["descripcion"]:
        print(f"    {rep['descripcion'][:160]}")
    for s in r["senales"]:
        print(f"    ! {s}")
    if r["alternativas"]:
        print(f"    otros candidatos: {', '.join(r['alternativas'])}")


def main(argv):
    offline, como_json = "--offline" in argv, "--json" in argv
    etiquetas = [a for a in argv if not a.startswith("--")]
    if not etiquetas:
        print(__doc__)
        return 2
    if offline:
        out = [normalizar(e) for e in etiquetas]
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    res = [resolver(e) for e in etiquetas]
    if como_json:
        print(json.dumps(res if len(res) > 1 else res[0], ensure_ascii=False, indent=1))
    else:
        for r in res:
            imprimir(r)
    return 0 if all(r["repo"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
