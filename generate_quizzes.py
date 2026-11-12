#!/usr/bin/env python3
"""generate_quizzes.py - (Re)build the exam bank from curso/curso.json.

Generates 3 multiple-choice questions per module into banco.json, WITHOUT
regenerating the modules. Resumable and crash-safe, same pattern as the rest:

  python3 generate_quizzes.py            # resume: only modules missing an exam
  python3 generate_quizzes.py --restart  # regenerate every module's exam
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CURSOF = os.path.join(HERE, "curso", "curso.json")
BANCO = os.path.join(HERE, "banco.json")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

def ollama(prompt):
    msgs = [{"role":"system","content":"Respondes SOLO con JSON valido, sin texto extra, sin <think>, en espanol."},
            {"role":"user","content":prompt}]
    body = json.dumps({"model":MODEL,"messages":msgs,"stream":False,"think":False,"format":"json"}).encode()
    req = urllib.request.Request(HOST+"/api/chat", data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]

def extraer_json(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    txt = re.sub(r"```json|```", "", txt)
    ini = min([p for p in (txt.find("{"), txt.find("[")) if p != -1], default=-1)
    if ini == -1: return None
    abre = txt[ini]; cierra = "}" if abre == "{" else "]"; prof = 0
    for j in range(ini, len(txt)):
        if txt[j] == abre: prof += 1
        elif txt[j] == cierra:
            prof -= 1
            if prof == 0:
                try: return json.loads(txt[ini:j+1])
                except Exception: return None
    return None

def _as_list(j):
    # Accept a bare JSON array OR an object that wraps the array (format=json habit).
    if isinstance(j, list): return j
    if isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list): return v
    return []

def _validas(qs):
    return [q for q in qs if isinstance(q, dict) and q.get("q")
            and isinstance(q.get("op"), dict) and q.get("ok") in q.get("op", {})]

def examen_de(mod):
    base = str(mod.get("titulo","")) + " - " + " ".join(l.get("texto","") for l in mod.get("lecciones",[]))
    p = ('Genera 3 preguntas de opcion multiple en JSON sobre este contenido, como una lista bajo '
         'la clave "preguntas". Cada pregunta: {"q":"...","op":{"a":"...","b":"...","c":"...","d":"..."},'
         '"ok":"a","exp":"..."}. ok es la letra correcta. SOLO JSON.\n\nCONTENIDO:\n' + base[:4000])
    return _validas(_as_list(extraer_json(ollama(p))))

def main():
    restart = "--restart" in sys.argv[1:]
    curso = json.load(open(CURSOF, encoding="utf-8"))
    banco = {}
    if os.path.exists(BANCO) and not restart:
        try: banco = json.load(open(BANCO, encoding="utf-8"))
        except Exception: banco = {}
    pend = [k for k in curso if restart or not banco.get(k)]
    print(f"Modules: {len(curso)} | exams to generate: {len(pend)} | already have: {len(curso)-len(pend)}")
    for i, k in enumerate(pend, 1):
        qs = examen_de(curso[k])
        if qs: banco[k] = qs
        json.dump(banco, open(BANCO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # incremental
        print(f"  {k}: {len(qs)} questions  ({i}/{len(pend)})")
    con = sum(1 for k in curso if banco.get(k))
    print(f"\nDone: {con}/{len(curso)} modules have exams in banco.json")

if __name__ == "__main__":
    main()
