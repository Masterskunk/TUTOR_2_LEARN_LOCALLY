#!/usr/bin/env python3
"""student_profile.py - Student memory (phase B).

Reads progreso/puntajes.csv and builds a profile: what the student has
mastered, what is in progress, and what needs reinforcing. The tutor reads
it at startup to PERSONALIZE the lesson. It is deterministic (derived from
the student's own scores, nothing invented).

Public functions:
  actualizar_perfil()  -> recompute and write progreso/perfil_alumno.md
  leer_perfil()        -> return the current profile text (for the prompt)
"""
import csv, os, json, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
CSVF = os.path.join(HERE, "progreso", "puntajes.csv")
PROG = os.path.join(HERE, "progreso", "progreso.json")
PERFIL = os.path.join(HERE, "progreso", "perfil_alumno.md")

def _titulos():
    """Map module key -> title, read from progreso.json."""
    if os.path.exists(PROG):
        return {k: v.get("titulo", k) for k, v in json.load(open(PROG, encoding="utf-8"))["modulos"].items()}
    return {}

def _stats():
    """Collect the list of scores per module from puntajes.csv."""
    data = collections.defaultdict(list)
    if os.path.exists(CSVF):
        for r in list(csv.reader(open(CSVF, encoding="utf-8")))[1:]:
            if len(r) >= 4 and r[3].isdigit():
                data[r[1]].append(int(r[3]))
    return data

def actualizar_perfil():
    """Recompute strengths / in-progress / weak areas and write the profile file."""
    data = _stats(); tit = _titulos()
    fuertes = []; progreso = []; debiles = []
    for mod, scs in data.items():
        prom = round(sum(scs)/len(scs)); recientes = scs[-3:]
        fila = (mod, tit.get(mod, mod), prom, len(scs))
        if prom >= 80 and all(s >= 80 for s in recientes): fuertes.append(fila)   # mastered
        elif prom < 60: debiles.append(fila)                                      # weak
        else: progreso.append(fila)                                               # in progress
    debiles.sort(key=lambda x: x[2]); progreso.sort(key=lambda x: x[2])
    # Build the markdown profile (user-facing text stays in Spanish).
    L = ["# Perfil del alumno", f"Actualizado: {datetime.date.today().isoformat()}", ""]
    L.append("## Fortalezas")
    L += [f"- {m} {t} (prom {p}, {n} ejercicios)" for m, t, p, n in fuertes] or ["- (aun ninguna consolidada)"]
    L.append("\n## En progreso")
    L += [f"- {m} {t} (prom {p})" for m, t, p, n in progreso] or ["- (nada por ahora)"]
    L.append("\n## A reforzar")
    L += [f"- {m} {t} (prom {p})" for m, t, p, n in debiles] or ["- (nada por ahora)"]
    L.append("\n## Recomendacion")
    if debiles: L.append(f"- Repasar primero {debiles[0][0]} {debiles[0][1]} (es lo mas flojo).")
    elif progreso: L.append(f"- Afianzar {progreso[0][0]} {progreso[0][1]} antes de avanzar.")
    else: L.append("- Vas bien; continua con el siguiente modulo.")
    os.makedirs(os.path.dirname(PERFIL), exist_ok=True)
    open(PERFIL, "w", encoding="utf-8").write("\n".join(L))
    return PERFIL

def leer_perfil(max_chars=900):
    """Return the current profile text (truncated), or '' if none yet."""
    if not os.path.exists(PERFIL): return ""
    return open(PERFIL, encoding="utf-8").read()[:max_chars]

if __name__ == "__main__":
    print("Profile written to:", actualizar_perfil()); print(); print(leer_perfil())
