# Intelligent Enterprise Document RAG

An internal document Q&A assistant that lets employees ask natural-language questions about company PDFs — policies, manuals, SOPs, and contracts — and get grounded answers with cited sources, via text or voice.

**Live demo:** https://20-6-74-147.sslip.io

---

## Overview

This is a Retrieval-Augmented Generation (RAG) system built to make internal documentation actually usable. Instead of employees searching through PDFs manually, they can ask questions in plain English (or by voice) and get accurate, source-cited answers grounded strictly in the uploaded documents — with graceful handling of everyday conversational messages ("hi", "how are you", "what can you do") so the assistant feels approachable to non-technical users, not just a bare document-search tool.

### Key features

- **Document-grounded Q&A** — answers are generated only from uploaded PDF content; the assistant explicitly says when something isn't in the documents rather than guessing.
- **Hybrid retrieval** — combines dense vector search (FAISS) with keyword-based BM25 search for more robust matching across both semantic meaning and exact terminology.
- **Conversational memory** — follow-up questions ("what about half-days?") are resolved using recent chat history.
- **Structural query handling** — questions like "summarize this document" or "what's this PDF about" use a different retrieval strategy (HyDE-expanded queries or direct opening-chunk retrieval) tuned for structure rather than fact-lookup.
- **Voice input & output** — ask questions by microphone and hear spoken answers back, powered by Deepgram STT/TTS.
- **Built-in small talk** — greetings, capability questions, and casual chat are recognized and answered instantly without hitting the LLM or retrieval pipeline, so the assistant feels natural for first-time, non-technical users.
- **Multi-document support** — scope questions to a specific uploaded document or search across all of them.
- **Feedback loop** — thumbs up/down on every answer, stored for future review.

---

## Architecture

```
┌─────────────────┐        HTTPS         ┌──────────────────┐
│   Caddy (proxy)  │◄────────────────────┤   Browser / User  │
│  Auto HTTPS via   │                     └──────────────────┘
│  Let's Encrypt    │
└─────────┬────────┘
          │ reverse proxy
          ▼
┌──────────────────┐        HTTP         ┌──────────────────┐
│ Streamlit Frontend│◄───────────────────►│  FastAPI Backend  │
│   (chat UI)        │                    │   (RAG pipeline)   │
└──────────────────┘                     └─────────┬─────────┘
                                                     │
                        ┌────────────────────────────┼────────────────────────────┐
                        ▼                            ▼                            ▼
               ┌─────────────────┐        ┌──────────────────┐        ┌──────────────────┐
               │  FAISS + BM25    │        │  Neon Postgres    │        │  Groq LLM API     │
               │  (local vector   │        │  (users, docs,    │        │  (llama-3.1)      │
               │   index)         │        │   chat history)   │        └──────────────────┘
               └─────────────────┘        └──────────────────┘
                                                     │
                                           ┌──────────────────┐
                                           │  Deepgram API      │
                                           │  (voice STT/TTS)   │
                                           └──────────────────┘
```

**Request flow (`/chat`):**
1. Incoming question is checked against a small-talk pattern matcher — if it's a greeting or casual message, an instant canned reply is returned, skipping retrieval and the LLM entirely.
2. Otherwise, the question is classified as structural (e.g. "summarize this") or standard, and routed to the appropriate retrieval path — either direct document-opening chunks, HyDE-expanded semantic search, or normal hybrid (FAISS + BM25) search.
3. Retrieved chunks are passed to the LLM (Groq, Llama 3.1) with a system prompt that enforces grounding strictly in the retrieved text.
4. The answer, its source chunks, and the conversation turn are saved to Postgres and returned to the frontend.

---

## Tech stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Streamlit | Chat UI, document upload, history, voice recorder |
| Backend | FastAPI + Uvicorn | REST API, RAG orchestration |
| Vector search | FAISS | Dense semantic similarity search over document chunks |
| Keyword search | BM25 (rank_bm25) | Hybrid retrieval alongside FAISS for exact-term matching |
| Embeddings | FastEmbed (`BAAI/bge-small-en-v1.5`) | Local, free embedding generation (no external API cost) |
| LLM | Groq API (`llama-3.1-8b-instant`) | Fast, low-latency answer generation |
| Database | Neon (serverless Postgres) | Users, documents metadata, chat history, feedback |
| Voice | Deepgram (Nova-3 STT, Aura-2 TTS) | Speech-to-text and text-to-speech |
| ORM | SQLAlchemy | Database models and queries |
| Prompt orchestration | LangChain (`langchain_core`) | Prompt templating and LLM invocation |
| Containerization | Docker + Docker Compose | Multi-service orchestration (backend, frontend, proxy) |
| Reverse proxy / TLS | Caddy | Automatic HTTPS certificate management via Let's Encrypt |
| Hosting | Microsoft Azure (VM) | Production deployment |

---

## Deployment

### Infrastructure

