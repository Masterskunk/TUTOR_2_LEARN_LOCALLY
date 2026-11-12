#!/usr/bin/env python3
"""generate_wiki.py - Build the LLM-wiki from curso/curso.json.

An LLM reads the already-created course content and writes a WIKI:
  - one markdown page per module (wiki/<key>.md),
  - with [[key]] links to related topics (hypertext),
  - plus an index wiki/INDICE.md.
It then builds the wiki's own vector database (indice_wiki.json) so the
tutor can use the WIKI as a selectable "memory type" in mode B.

Run:  python3 generate_wiki.py            (resume: skip pages that already exist)
      python3 generate_wiki.py --restart  (overwrite: regenerate every page)
      python3 generate_wiki.py --no-index (pages only, skip the vector DB)
Requires a chat model + nomic-embed-text.
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CURSOF = os.path.join(HERE, "curso", "curso.json")
WIKIDIR = os.path.join(HERE, "wiki")
INDICE_WIKI = os.path.join(HERE, "indice_wiki.json")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")     # chat model (writes pages)
EMB = os.environ.get("OLLAMA_EMBED", "nomic-embed-text")  # embedding model

def limpiar(t):
    """Strip qwen3 <think> reasoning blocks (closed or unclosed) from output."""
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    return re.sub(r"<think>.*$", "", t, flags=re.S).strip()

def chat(prompt):
    """Ask the chat model to write a wiki page (Spanish content for the learner)."""
    msgs = [{"role":"system","content":"Escribes paginas de wiki claras y correctas en espanol (markdown), bilingue ES/EN en los terminos clave. Sin <think>, sin preambulos."},
            {"role":"user","content":prompt}]
    body = json.dumps({"model":MODEL,"messages":msgs,"stream":False,"think":False}).encode()
    req = urllib.request.Request(HOST+"/api/chat", data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return limpiar(json.loads(r.read())["message"]["content"])

def embed(txt):
    """Ask Ollama for the embedding (vector) of a text."""
    body = json.dumps({"model":EMB,"prompt":txt}).encode()
    req = urllib.request.Request(HOST+"/api/embeddings", data=body, headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["embedding"]

def contenido_modulo(v):
    """Flatten a module's lessons + glossary into a plain text block for the prompt."""
    t = [f"Por que importa: {v.get('porque_importa','')}"]
    for l in v["lecciones"]:
        t.append(f"- {l['concepto']}: {l['texto']} Ejemplo: {l.get('ejemplo','')}")
    if v.get("glosario"):
        t.append("Glosario: " + "; ".join(f"{a}={b}" for a, b in v["glosario"].items()))
    return "\n".join(t)

def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    restart = "--restart" in flags        # overwrite every page
    do_index = "--no-index" not in flags   # also (re)build the vector DB
    curso = json.load(open(CURSOF, encoding="utf-8"))
    claves = list(curso.items())
    listado = "\n".join(f"[[{k}]] = {v['titulo']}" for k, v in claves)  # link menu for the model
    os.makedirs(WIKIDIR, exist_ok=True)

    # ---- 1) One wiki page per module. RESUME by default (skip pages that
    #        already exist); --restart regenerates/overwrites them all. ----
    print(f"Wiki pages: {len(claves)} modules ({'overwrite' if restart else 'resume: skip existing'})...")
    hechas = saltadas = 0
    for k, v in claves:
        pagina = os.path.join(WIKIDIR, f"{k}.md")
        if os.path.exists(pagina) and not restart:
            saltadas += 1; continue     # already generated -> continue from the next one
        prompt = (f"Escribe una pagina de wiki en markdown para el tema {k}: {v['titulo']}.\n"
                  f"Usa SOLO este contenido (no inventes datos):\n{contenido_modulo(v)}\n\n"
                  f"Formato: encabezado '# {v['titulo']}', una explicacion clara y ampliada, "
                  f"ejemplos, un glosario ES<->EN, y al final una seccion '## Relacionado' con 2 o 3 "
                  f"enlaces en formato [[clave]] a temas de esta lista (elige los mas afines):\n{listado}\n"
                  f"Responde SOLO el markdown.")
        try:
            md = chat(prompt)
        except Exception as e:
            print(f"  {k}: LLM error ({e}); using fallback"); md = ""
        if not md:
            md = f"# {v['titulo']}\n\n{contenido_modulo(v)}\n"   # fallback page
        open(pagina, "w", encoding="utf-8").write(md)
        hechas += 1; print(f"  wiki/{k}.md  ({hechas} new)")
    print(f"Pages: {hechas} generated, {saltadas} already existed.")

    # ---- 2) Index page (for humans to navigate) ----
    idx_md = ["# Indice de la wiki\n"]
    for k, v in claves: idx_md.append(f"- [[{k}]] {v['titulo']}")
    open(os.path.join(WIKIDIR, "INDICE.md"), "w", encoding="utf-8").write("\n".join(idx_md))

    if not do_index:
        print("Skipping vector DB (--no-index). Pages are in wiki/."); return

    # ---- 3) Vector DB of the wiki: chunk pages by paragraph, then embed.
    #        CONTINUE by default (keep vectors already computed); --restart rebuilds. ----
    chunks = []
    for k, v in claves:
        pag = open(os.path.join(WIKIDIR, f"{k}.md"), encoding="utf-8").read()
        for parrafo in [p.strip() for p in pag.split("\n\n") if len(p.strip()) > 30]:
            chunks.append({"modulo": k, "titulo": v["titulo"], "texto": f"[{k} {v['titulo']}] {parrafo}"})
    out = []
    if os.path.exists(INDICE_WIKI) and not restart:
        try: out = json.load(open(INDICE_WIKI, encoding="utf-8"))
        except Exception: out = []
    done = {c["texto"] for c in out}
    pend = [c for c in chunks if c["texto"] not in done]
    print(f"Wiki vector DB: {len(chunks)} chunks, {len(pend)} to embed, {len(done)} already done.")
    try:
        for i, c in enumerate(pend, 1):
            c["vector"] = embed(c["texto"]); out.append(c)
            if i % 10 == 0 or i == len(pend):
                json.dump(out, open(INDICE_WIKI, "w", encoding="utf-8"), ensure_ascii=False)  # incremental save
                print(f"  embedded {i}/{len(pend)}")
    except Exception as e:
        json.dump(out, open(INDICE_WIKI, "w", encoding="utf-8"), ensure_ascii=False)  # keep progress
        print(f"ERROR embeddings: {e}. Progress saved; re-run to continue. (ollama pull {EMB})"); return
    json.dump(out, open(INDICE_WIKI, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nDone: {len(claves)} pages in wiki/ and {len(out)} vectors in indice_wiki.json")

if __name__ == "__main__":
    main()
