# Agentic AI-Based Personal Study Assistant

Starter scaffold — Week 1-2 milestone: document ingestion + vector store, testable via a minimal API.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (not committed) if/when the Tutor or Evaluator agent needs an LLM key:

```
ANTHROPIC_API_KEY=your_key_here
```

> **First run note:** Chroma downloads a small embedding model (`all-MiniLM-L6-v2`, ~80MB) the first time you call `ingest_file`. This needs a normal internet connection — it'll cache locally after that.

## Run the ingestion API

```bash
uvicorn main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for interactive Swagger UI.

### Try it

```bash
# Upload a PDF for a subject
curl -X POST http://127.0.0.1:8000/upload \
  -F "subject=operating-systems" \
  -F "file=@/path/to/your/notes.pdf"

# Query it
curl "http://127.0.0.1:8000/query?subject=operating-systems&question=what+is+a+semaphore"

# List ingested subjects
curl http://127.0.0.1:8000/subjects
```

## Project structure

```
study-assistant/
├── main.py               # FastAPI app: upload / query / subjects endpoints
├── ingestion/
│   ├── loaders.py         # PDF / PPTX / DOCX / TXT text extraction
│   └── pipeline.py        # Chunking + Chroma vector store (per-subject collections)
├── agents/                 # Planner / Tutor / Evaluator agents go here (Week 3-6)
├── data/uploads/            # Uploaded source files land here
├── vectorstore/chroma/       # Persistent Chroma DB (gitignored)
└── db/                      # SQLite DB for study plans & progress (Week 3+)
```

## What's built (Week 1-2)

- [x] Multi-format document loading (PDF, PPTX, DOCX, TXT)
- [x] Chunking (1000 chars, 150 overlap) tuned for lecture-note-style text
- [x] Per-subject Chroma collections so retrieval stays scoped
- [x] Minimal API to upload files and test retrieval before any agent exists

## Next up (Week 3-4)

- [ ] `agents/planner.py` — takes a subject's ingested topics + a deadline, produces a day-wise plan
- [ ] SQLite schema (`db/`) for storing plans, sessions, and quiz scores
- [ ] Decide agent framework: LangGraph vs CrewAI (see project scope doc)

## Notes for the team

- Each teammate can develop against `ingestion/pipeline.py`'s two functions
  (`ingest_file`, `query_subject`) without needing the others' code to exist yet.
- Swap `sentence-transformers`'s default embedding model for a hosted one later
  if local embedding quality/speed becomes a bottleneck — it's isolated in
  `chromadb`'s default embedding function, not hardcoded elsewhere.
