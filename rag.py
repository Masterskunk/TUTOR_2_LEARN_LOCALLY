#!/usr/bin/env python3
"""rag.py - Vector search ("retrieval" side of the RAG).

Given a question, this module:
  1) turns the QUESTION into a vector with the same embedding model,
  2) compares it against every stored vector using COSINE SIMILARITY,
  3) returns the most similar chunks (higher cosine = more similar).

Cosine similarity measures how "aligned" two vectors point:
  1.0 = identical meaning, 0 = unrelated.   formula: (A . B) / (|A| * |B|)

Used by tutor.py in mode B. buscar() accepts any index path, so the tutor
can switch between the vector index (indice_vectorial.json) and the
wiki index (indice_wiki.json).
"""
import json, os, math, urllib.request

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMB  = os.environ.get("OLLAMA_EMBED", "nomic-embed-text")   # embedding model
HERE = os.path.dirname(os.path.abspath(__file__))
INDICE = os.path.join(HERE, "indice_vectorial.json")        # default index

def embed(texto):
    """Ask Ollama for the embedding (vector) of a piece of text."""
    body = json.dumps({"model": EMB, "prompt": texto}).encode()
    req = urllib.request.Request(HOST+"/api/embeddings", data=body,
                                 headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["embedding"]

def coseno(a, b):
    """Cosine similarity between two vectors (1.0 = same meaning, 0 = unrelated)."""
    punto = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return punto/(na*nb) if na and nb else 0.0

def hay_indice(indice=INDICE):
    """True if the given vector index file exists."""
    return os.path.exists(indice)

def buscar_scored(pregunta, k=4, indice=INDICE):
    """Like buscar(), but returns (score, chunk) pairs so the caller can tell
    whether the best match is actually relevant (score near 0 = not in content)."""
    idx = json.load(open(indice, encoding="utf-8"))
    q = embed(pregunta)
    scored = sorted(((coseno(q, c["vector"]), c) for c in idx), key=lambda x: x[0], reverse=True)
    return scored[:k]

def buscar(pregunta, k=4, indice=INDICE):
    """Return the k chunks most similar to the question, from any index file."""
    idx = json.load(open(indice, encoding="utf-8"))
    q = embed(pregunta)
    ranked = sorted(idx, key=lambda c: coseno(q, c["vector"]), reverse=True)
    return ranked[:k]

if __name__ == "__main__":
    # Quick manual test:  python3 rag.py "why is a candle red"
    import sys
    if not hay_indice():
        print("No index found. Run first: python3 build_index.py"); sys.exit(1)
    pregunta = " ".join(sys.argv[1:]) or "por que una vela es roja?"
    for c in buscar(pregunta):
        print(f"- ({c['modulo']}) {c['texto'][:90]}...")
