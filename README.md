# TUTOR_2_LEARN_LOCALLY

Un **tutor de IA 100% local y offline** que te enseña cualquier tema paso a paso,
con exámenes, puntajes y reporte de avance — usando **Ollama** en tu propia
máquina, sin API keys ni nube.

Dale un **PDF (o .txt / .md) de cualquier tema** y el tutor **genera el módulo de
enseñanza** automáticamente. Incluye un curso de ejemplo ya cargado:
*Economía con matemáticas desde cero* (19 módulos, bilingüe español/inglés).

> A fully local, offline AI tutor built on Ollama. Feed it any PDF and it builds
> the lessons, quizzes and progress tracking for you. No cloud, no API keys.

---

## ✨ Qué hace

- **Enseña un concepto a la vez**, paciente, en español con términos en inglés al lado.
- **Dos modos de estudio:**
  - **A — Guiado por módulo:** lecciones en orden, desde el contenido del curso.
  - **B — Pregúntale lo que sea (RAG):** búsqueda vectorial sobre todo el curso.
- **Exámenes de opción múltiple** que se autocalifican (funcionan sin modelo).
- **Puntajes y avance** guardados en tu disco; **reporte HTML** de alto contraste
  que se actualiza en vivo.
- **Ingesta de documentos:** convierte un PDF en módulos de curso + exámenes.
- **Búsqueda web opcional** (DuckDuckGo) desde el menú.

---

## 🚀 Instalación rápida