- **Host:** Azure Virtual Machine (`Standard_B2ats_v2`, 2 vCPUs, 1 GiB RAM + 2 GiB swap, Ubuntu 24.04 LTS), Azure for Students subscription, Southeast Asia region.
- **Database:** [Neon](https://neon.tech) — serverless Postgres, connected over TLS (`sslmode=require`). Chosen over a self-hosted Postgres container to offload database management and avoid local resource contention on a small VM.
- **Public access:** A free `sslip.io` hostname (`20-6-74-147.sslip.io`) resolves to the VM's public IP without needing a purchased domain, while still allowing Caddy to provision a real, trusted TLS certificate — necessary because browsers only grant microphone access (used for voice input) to secure (HTTPS) origins.
- **Reverse proxy:** [Caddy](https://caddyserver.com) sits in front of the Streamlit frontend, terminating HTTPS and handling automatic certificate renewal via Let's Encrypt. This is the only service exposed on ports 80/443; the backend and frontend containers are otherwise only reachable on the internal Docker network.

### Containers

Three services, orchestrated via `docker-compose.prod.yml`:

| Service | Image | Role |
|---|---|---|
| `caddy` | `caddy:latest` | HTTPS reverse proxy, public entrypoint |
| `backend` | built from `Dockerfile` | FastAPI app, RAG logic, connects to Neon + Groq + Deepgram |
| `frontend` | built from `Dockerfile.streamlit` | Streamlit chat UI, talks to backend over the internal Docker network |

Backend and frontend are on an isolated Docker network and expose no ports directly to the host — Caddy is the sole public-facing service.

### Environment configuration

All secrets and connection details are supplied via a `.env` file (not committed to version control; `.env.example` documents the required variables), covering:
- App metadata (name, environment, log level)
- Neon Postgres connection string and SSL mode
- Groq API key and model selection
- Deepgram API key and STT/TTS model selection
- FAISS index location, chunking parameters, and retrieval top-K

### Operational notes

- **Persistent storage:** uploaded PDFs and the FAISS index are stored on bind-mounted host directories (`./documents`, `./faiss_index`), so they survive container rebuilds and restarts.
- **Schema management:** tables are created automatically via SQLAlchemy's `create_all()` on backend startup — appropriate for this stage of the project; a migration tool (e.g. Alembic) would be the natural next step for handling schema changes without data loss.
- **Resource tuning:** given the VM's limited 1 GiB RAM, a 2 GiB swap file was added to prevent out-of-memory instability during concurrent operations (e.g. simultaneous document ingestion and LLM calls), and Docker's build cache is periodically pruned to manage disk usage from image rebuilds.

---

## Running locally

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd intelligent-enterprise-document-RAG

# 2. Set up environment
cp .env.example .env
# then fill in your own Groq / Deepgram API keys and database credentials

# 3. Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Run the backend
uvicorn app.main:app --reload

# 5. In a separate terminal, run the frontend
streamlit run streamlit.py
```

The backend API docs are available at `http://127.0.0.1:8000/docs` (FastAPI's interactive Swagger UI).

## Running via Docker (production-style)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This brings up all three services (Caddy, backend, frontend) exactly as they run in production, minus the public DNS/TLS step if run without a real reachable IP.

---

## Project structure

```
.
├── app/
│   ├── main.py                  # FastAPI app entrypoint, lifespan, CORS, routers
│   ├── config.py                # Settings loaded from .env
│   ├── database/
│   │   ├── connection.py        # SQLAlchemy engine/session setup
│   │   └── crud.py              # Database access functions
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models
│   ├── routers/
│   │   ├── chat.py              # /chat endpoint
│   │   ├── upload.py            # /upload endpoint
│   │   ├── documents.py         # /documents, /document/{id}
│   │   ├── history.py           # /history
│   │   ├── users.py             # /users
│   │   └── voice.py             # /voice/transcribe, /voice/speak
│   └── services/
│       ├── rag_service.py       # Core RAG logic, small-talk detection, prompt orchestration
│       ├── vector_store_service.py  # FAISS + BM25 hybrid search
│       ├── document_service.py  # PDF chunking + ingestion
│       └── llm_service.py       # Groq LLM client
├── streamlit.py                 # Frontend chat UI
├── docker-compose.prod.yml      # Production container orchestration
├── Dockerfile                   # Backend image
├── Dockerfile.streamlit         # Frontend image
├── Caddyfile                    # Reverse proxy / HTTPS config
└── .env.example                 # Documented environment variable template
```

---

## Notes on design decisions

- **FastEmbed over a paid embedding API** — runs locally at no per-request cost, appropriate for a small-scale internal tool without high-volume embedding needs.
- **Groq over other LLM providers** — chosen for very low inference latency, keeping the chat experience responsive.
- **Neon over self-hosted Postgres** — removes database operations (backups, patching, SSL setup) from the deployment surface, which matters more on a resource-constrained single VM than the marginal cost of a managed service.
<<<<<<< HEAD
- **Small-talk pattern matching over LLM-based routing** — greetings and capability questions are matched via regex and answered instantly, avoiding unnecessary LLM calls and making the assistant's behavior for these cases fully predictable and free.
=======
- **Small-talk pattern matching over LLM-based routing** — greetings and capability questions are matched via regex and answered instantly, avoiding unnecessary LLM calls and making the assistant's behavior for these cases fully predictable and free.
>>>>>>> d3c6960 (Add project README)
