"""Prueba básica de los scripts del consejo (solo stdlib, sin red ni modelos).

Uso: python tests/prueba_basica.py
Crea una carpeta temporal con el encuadre ficticio de templates/ y cinco respuestas falsas de asesores, y comprueba:
  1. revisar_encuadre.py: código 0 con el ejemplo y código 3 al quitar una «Señal temprana».
  2. sala.py sellar: sella, reconoce un sello intacto y detecta la manipulación (código 3).
  3. barajar.py: código 0, cinco respuestas anónimas sin nombres de papel y recuento correcto.
  4. sala.py asesores: 4 tareas + _fable_contrario.md; con --todo-opus, 5 tareas y sin archivo para el otro modelo.
  5. registro.py: alta, resolver y resumen con Brier correcto (70 % que ocurre + 30 % que no ocurre → 0,09).
Sale con código 0 si todo pasa y 1 si algo falla.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
EJEMPLO = RAIZ / "templates" / "ejemplo_encuadre.md"
ROLES = ["El Contrario", "Primeros Principios", "El Expansionista", "El de Afuera", "El Ejecutor"]

ENCUADRE_AFUERA = """# Decisión: qué hacer con el sistema principal de una empresa pequeña

## Opciones
- A: rehacerlo todo desde cero y cambiarlo de una vez
- B: cambiar una pieza cada vez, empezando por la que más falla
- C: dejarlo como está y dedicar un día por semana a reforzarlo

