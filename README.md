# TUTOR_2_LEARN_LOCALLY

A **100% local, offline AI tutor** built on **Ollama**. It teaches any subject
one concept at a time, challenges you with **live-generated exercises**, grades
your math **deterministically**, and answers free questions with **RAG** — all
on your own machine, with no cloud and no API keys.

Feed it **any PDF (or .txt / .md)** and it auto-builds a full course (lessons +
quizzes). A Spanish example course ships in `curso/` (*Economics 101 + basic
math*, bilingual ES/EN).

> Note on language: this tool is a **bilingual (ES/EN) tutor** aimed at a Spanish
> speaker, so the shipped example course and the tutor's spoken output are in
> **Spanish by design**. The code, comments and this documentation are in
> **English**. To teach another subject or language, replace `curso/curso.json`
> (or ingest your own PDF).

---

## Features

- **Two study modes:** **A — Guided** (lessons module by module) and **B — Ask
  anything** (vector RAG over the course).
- **Live challenge engine:** fresh exercises every time, escalating difficulty,
  streaks, and an adjustable intensity (easy / normal / intense).
- **Deterministic math grading:** the script checks arithmetic (not the model),
  so grading is reliable even with small local models; answers are hidden from
  the learner.
- **Two selectable memories for mode B:** a **vector index** or an **LLM-wiki**
  (linked Markdown pages).
- **PDF ingestion:** turn any document into course modules + quizzes.
- **Online fallback:** if an answer isn't in the course, mode B announces it,
  searches DuckDuckGo, and cites the source links.
- **Progress & personalization:** scores, a live HTML report, and a student
  profile that targets your weak spots.
- **Persistent config** (`config.json`) with an in-app Maintenance menu.
- All generators **resume** and support **`--restart`**, saving incrementally.

---

## Quick start

Requirements: [Ollama](https://ollama.com) and Python 3.10+.

```bash
# Chat model (any works with code grading; Western options: phi4, llama3.1, gemma2)
ollama pull phi4
# Embedding model (for mode B / wiki)
ollama pull nomic-embed-text
# For PDF ingestion
pip3 install pypdf

git clone https://github.com/<YOUR_USER>/TUTOR_2_LEARN_LOCALLY.git
cd TUTOR_2_LEARN_LOCALLY
cp config.example.json config.json     # optional; else sensible defaults are used
python3 build_index.py                  # build the vector memory (mode B)
python3 tutor.py                        # start
```

---

## Use your own document

```bash
python3 ingest_document.py my_file.pdf      # build a course from the PDF
python3 tutor.py
```
Flags: `--append`, `--restart`, `--no-examen`, `--no-rebuild`.

---

## Scripts & flags

Every generator **resumes by default** and takes **`--restart`** to rebuild from
scratch; all save incrementally (crash-safe).

```
python3 ingest_document.py doc.pdf   # PDF/TXT/MD -> course (+ quizzes)
python3 build_index.py               # vector DB for mode B
python3 generate_wiki.py             # LLM-wiki memory (+ its index)
python3 generate_quizzes.py          # (re)build quizzes from the course
python3 tutor.py                      # study (modes A/B, report, profile)
```

---

## How the RAG works

A computer doesn't understand "text", but it understands **numbers**. An
*embedding* turns a chunk of text into a **vector** that captures its meaning;
similar texts get similar vectors. `build_index.py` chunks `curso.json`, asks
Ollama (`nomic-embed-text`) for each chunk's vector, and stores
`[{module, text, vector}]` in `indice_vectorial.json` — that file **is** the
vector database (no server). `rag.py` embeds your question and finds the closest
chunks by **cosine similarity**, feeding them to the model as grounded context.

---

## LLM-wiki (second memory type)

`generate_wiki.py` has the model expand `curso.json` into one linked Markdown
page per module (`wiki/<key>.md`, with `[[key]]` cross-links), then embeds those
pages into `indice_wiki.json`. In mode B you can switch memory between
**vectorial** and **wiki** from the Maintenance menu.

---

## Configuration (`config.json`)

Loaded on startup, saved on exit or from the **Maintenance** menu. Copy the
template to begin: `cp config.example.json config.json` (it is gitignored —
personal). Fields:

- **modelo** — Ollama chat model (`phi4`, `llama3.1:8b`, `gemma2:9b`, `qwen3:14b`…).
- **modo** — `"A"` (guided) or `"B"` (ask anything / RAG).
- **memoria** — `"vectorial"` or `"wiki"` (mode B only).
- **calculo** — `"codigo"` (script grades arithmetic — reliable) or `"modelo"`
  (model reasons; enables `think:true`, best with a reasoning model).
- **umbral** — 0–1; minimum similarity to answer from the course in mode B
  (lower = search online less).
- **reto** — challenge intensity: `"suave"` / `"normal"` / `"intenso"`.
- **host** — Ollama URL.

### Choosing a model
With `calculo: "codigo"` the script does the arithmetic, so **any model works**
for teaching. Western (non-Chinese) options: **phi4** (Microsoft, strong math),
**llama3.1:8b** (Meta), **gemma2:9b / 27b** (Google), **mistral-small** (EU).
`calculo: "modelo"` benefits from a reasoning model; today the `<think>` models
on Ollama are mostly qwen3 / deepseek-r1 — thanks to code grading you don't need
them.

---

## File layout

```
tutor.py              Main app: menu, lessons, challenge engine, exams, report
curso/curso.json      Course content = single source of truth (editable)
banco.json            Multiple-choice quiz bank
ingest_document.py    PDF/TXT/MD -> course modules + quizzes
build_index.py        Builds the vector DB from curso.json
rag.py                Vector search (embed -> cosine similarity -> top chunks)
generate_wiki.py      curso.json -> wiki/*.md + indice_wiki.json
generate_quizzes.py   (Re)builds the quiz bank
student_profile.py    puntajes.csv -> progreso/perfil_alumno.md
tutor_prompt.md       Tutor pedagogy/system prompt (Spanish teaching content)
config.example.json   Config template
progreso/             Per-user progress (gitignored)
```

---

## Publishing

```bash
./push_to_github.sh                 # create the repo and push (public; add --private)
```
Generated files and personal progress are gitignored.

---

## Docs
- **[AGENTS.md](AGENTS.md)** — architecture, conventions, and an open invitation
  for AI agents to explore and branch.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how to contribute.

## License
MIT — see [LICENSE](LICENSE).
