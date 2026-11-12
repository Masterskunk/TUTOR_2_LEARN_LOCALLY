# Contributing

Thanks for your interest in **TUTOR_2_LEARN_LOCALLY**! Contributions — bug
fixes, new features, docs, more sample courses — are welcome.

## Setup
1. Install [Ollama](https://ollama.com) and Python 3.10+.
2. Pull the models:
   ```bash
   ollama pull qwen3:14b          # chat model (math + Spanish)
   ollama pull nomic-embed-text   # embeddings (mode B / wiki)
   pip3 install pypdf             # only needed for PDF ingestion
   ```
3. Run it: `python3 tutor.py` (an example economics course ships in `curso/`).

## Project layout
`curso/curso.json` is the single source of truth; everything else is derived
from it. See **[AGENTS.md](AGENTS.md)** for the full architecture, data flow,
and the design conventions this project relies on. Read it before a non-trivial
change.

## Conventions (short version)
- **Code and comments in English; user-facing printed text in Spanish** (that's
  what the learner reads — don't translate `print()` output).
- Every generator **resumes by default** and supports **`--restart`**; all save
  incrementally. Keep that contract.
- **Dependency-light**: standard library + Ollama HTTP, plus `pypdf` for PDFs.
  Avoid heavy dependencies unless they're optional.
- **Never commit generated or personal data** — `progreso/`, `indice_*.json`,
  `wiki/`, `reporte.html`, `*.bak-*` and `.ingest_state.json` are gitignored.

## Workflow
```bash
git checkout -b feature/<short-name>
# make a focused change
python3 -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('*.py')]"  # syntax check
git commit -m "<what and why>"
git push -u origin feature/<short-name>   # open a Pull Request
```
- Keep each PR focused on one thing.
- Describe **what** changed, **why**, and **how you tested it** (prefer the tiny
  doc in `ejemplos/` for end-to-end tests).
- If you add a script or a flag, update `README.md` and bump `VERSION`.

## Reporting issues
Open a GitHub issue with: what you expected, what happened, the command you ran,
your OS, and your Ollama model. For generation problems, include the console
output — the generators print per-item progress.

## License
By contributing you agree your work is licensed under the project's
[MIT License](LICENSE).
