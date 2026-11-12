#!/usr/bin/env python3
"""ingest_document.py - Turn a document (PDF/TXT/MD) into course modules.

Give it a document on ANY topic and the local LLM generates the course
(modules with concept, text, example and glossary) + quizzes, in the same
format the tutor uses. Then study it with tutor.py.

Flow:
  1) EXTRACT text (PDF via pypdf; txt/md read directly).
  2) CHUNK into "topics" (blocks of ~1200 words).
  3) GENERATE one JSON module per topic with the LLM (+ 3 quiz questions each).
  4) SAVE curso/curso.json + banco.json + a fresh progreso, backing up old files.
  5) (optional) rebuild the vector database.

Usage:
  python3 ingest_document.py my_document.pdf
  python3 ingest_document.py notes.md --append        # add to the current course
  python3 ingest_document.py doc.pdf --no-examen       # skip quiz generation
  python3 ingest_document.py doc.pdf --no-rebuild      # don't rebuild vectors
"""
import json, os, re, sys, datetime, urllib.request, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CURSOF = os.path.join(HERE, "curso", "curso.json")
BANCO = os.path.join(HERE, "banco.json")
PROG = os.path.join(HERE, "progreso", "progreso.json")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

def extraer_texto(path):
    """Extract plain text from a PDF (pypdf) or read a .txt / .md file."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return open(path, encoding="utf-8", errors="ignore").read()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("pypdf is missing. Install it:  pip3 install pypdf"); sys.exit(1)
        r = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in r.pages)
    print(f"Unsupported format: {ext}. Use PDF, TXT or MD."); sys.exit(1)

def trocear(texto, palabras=2000):
    """Split text into chunks of ~`palabras` words; each chunk becomes a module."""
    pals = texto.split()
    return [" ".join(pals[i:i+palabras]) for i in range(0, len(pals), palabras)] or [""]

def ollama(prompt):
    """Ask the model for JSON only (system prompt forces JSON, Spanish, no <think>)."""
    msgs = [{"role":"system","content":"Eres un disenador instruccional. Respondes SOLO con JSON valido, sin texto extra, sin <think>, en espanol."},
            {"role":"user","content":prompt}]
    body = json.dumps({"model":MODEL,"messages":msgs,"stream":False,"think":False,"format":"json"}).encode()
    req = urllib.request.Request(HOST+"/api/chat", data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]

def extraer_json(txt):
    """Pull the first balanced JSON object/array out of the model's reply.

    Local models wrap JSON in prose / code fences / <think> blocks, so we
    strip those and scan for a brace-balanced substring, then json.loads it.
    """
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

def normalizar_modulo(mod, n):
    """Coerce any LLM-produced module into the exact expected shape so that every
    consumer (exam, indexer, wiki, tutor) can rely on concepto/texto/ejemplo keys.
    Local models sometimes use different keys (e.g. 'contenido') or omit fields."""
    if not isinstance(mod, dict): mod = {}
    mod["titulo"] = str(mod.get("titulo") or f"Tema {n}")
    mod["porque_importa"] = str(mod.get("porque_importa") or "")
    lecs = mod.get("lecciones")
    if not isinstance(lecs, list) or not lecs:
        lecs = [{"concepto": mod["titulo"], "texto": "", "ejemplo": ""}]
    norm = []
    for l in lecs:
        if not isinstance(l, dict): l = {"texto": str(l)}
        norm.append({
            "concepto": str(l.get("concepto") or l.get("tema") or ""),
            "texto":    str(l.get("texto") or l.get("contenido") or l.get("descripcion") or ""),
            "ejemplo":  str(l.get("ejemplo") or l.get("example") or ""),
        })
    mod["lecciones"] = norm
    glo = mod.get("glosario")
    mod["glosario"] = glo if isinstance(glo, dict) else {}
    return mod

def generar_modulo(chunk, n):
    """Ask the LLM to turn one text chunk into a course-module JSON (with retries)."""
    p = (f"Con base UNICAMENTE en este texto, genera un modulo de curso en JSON con esta forma exacta:\n"
         '{"titulo":"...","porque_importa":"una frase","lecciones":[{"concepto":"...","texto":"2-3 frases","ejemplo":"..."}],'
         '"glosario":{"termino":"traduccion al ingles"}}\n'
         "2 o 3 lecciones, 3 a 5 terminos de glosario. SOLO JSON.\n\nTEXTO:\n" + chunk[:12000])
    for _ in range(2):   # retry once if the JSON doesn't parse
        j = extraer_json(ollama(p))
        if isinstance(j, dict) and j.get("lecciones"):
            return normalizar_modulo(j, n)
    # Fallback: minimal module built straight from the raw text.
    return normalizar_modulo({"titulo": f"Tema {n}", "porque_importa": "Generado del documento.",
            "lecciones": [{"concepto": f"Tema {n}", "texto": chunk[:400], "ejemplo": ""}], "glosario": {}}, n)

def _as_list(j):
    """Return a list of questions whether the model returned a bare JSON array
    or an object that wraps the array (e.g. {"preguntas":[...]}). With
    Ollama's format=json the model often wraps the list in an object."""
    if isinstance(j, list): return j
    if isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list): return v
    return []