## Qué está en juego
Dos meses de trabajo de un equipo pequeño y la estabilidad que exige su cliente principal.
"""

ASESORES_FALSOS = {
    "asesor_1_contrario.md": ("Si se elige reescribir, el equipo se queda sin funciones nuevas durante meses y el "
                              "cliente principal se impacienta. Si se migra por partes, la base de datos compartida "
                              "puede frenar la separación de pagos.",
                              "B acotada: solo pagos durante el horizonte", "C", "6/10",
                              "que la base de datos compartida impida separar pagos", "A"),
    "asesor_2_principios.md": ("El objetivo no está declarado. Si es estabilidad, pagos concentra la mayoría de las "
                               "incidencias graves y conviene atacarlo primero.",
                               "B", "C", "7/10", "que el objetivo declarado sea reducir costos", "ninguna"),
    "asesor_3_expansionista.md": ("Separar pagos abre la puerta a ofrecerlo a otros clientes si sale bien.",
                                  "B", "A", "7/10", "que la capa de reparto añada más de 8 horas semanales",
                                  "ninguna"),
    "asesor_4_afuera.md": ("Desde fuera, cambiar una pieza cada vez es lo que suele hacer la gente que no puede parar "
                           "su sistema (conocimiento general).",
                           "B", "C", "6/10", "que el sistema pueda pararse varios días sin daño", "ninguna"),
    "asesor_5_ejecutor.md": ("El primer paso es medir cuántas reglas de negocio no documentadas hay: dos días de "
                             "lectura. Luego, la capa de reparto delante de pagos.",
                             "C", "B", "5/10", "que la lectura muestre menos de diez reglas ocultas", "B"),
}

VEREDICTO = """## Veredicto del consejo
**Recomendación:** migrar por partes empezando por pagos.
**Confianza:** 6/10 — falta medir las reglas ocultas.
### 1. Dónde coincide el consejo
x
### 2. Dónde choca
x
### 3. Puntos ciegos
x
### 4. Por qué esta recomendación
x
### 5. El primer paso
x
### 6. Si sale mal
x
### 7. Predicciones comprobables
- P1 | 2030-01-15 | 70 % | pagos servido por el módulo nuevo | panel de monitorización
- P2 | 2030-02-15 | 30 % | incidencias de pagos por encima de 5 | historial de incidencias
**Criterio de corte:** si el 2030-02-15 pagos no está separado, se revisa.
### 8. Límites
x
**Hechos de los que depende:** x
**Qué invertiría el veredicto:** x
"""

resultados = []


def correr(*args):
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=entorno)
    return r.returncode, r.stdout + r.stderr


def comprobar(nombre, condicion, detalle=""):
    resultados.append((nombre, bool(condicion)))
    print("%s  %s%s" % ("OK   " if condicion else "FALLA", nombre, "" if condicion else "\n       " + detalle[-800:]))


def escribible(funcion, ruta, _):
    os.chmod(ruta, stat.S_IWRITE)
    funcion(ruta)


def preparar(base, nombre):
    c = base / nombre
    c.mkdir()
    shutil.copyfile(str(EJEMPLO), str(c / "encuadre.md"))
    (c / "encuadre_afuera.md").write_text(ENCUADRE_AFUERA, encoding="utf-8")
    (c / "preferencia.txt").write_text("ninguna declarada\n", encoding="utf-8")
    return c


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    base = Path(tempfile.mkdtemp(prefix="consejo_prueba_"))
    try:
        c = preparar(base, "2030-01-01_backend")

        # 1. revisar_encuadre
        codigo, salida = correr(SCRIPTS / "revisar_encuadre.py", c)
        comprobar("revisar_encuadre: el ejemplo pasa (código 0)", codigo == 0, salida)
        c2 = preparar(base, "2030-01-01_sin_senal")
        texto = (c2 / "encuadre.md").read_text(encoding="utf-8")
        recortado = "\n".join(l for l in texto.splitlines() if not l.startswith("Señal temprana para A"))
        comprobar("el ejemplo trae una línea «Señal temprana para A»", recortado != texto.rstrip("\n"))
        (c2 / "encuadre.md").write_text(recortado + "\n", encoding="utf-8")
        codigo, salida = correr(SCRIPTS / "revisar_encuadre.py", c2)
        comprobar("revisar_encuadre: sin «Señal temprana para A» falla (código 3) y nombra la opción A",
                  codigo == 3 and "opción A" in salida, salida)

        # 2. sellar y detectar manipulación
        codigo, salida = correr(SCRIPTS / "sala.py", "sellar", c, "encuadre.md")
        comprobar("sellar: primer sello (código 0)", codigo == 0 and "SELLADO" in salida, salida)
        codigo, salida = correr(SCRIPTS / "sala.py", "sellar", c, "encuadre.md")
        comprobar("sellar: sello intacto reconocido (código 0)", codigo == 0 and "Ya estaba sellado" in salida,
                  salida)
        sellos = json.loads((c / "sellos.json").read_text(encoding="utf-8"))
        comprobar("sellos.json guarda el md5 del encuadre", len(sellos.get("encuadre.md", {}).get("md5", "")) == 32)
        c3 = base / "manipulado"
        shutil.copytree(str(c), str(c3))
        ruta = c3 / "encuadre.md"
        os.chmod(str(ruta), stat.S_IWRITE)
        ruta.write_text(ruta.read_text(encoding="utf-8") + "\nUna línea añadida después del sello.\n",
                        encoding="utf-8")
        codigo, salida = correr(SCRIPTS / "sala.py", "sellar", c3, "encuadre.md")
        comprobar("sellar: detecta la manipulación (código 3)", codigo == 3, salida)

        # 3. barajar
        for archivo, (cuerpo, postura, segunda, conf, cambiar, favorece) in ASESORES_FALSOS.items():
            (c / archivo).write_text("%s\n\nPOSTURA: %s\nSEGUNDA OPCIÓN: %s\nCONFIANZA: %s\nME HARÍA CAMBIAR: %s\n"
                                     "EL ENCUADRE FAVORECE: %s\n" % (cuerpo, postura, segunda, conf, cambiar,
                                                                     favorece), encoding="utf-8")
        codigo, salida = correr(SCRIPTS / "barajar.py", c, "--semilla", "7")
        comprobar("barajar: código 0", codigo == 0, salida)
        anonimas = (c / "anonimas.md").read_text(encoding="utf-8")
        fugas = [r for r in ROLES if r in anonimas]
        comprobar("barajar: anonimas.md sin nombres de papel", not fugas, str(fugas))
        comprobar("barajar: cinco respuestas R1-R5", all("## Respuesta R%d" % i in anonimas for i in range(1, 6)))
        recuento = json.loads((c / "recuento.json").read_text(encoding="utf-8"))
        comprobar("barajar: recuento B 4 · C 1, sin unanimidad, 1 con matiz",
                  recuento["votos"] == {"B": 4, "C": 1} and not recuento["unanimidad"] and recuento["con_matiz"] == 1,
                  json.dumps(recuento["votos"]))
        mapa = json.loads((c / "mapa.json").read_text(encoding="utf-8"))
        comprobar("barajar: mapa.json con las cinco etiquetas", sorted(mapa) == ["R1", "R2", "R3", "R4", "R5"])

        # 4. sala.py asesores
        codigo, salida = correr(SCRIPTS / "revisar_encuadre.py", c)  # deja lint_encuadre.json
        (c / "auditoria_encuadre.md").write_text("Sin asimetrías.\nDICTAMEN: APTO\nOPCIÓN FAVORECIDA: ninguna · 20 %\n",
                                                 encoding="utf-8")
        (c / "horario.txt").write_text("tardes de 18 a 21 h de lunes a viernes\n", encoding="utf-8")
        codigo, salida = correr(SCRIPTS / "sala.py", "asesores", c)
        tareas = json.loads((c / "_tareas_asesores.json").read_text(encoding="utf-8")) if codigo == 0 else []
        comprobar("asesores: 4 tareas + _fable_contrario.md",
                  codigo == 0 and len(tareas) == 4 and (c / "_fable_contrario.md").exists(), salida)
        comprobar("asesores: el Contrario no está entre las tareas",
                  not any("(contrario)" in t["goal"] for t in tareas))
        ejecutor = [t for t in tareas if "(ejecutor)" in t["goal"]]
        comprobar("asesores: el Ejecutor recibe el horario configurado",
                  ejecutor and "tardes de 18 a 21 h" in ejecutor[0]["context"]
                  and "{{HORARIO}}" not in ejecutor[0]["context"])
        afuera = [t for t in tareas if "(afuera)" in t["goal"]]
        comprobar("asesores: el de Afuera recibe el encuadre genérico",
                  afuera and "rehacerlo todo desde cero" in afuera[0]["context"]
                  and "41 módulos" not in afuera[0]["context"])
        (c / "_fable_contrario.md").unlink()
        codigo, salida = correr(SCRIPTS / "sala.py", "asesores", c, "--todo-opus")
        tareas = json.loads((c / "_tareas_asesores.json").read_text(encoding="utf-8")) if codigo == 0 else []
        comprobar("asesores --todo-opus: 5 tareas y sin _fable_contrario.md",
                  codigo == 0 and len(tareas) == 5 and not (c / "_fable_contrario.md").exists(), salida)

        # 5. registro
        (c / "veredicto.md").write_text(VEREDICTO, encoding="utf-8")
        reg = base / "registro_prueba.jsonl"
        codigo, salida = correr(SCRIPTS / "registro.py", "--registro", reg, "alta", c, "--llamadas", "8",
                                "--minutos", "12")
        comprobar("registro alta: 2 predicciones (código 0)", codigo == 0 and "2 predicción(es)" in salida, salida)
        slug = c.name
        codigo1, s1 = correr(SCRIPTS / "registro.py", "--registro", reg, "resolver", slug + "#P1", "si",
                             "--evidencia", "panel, prueba")
        codigo2, s2 = correr(SCRIPTS / "registro.py", "--registro", reg, "resolver", slug + "#P2", "no",
                             "--evidencia", "historial, prueba")
        comprobar("registro resolver: P1 = si, P2 = no (código 0)", codigo1 == 0 and codigo2 == 0, s1 + s2)
        codigo, salida = correr(SCRIPTS / "registro.py", "--registro", reg, "resumen")
        comprobar("registro resumen: 2 de 2 aciertos y Brier 0,09", codigo == 0 and "Aciertos: 2 de 2" in salida
                  and "Brier 0,09" in salida, salida)
        sys.path.insert(0, str(SCRIPTS))
        import registro  # noqa: E402
        datos = registro.calcular(registro.cargar(reg))
        comprobar("registro: Brier calculado = 0,09 exacto", abs(datos["brier"] - 0.09) < 1e-9, str(datos["brier"]))
        codigo, salida = correr(SCRIPTS / "registro.py", "--registro", reg, "resumen", "--markdown")
        comprobar("registro resumen --markdown: tabla Markdown", codigo == 0 and "| Puntuación de Brier | 0,09 |"
                  in salida, salida)
    finally:
        shutil.rmtree(str(base), onerror=escribible)

    fallas = [n for n, ok in resultados if not ok]
    print("\nRESULTADO: %d comprobaciones, %d fallas." % (len(resultados), len(fallas)))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
