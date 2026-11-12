# AGENTS.md — A guide for AI agents exploring this repo

Welcome, agent. This project is **TUTOR_2_LEARN_LOCALLY**: a 100% local,
offline AI tutor built on Ollama. You are encouraged to **explore the code
freely, experiment, and open branches** with improvements. This file is your
map and your rules of the road.

## What this project is
A terminal tutor that teaches any subject one concept at a time. It can
**ingest any PDF/TXT/MD** and auto-generate a course (modules + quizzes), then
teach it in two modes: **A — guided** (module by module) and **B — ask
anything** (vector RAG, with an optional LLM-wiki memory and a web-search
fallback). Everything runs against a local Ollama model — no cloud, no keys.

Start with `README.md` for the user-facing overview; this file is the
contributor/agent view.

## Architecture & data flow
```
ingest_document.py  (PDF/TXT/MD) ──► curso/curso.json  ──► build_index.py ──► indice_vectorial.json
                                   └► banco.json (quizzes)                     (mode B "vectorial" memory)
                                   └► progreso/ (fresh)
generate_wiki.py    curso.json ──► wiki/*.md (+ [[links]]) ──► indice_wiki.json   (mode B "wiki" memory)
generate_quizzes.py curso.json ──► banco.json                                    (regenerate exams only)
student_profile.py  progreso/puntajes.csv ──► progreso/perfil_alumno.md          (personalizes mode A)
tutor.py            reads curso.json + indices + profile ──► lessons, exams, HTML report
rag.py              embed(question) → cosine similarity → top-k chunks (any index)
```
`curso/curso.json` is the **single source of truth** for content. Every other
artifact is derived from it and is regenerable.

## Conventions you MUST keep
1. **Code & comments in English; all user-facing printed strings in Spanish.**
   The learner reads Spanish; the repo is English-readable. Do not translate
   `print()` output.
2. **Resume + `--restart` on every generator.** `ingest_document.py`,
   `build_index.py`, `generate_wiki.py`, `generate_quizzes.py` all resume by
   default and rebuild fully with `--restart`. Preserve this contract in any
   change; add it to any new generator.
3. **Incremental, crash-safe saves.** Write progress to disk after each item,
   never only at the end.
4. **Dependency-light.** Standard library + Ollama HTTP only. The sole external
   dependency is `pypdf` (PDF ingestion). Do not add heavy deps (no LangChain,
   no vector-DB servers) unless you make them optional.
5. **Local model robustness.** Weak models misbehave: send `"think": false`,
   strip `<think>...</think>`, use `"format":"json"` for JSON tasks, accept
   both a bare JSON list and an object-wrapped list, and normalize every
   generated module (see `normalizar_modulo`). Never assume perfect output.
6. **Never commit generated or personal data.** `progreso/`, `indice_*.json`,
   `wiki/`, `reporte.html`, `*.bak-*`, `.ingest_state.json` are gitignored.

## Good areas to explore (open a branch for any of these)
- **Streaming** model output in `tutor.py` so replies appear token-by-token.
- **Better chunking** in `ingest_document.py` (semantic/heading-aware instead of
  fixed word counts) to produce cleaner modules.
- **Incremental embeddings resume** keyed by a content hash rather than exact
  text match.
- **Spaced-repetition** review mode driven by `progreso/puntajes.csv`.
- **A small web UI** (single static HTML) over the same JSON, keeping the CLI.
- **Multi-language** courses (generalize the Spanish-UI assumption behind a
  locale setting, without breaking the default).
- **Evaluation**: a script that scores quiz quality / wiki faithfulness against
  `curso.json`.

## How to work (branch etiquette)
```bash
git checkout -b feature/<short-name>
# ... make a focused change ...
python3 -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('*.py')]"  # syntax check
git add -p && git commit -m "<what and why>"
git push -u origin feature/<short-name>   # then open a PR
```
- Keep each branch focused on one idea.
- Explain the *why* in the PR, and how you tested it (ideally against a tiny
  sample doc in `ejemplos/`).
- Don't break the resume/restart contract or the English-code/Spanish-UI rule.
- If you add a generator or a flag, document it in `README.md` and bump
  `VERSION`.

## Safe sandbox
`ejemplos/` holds a tiny sample document for end-to-end testing without a large
PDF. Prefer testing there. The tutor and all generators are safe to run
repeatedly — they back up and resume.

Explore boldly. Leave the code clearer than you found it.