def _preguntas_validas(qs):
    """Keep only well-formed questions: q text, an options dict, ok inside it."""
    return [q for q in qs if isinstance(q, dict) and q.get("q")
            and isinstance(q.get("op"), dict) and q.get("ok") in q.get("op", {})]

def generar_examen(mod_json):
    """Best-effort: ask the LLM for 3 multiple-choice questions about a module."""
    base = str(mod_json.get("titulo","")) + " - " + " ".join(l.get("texto","") for l in mod_json.get("lecciones",[]))
    p = ('Genera 3 preguntas de opcion multiple en JSON sobre este contenido, como una lista '
         'bajo la clave "preguntas". Cada pregunta: {"q":"...","op":{"a":"...","b":"...","c":"...","d":"..."},"ok":"a","exp":"..."}. '
         "ok es la letra correcta. SOLO JSON.\n\nCONTENIDO:\n" + base[:4000])
    return _preguntas_validas(_as_list(extraer_json(ollama(p))))

def main():
    args = list(sys.argv[1:])
    flags = {a for a in args if a.startswith("--")}
    archivos = [a for a in args if not a.startswith("--")]
    if not archivos:
        print("Usage: python3 ingest_document.py <file.pdf|.txt|.md> [--append] [--restart] [--no-examen] [--no-rebuild]"); return
    doc = archivos[0]
    if not os.path.exists(doc): print(f"Not found: {doc}"); return
    append = "--append" in flags; examen = "--no-examen" not in flags; rebuild = "--no-rebuild" not in flags

    print(f"Reading {doc} ...")
    texto = extraer_texto(doc)
    chunks = trocear(texto)
    print(f"{len(texto.split())} words -> {len(chunks)} topic(s). Generating with {MODEL} (may take a while)...")

    doc_abs = os.path.abspath(doc)
    STATE = os.path.join(HERE, ".ingest_state.json")   # resume checkpoint
    restart = "--restart" in flags

    # RESUME: if a previous run on THIS same document was interrupted, pick up
    # where it left off instead of regenerating everything from T1.
    done = 0
    st = {}
    if os.path.exists(STATE):
        try: st = json.load(open(STATE, encoding="utf-8"))
        except Exception: st = {}
    resume = (not append and not restart and os.path.exists(CURSOF)
              and st.get("doc") == doc_abs and st.get("total") == len(chunks))

    if resume:
        curso = json.load(open(CURSOF, encoding="utf-8"))
        banco = json.load(open(BANCO, encoding="utf-8")) if os.path.exists(BANCO) else {}
        done = int(st.get("done", 0))
        print(f"Resuming: {done}/{len(chunks)} modules already built; continuing from T{done+1}.")
    else:
        curso = json.load(open(CURSOF, encoding="utf-8")) if (append and os.path.exists(CURSOF)) else {}
        banco = json.load(open(BANCO, encoding="utf-8")) if (append and os.path.exists(BANCO)) else {}
        # Back up existing files ONCE, up front (only on a fresh/append start).
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        for f in (CURSOF, BANCO, PROG):
            if os.path.exists(f):
                try: open(f + f".bak-{ts}", "w", encoding="utf-8").write(open(f, encoding="utf-8").read())
                except Exception: pass
    base_n = len(curso) if append else 0
    os.makedirs(os.path.dirname(CURSOF), exist_ok=True)

    for i, ch in enumerate(chunks, 1):
        key = f"T{base_n+i}"
        if (not append) and i <= done:   # already built in a previous run -> skip
            continue
        print(f"  {key}: generating module...")
        mod = generar_modulo(ch, base_n+i); curso[key] = mod
        if examen:
            print(f"  {key}: generating quiz...")
            qs = generar_examen(mod)
            if qs: banco[key] = qs
        # INCREMENTAL SAVE + checkpoint: persist after every module so progress
        # is visible, a crash never loses work, and a re-run can resume here.
        json.dump(curso, open(CURSOF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(banco, open(BANCO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump({"doc": doc_abs, "total": len(chunks), "done": i},
                  open(STATE, "w", encoding="utf-8"))
        print(f"  {key}: saved ({i}/{len(chunks)})")
    # Finished this document: clear the checkpoint so a later re-run starts clean.
    try: os.remove(STATE)
    except Exception: pass
    # Fresh progress for the new syllabus (first module unlocked).
    ks = list(curso.keys())
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    mods = {k: {"titulo": curso[k].get("titulo", k), "estado": "pendiente" if j == 0 else "bloqueado",
                "mejor_puntaje": 0, "intentos": 0} for j, k in enumerate(ks)}
    json.dump({"alumno": "", "idioma": "es+en", "ultima_sesion": None, "modulo_actual": ks[0], "modulos": mods},
              open(PROG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nCourse generated: {len(ks)} modules.")

    if rebuild:
        print("Rebuilding vector database...")
        try: subprocess.run([sys.executable, os.path.join(HERE, "build_index.py"), "--restart"], check=False)
        except Exception as e: print(f"(index not rebuilt: {e}. Run: python3 build_index.py)")
    print("Done. Study with:  python3 tutor.py")

if __name__ == "__main__":
    main()