**Requisitos:** [Ollama](https://ollama.com) y Python 3.10+.

```bash
# 1) Modelo de chat (bueno en mates y español; ~24 GB RAM)
ollama pull qwen3:14b
# 2) (para el modo B) modelo de embeddings
ollama pull nomic-embed-text
# 3) (para ingerir PDFs)
pip3 install pypdf

git clone https://github.com/<TU_USUARIO>/TUTOR_2_LEARN_LOCALLY.git
cd TUTOR_2_LEARN_LOCALLY
python3 tutor.py
```

Al iniciar eliges **modo A o B**. El avance se guarda solo en `progreso/`.

---

## 📚 Usar tu propio documento (PDF de cualquier tema)

```bash
python3 ingest_document.py mi_documento.pdf      # genera el curso desde el PDF
python3 tutor.py                                    # estúdialo
```

Opciones: `--append` (agrega al curso actual), `--no-examen`, `--no-rebuild`.
Cada ingesta respalda tu curso anterior con sufijo `.bak-<fecha>`.

---

## 🧠 Cómo funciona el RAG (base vectorial)

La computadora no entiende "texto", pero sí **números**. Un *embedding* convierte
un pedazo de texto en un **vector** que captura su significado; textos parecidos
tienen vectores parecidos.

1. **`build_index.py`** trocea `curso/curso.json`, pide el vector de cada
   pedazo a Ollama (`nomic-embed-text`) y guarda `[{modulo, texto, vector}]` en
   `indice_vectorial.json`. **Ese archivo es la base vectorial** (sin servidor).
2. **`rag.py`** convierte tu pregunta en vector y busca los pedazos más parecidos
   por **similitud coseno** → se los pasa al modelo como contexto → responde solo
   con eso (por eso no inventa).

```bash
python3 build_index.py              # construir la base
python3 rag.py "por que una vela es roja"  # probar el buscador
```

---

## 🗂️ Estructura

```
tutor.py              El tutor (menú de inicio A/B, exámenes, reporte)
curso/curso.json      Contenido del curso (fuente única, editable)
banco.json            Exámenes de opción múltiple
ingest_document.py  PDF/TXT/MD  ->  módulos de curso + exámenes
build_index.py   Construye la base vectorial
rag.py                Buscador vectorial (similitud coseno)
tutor_prompt.md       Instrucciones pedagógicas del tutor
progreso/             Tu avance (se crea solo; NO se sube a GitHub)
```

---

## ⚙️ Configuración

Variables de entorno opcionales:

```bash
OLLAMA_MODEL=qwen3:30b-a3b python3 tutor.py   # otro modelo de chat
OLLAMA_EMBED=nomic-embed-text                 # modelo de embeddings
OLLAMA_HOST=http://localhost:11434            # host de Ollama
```

---

## 📝 Licencia

MIT — ver [LICENSE](LICENSE).

## 🧩 LLM-Wiki (segundo tipo de memoria)

Ademas del RAG vectorial sobre `curso.json`, puedes generar una **wiki**: una
pagina markdown por modulo, con enlaces `[[...]]` entre temas, escrita por el
modelo a partir del curso. Sirve como memoria mas rica y navegable.

```bash
python3 generate_wiki.py        # crea wiki/*.md + indice_wiki.json
python3 tutor.py               # menu opcion 8 -> elige memoria "wiki"
```

En el **modo B** puedes cambiar el **tipo de memoria** (menu, opcion 8):
- **vectorial** — pedazos de `curso.json` (rapida, literal).
- **wiki** — paginas enlazadas (respuestas con mas contexto).

Si editas el curso, regenera la wiki para refrescarla.

## Scripts & flags (v1.2)
Every generator **resumes by default** and takes **`--restart`** to rebuild from scratch; all save incrementally (crash-safe).

```
python3 ingest_document.py doc.pdf      # PDF/TXT/MD -> course (+ exams); resume / --restart / --append
python3 build_index.py                  # build the vector DB; resume / --restart
python3 generate_wiki.py                # build the LLM-wiki (+ its index); resume / --restart / --no-index
python3 generate_quizzes.py             # (re)build exams from the course; resume / --restart
python3 tutor.py                        # study (modes A/B, memory selector, report, profile)
```

## Mode B online fallback
When a question isn't covered by the course (vector similarity below a threshold),
Mode B announces it, searches DuckDuckGo, answers from the web, and lists the
**source links** as references — clearly labeled as web (not course) content.
Tune the threshold: `RAG_MIN_SCORE=0.55 python3 tutor.py` (lower = search less).

## Publishing / updating on GitHub
```
./push_to_github.sh                 # creates the repo and pushes (public; add --private)
```
Requires `gh auth login` once. Generated files and personal progress are gitignored.

## For AI agents / contributors
See [AGENTS.md](AGENTS.md) — architecture, conventions, and an open invitation to explore and branch.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Configuración (config.json)
El tutor carga `config.json` al iniciar y lo guarda al salir (opción 8) o desde
Mantenimiento (opción 7). Para empezar, copia la plantilla:
```bash
cp config.example.json config.json
```
`config.json` es personal y está en `.gitignore` (no se sube). Campos:
- **modelo**: modelo de Ollama para el chat (ej. `phi4`, `llama3.1:8b`, `gemma2:9b`, `qwen3:14b`).
- **modo**: `"A"` (guiado, módulo por módulo) o `"B"` (pregúntale lo que sea / RAG).
- **memoria**: `"vectorial"` o `"wiki"` (solo aplica en modo B).
- **calculo**: `"codigo"` (el script califica la aritmética — determinista y confiable)
  o `"modelo"` (el modelo razona la aritmética; enciende `think:true`, conviene un modelo de razonamiento).
- **umbral**: 0–1. Similitud mínima para responder desde el curso en modo B; más bajo = busca menos en línea.
- **host**: URL de Ollama (por defecto `http://localhost:11434`).

### Elegir modelo
- Con **`calculo: "codigo"`** el script hace las cuentas, así que **cualquier modelo sirve** para enseñar.
  Opciones occidentales (no chinas): **phi4** (Microsoft, fuerte en matemáticas), **llama3.1:8b** (Meta),
  **gemma2:9b / 27b** (Google), **mistral-small** (Mistral, UE).
- **`calculo: "modelo"`** saca más provecho de un modelo de razonamiento; hoy los modelos con
  pensamiento `<think>` en Ollama son mayormente qwen3 / deepseek-r1. Gracias al modo "codigo" **no los necesitas**.
