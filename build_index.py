#!/usr/bin/env python3
"""build_index.py - Build the course VECTOR DATABASE (RAG, build side).

A computer does not understand "text", but it does understand NUMBERS.
An "embedding" turns a piece of text into a list of numbers (a vector)
that captures its MEANING. Texts with similar meaning get similar vectors.

Pipeline (3 steps):
  1) CHUNK   : split the course into small pieces ("chunks").
  2) EMBED   : ask Ollama (nomic-embed-text) for each chunk's vector.
  3) STORE   : save [{modulo, texto, vector}] to indice_vectorial.json.
               That file IS the vector database (no server needed).

At query time rag.py embeds the question and finds the closest chunks.

Requires:  ollama pull nomic-embed-text
Run:       python3 build_index.py
"""
import json, os, sys, urllib.request

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMB  = os.environ.get("OLLAMA_EMBED", "nomic-embed-text")
HERE = os.path.dirname(os.path.abspath(__file__))
CURSO = os.path.join(HERE, "curso", "curso.json")
INDICE = os.path.join(HERE, "indice_vectorial.json")

def embed(texto):
    """Ask Ollama for the vector (embedding) of a text."""
    body = json.dumps({"model": EMB, "prompt": texto}).encode()
    req = urllib.request.Request(HOST+"/api/embeddings", data=body,
                                 headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["embedding"]

def main():
    restart = "--restart" in sys.argv[1:]   # full rebuild (use when the course changed)
    curso = json.load(open(CURSO, encoding="utf-8"))
    # ---- STEP 1: CHUNK (one chunk per lesson + one per glossary) ----
    chunks = []
    for mod, d in curso.items():
        for lec in d["lecciones"]:
            txt = f"[{mod} {d['titulo']}] {lec['concepto']}: {lec['texto']} Ejemplo: {lec.get('ejemplo','')}"
            chunks.append({"modulo": mod, "titulo": d["titulo"], "texto": txt})
        glo = "; ".join(f"{k} = {v}" for k, v in d.get("glosario", {}).items())
        if glo:
            chunks.append({"modulo": mod, "titulo": d["titulo"], "texto": f"[{mod} {d['titulo']}] Glosario: {glo}"})

    # ---- STEP 2: EMBED. CONTINUE by default (keep vectors already computed);
    #        --restart rebuilds from scratch. Saves incrementally (crash-safe). ----
    out = []
    if os.path.exists(INDICE) and not restart:
        try: out = json.load(open(INDICE, encoding="utf-8"))
        except Exception: out = []
    done = {c["texto"] for c in out}
    pend = [c for c in chunks if c["texto"] not in done]
    print(f"{len(chunks)} chunks | {len(pend)} to embed | {len(done)} already done | model {EMB}")
    try:
        for i, c in enumerate(pend, 1):
            c["vector"] = embed(c["texto"]); out.append(c)
            if i % 10 == 0 or i == len(pend):
                json.dump(out, open(INDICE, "w", encoding="utf-8"), ensure_ascii=False)  # incremental save
                print(f"  {i}/{len(pend)}")
    except Exception as e:
        json.dump(out, open(INDICE, "w", encoding="utf-8"), ensure_ascii=False)  # keep progress
        print(f"\nERROR embeddings: {e}. Progress saved; re-run to continue. (ollama pull {EMB})")
        return

    # ---- STEP 3: STORE ----
    json.dump(out, open(INDICE, "w", encoding="utf-8"), ensure_ascii=False)
    dim = len(out[0]["vector"]) if out else 0
    print(f"\nDone: {INDICE}")
    print(f"{len(out)} vectors of {dim} dimensions each. This is your vector DB.")

if __name__ == "__main__":
    main()
