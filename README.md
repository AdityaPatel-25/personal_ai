# AlgoCoach AI

> An intelligent, context-grounded AI coach for Competitive Programming and Data Structures & Algorithms, powered by Groq Llama-3.3-70B, ChromaDB RAG, and persistent SQLite memory.

[![CI](https://github.com/AdityaPatel-25/Personal_AI/actions/workflows/ci.yml/badge.svg)](https://github.com/AdityaPatel-25/Personal_AI/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/Demo-personallai.vercel.app-blue)](https://personallai.vercel.app)
[![Backend API](https://img.shields.io/badge/API-Render-green)](https://personal-ai-p018.onrender.com)

- **Live Frontend**: [https://personallai.vercel.app](https://personallai.vercel.app)
- **Backend API**: [https://personal-ai-p018.onrender.com](https://personal-ai-p018.onrender.com)

![AlgoCoach AI Interface](docs/screenshot.png)

---

## 🚀 Features

- **Streaming Chat**: Real-time token-by-token streaming using Server-Sent Events (SSE) and chunked HTTP transfer encoding (`POST /chat`), powered by Groq's high-throughput `llama-3.3-70b-versatile` (with automatic fallback to `openai/gpt-oss-120b`).
- **Persistent Memory (SQLite)**: Automatically tracks conversations and message histories (`conversations` and `messages` tables). Injects the last 14 messages (`CONTEXT_MESSAGE_LIMIT = 14`) into LLM prompt turns for conversational coherence across sessions.
- **RAG over DSA Notes (ChromaDB)**: Curated algorithmic notes covering Binary Search, Dynamic Programming, Graphs, and Trees & Heaps in `data/`. Vector search grounds responses with relevant patterns, invariants, and templates before answering.
- **Action Tool Calling**:
  - `suggest_problem`: Curated catalog lookup across LeetCode/Codeforces patterns (e.g., 0/1 Knapsack, Course Schedule, Koko Eating Bananas, LCA) with informal topic alias normalization.
  - `get_weak_topics`: Scans chat history for struggle indicators (`confused`, `stuck`, `hard`, `wa`, `tle`) and past verdicts to calculate algorithmic weakness scores and recommend targeted practice.
  - `log_submission`: Records problem-solving verdicts (`Accepted`, `Wrong Answer`, `Time Limit Exceeded`, `Runtime Error`) directly into SQLite.
- **Per-IP Rate Limiting**: Built with `slowapi`, protecting `POST /chat` with a default quota of 10 requests per minute and 100 requests per day per IP address (configurable via `CHAT_RATE_LIMIT`). Unaffected health endpoints (`GET /rag/status`) allow uninterrupted keep-alive pinging.
- **Voice Input**: Integrated browser recording via `MediaRecorder` API and backend speech-to-text transcription (`POST /transcribe`) powered by Groq's `whisper-large-v3-turbo` model for hands-free problem discussions.

---

## 🛠️ Tech Stack

| Component | Technology | Details |
|---|---|---|
| **Frontend** | React 18, Vite | Single-page application with streaming response decoding via `ReadableStream` |
| **Styling & UI** | Tailwind CSS, Lucide React | Dark aesthetic, responsive drawer, modal dialogs, and code highlighting |
| **Backend** | FastAPI, Uvicorn | Asynchronous Python REST API with SSE, CORS middleware, and custom exception handling |
| **LLM Engine** | Groq API (`llama-3.3-70b-versatile`) | High-speed cloud LLM inference with fallback to `openai/gpt-oss-120b` |
| **Speech-to-Text** | Groq Whisper (`whisper-large-v3-turbo`) | High-speed audio transcription for voice inputs (`POST /transcribe`) |
| **Vector Store** | ChromaDB (`chromadb>=1.5.0`) | Local persistent vector storage with cosine distance metric (`hnsw:space: cosine`) |
| **Embedding Model** | ONNX `all-MiniLM-L6-v2` (384 dims) | ChromaDB `DefaultEmbeddingFunction` executing 100% locally on CPU (<50MB RAM) |
| **Database** | SQLite 3 (`sqlite3`) | Local transactional persistence for conversations, messages, and submissions |
| **Rate Limiter** | SlowAPI | Token bucket / sliding window per-IP rate limiting |
| **Frontend Hosting**| Vercel | Global edge CDN deployment ([personallai.vercel.app](https://personallai.vercel.app)) |
| **Backend Hosting** | Render | Cloud container deployment ([personal-ai-p018.onrender.com](https://personal-ai-p018.onrender.com)) |
| **CI / Automation** | GitHub Actions | Automated test runner on Python 3.12 (`.github/workflows/ci.yml`) |

---

## 🧠 How It Works

### 1. Chat Flow
1. **User Request**: The student enters a prompt or records an audio query (transcribed into text via Groq Whisper).
2. **Rate Limit Inspection**: `slowapi` checks the client IP against configured window limits (10/min, 100/day). If exceeded, a clean HTTP 429 JSON response is returned immediately.
3. **Database Logging**: The incoming user prompt is saved to SQLite, and conversation titles are automatically generated or resolved.
4. **RAG Semantic Retrieval**: The prompt is embedded and queried against the local ChromaDB vector store to retrieve the top 4 relevant note snippets (`top_k = 4`).
5. **Prompt Augmentation**: Recent chat turns (up to 14 messages) are assembled with system instructions and the retrieved DSA notes injected directly into the active prompt turn.
6. **Streaming Generation**: The request streams from Groq (`stream=True`) and emits SSE/chunked bytes to the frontend. Custom HTTP headers (`X-Conversation-Id`, `X-Rag-Chunks`, `X-Rag-Sources`) pass retrieval provenance metadata.
7. **Client Rendering**: React decodes incoming bytes incrementally with `TextDecoder` and `ReadableStreamDefaultReader`, displaying the response token-by-token. The complete assistant response is committed to SQLite on finish.

### 2. RAG Pipeline
- **Chunking Strategy**: Paragraph-aware recursive chunking (`chunk_text` in `backend/rag.py`). Documents are split on double newlines (`\n\s*\n`). If any paragraph exceeds `chunk_size`, it is split by lines while keeping multi-line code blocks intact without mid-line truncation. Overlapping sliding windows are then assembled.
- **Default Chunking Parameters**:
  - `chunk_size = 600` characters (`DEFAULT_CHUNK_SIZE`)
  - `chunk_overlap = 120` characters (`DEFAULT_CHUNK_OVERLAP`, ~20% overlap)
- **Embedding Model**: ChromaDB's built-in `DefaultEmbeddingFunction` using ONNX runtime and `all-MiniLM-L6-v2` (384 dimensions). Executes purely on local CPU with low memory overhead, avoiding PyTorch or sentence-transformers dependencies.
- **Retrieval Metric & Top-K**: Chunks are retrieved with cosine distance, mapped to similarity scores (`similarity = 1.0 - distance`). Defaults to `top_k = 4` in chat generation and `top_k = 3` in evaluation scripts.

### 3. Tool-Calling Loop
- **Endpoints**: Tools are exposed via REST endpoints `GET /tools` and `POST /tools/execute`.
- **UI Integration**: Frontend modals allow interactive execution of coaching tools:
  - `suggest_problem`: Resolves topic aliases (e.g., `dp`, `bfs`, `tree`) against `TOPIC_ALIASES` and returns curated problem templates, patterns, and difficulty levels from `CURATED_PROBLEMS`.
  - `get_weak_topics`: Scans chat history for struggle phrases and aggregates submission outcomes into a weighted weakness score (`(struggles * 3.0) + (failed * 4.0) - (accepted * 2.0)`).
  - `log_submission`: Standardizes verdicts (`Accepted`, `Wrong Answer`, `Time Limit Exceeded`) and records entries in the SQLite `submissions` table.

---

## 📊 Retrieval Evaluation

Evaluation benchmarks are measured locally against 24 hand-crafted questions across all 4 topic note files using [scripts/eval_retrieval.py](scripts/eval_retrieval.py) (stored in [eval/results.json](eval/results.json)):

| Configuration (Chunk Size / Overlap) | Benchmark Questions | Top-1 Accuracy | Top-3 Accuracy | Average Similarity |
|---|---|---|---|---|
| `chunk_size=600`, `chunk_overlap=120` | 24 questions across 4 note files | **95.8%** (23 / 24) | **100.0%** (24 / 24) | `0.5859` |

Run the evaluation harness:
```bash
# Evaluate retrieval accuracy and save results to eval/results.json:
python scripts/eval_retrieval.py --top-k 3 --json-out eval/results.json
```

---

## 🧪 Testing and CI

### Running Tests Locally
Automated unit and integration tests use `pytest`:

```bash
# Run the test suite:
pytest -v
```

### What's Covered
- **[tests/test_chunking.py](tests/test_chunking.py)**:
  - `chunk_text` respects `chunk_size` character limits.
  - Overlap carries over between consecutive chunks.
  - Empty, whitespace, and newline inputs return empty lists.
  - Multi-line code blocks are preserved line-by-line without mid-line splitting.
- **[tests/test_api.py](tests/test_api.py)**:
  - `POST /chat` rejects empty/whitespace messages with a 4xx error (422).
  - `GET /conversations` returns a list and persists newly created threads.
  - `GET /rag/status` returns expected diagnostic keys (`status`, `collection_name`, `total_chunks`, `chroma_db_path`, `embedding_model`).
  - Per-IP rate limiting on `POST /chat` triggers an HTTP 429 JSON response when limits are exceeded.
  - `GET /rag/status` is not rate-limited, allowing keep-alive pings.
- **[tests/test_tools.py](tests/test_tools.py)**:
  - `suggest_problem` returns valid problems for all supported topics and aliases.
  - `suggest_problem` handles unknown topics cleanly without unhandled exceptions.
  - `log_submission` inserts rows into the temporary SQLite submissions database.
- **Test Isolation**: [tests/conftest.py](tests/conftest.py) supplies isolated test fixtures:
  - `temp_db`: Dedicated temporary SQLite database per test.
  - `temp_chroma`: Dedicated temporary ChromaDB directory per test.
  - `mock_groq`: Mocks `AsyncGroq` chat completion streams and Whisper transcriptions (no network calls or real API keys needed).

### Continuous Integration (CI)
A GitHub Actions workflow ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every push and pull request to `main`:
- Sets up Python 3.12.
- Installs `backend/requirements.txt`, `pytest`, and `httpx`.
- Executes `pytest -v` (pure testing without calling external LLM APIs).

---

## 💻 Running Locally

### 1. Prerequisites
- **Python 3.10+** (tested on 3.10, 3.12, 3.14)
- **Node.js 18+** & **npm**
- A Groq API key from [Groq Console](https://console.groq.com/keys)

### 2. Environment Configuration
Copy `.env.example` to `.env` in the repository root:

```bash
cp .env.example .env
```

Configure your environment variables in `.env`:
```env
# Required: Groq API Key
GROQ_API_KEY=gsk_your_actual_key_here

# Optional: Groq model identifier (defaults to llama-3.3-70b-versatile)
GROQ_MODEL=llama-3.3-70b-versatile

# Frontend API URL (points to local FastAPI backend)
VITE_API_URL=http://localhost:8000

# Optional: Chat endpoint per-IP rate limits (default: 10/minute,100/day)
CHAT_RATE_LIMIT=10/minute,100/day
```

### 3. Backend Setup
Create and activate a virtual environment, then install dependencies:

```bash
# Windows:
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

# Install requirements:
pip install -r backend/requirements.txt
```

### 4. Index Knowledge Base Notes
Build the local ChromaDB vector database from markdown notes in `data/`:

```bash
python scripts/index_data.py
```

### 5. Start Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```
Backend API and interactive documentation are available at `http://localhost:8000/docs`.

### 6. Frontend Setup
In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🌐 Deployment Notes

- **Backend**: Hosted on **Render** at [https://personal-ai-p018.onrender.com](https://personal-ai-p018.onrender.com).
- **Frontend**: Hosted on **Vercel** at [https://personallai.vercel.app](https://personallai.vercel.app).
- **Free-Tier Cold Starts**: Render free-tier web services spin down automatically after 15 minutes of inactivity. When a request arrives after inactivity, the instance requires approximately **~50 seconds** to spin up and load the ChromaDB vector database. The frontend handles this with an initial loading indicator, a 30-second timeout warning, and a Retry button.

---

## 📁 Project Structure

```text
Personal_AI/
├── .env.example              # Template environment variables
├── README.md                 # Project architecture, setup & evaluation guide
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI workflow (Python 3.12 + pytest)
├── data/                     # DSA topic notes for RAG indexing
│   ├── binary_search.md
│   ├── dynamic_programming.md
│   ├── graph_algorithms.md
│   └── trees_and_heaps.md
├── eval/                     # Retrieval evaluation benchmark suite
│   ├── questions.json        # 24 benchmark questions across all notes
│   └── results.json          # Benchmark accuracy report (Top-1, Top-3, similarity)
├── scripts/
│   ├── index_data.py         # CLI tool to (re)index notes into ChromaDB
│   └── eval_retrieval.py     # Retrieval accuracy evaluation harness
├── tests/                    # Automated pytest test suite
│   ├── conftest.py           # Pytest fixtures (temporary DB, Chroma, Groq mock)
│   ├── test_chunking.py      # Chunk size, overlap, empty input & code block tests
│   ├── test_api.py           # FastAPI endpoints, validation, and rate limiting tests
│   └── test_tools.py         # Problem suggestion and submission logging tests
├── backend/
│   ├── main.py               # FastAPI application entrypoint & CORS middleware
│   ├── chat.py               # Groq streaming, Whisper audio transcription, RAG injection
│   ├── db.py                 # SQLite database persistence (conversations, messages, submissions)
│   ├── rag.py                # ChromaDB vector store & ONNX embedding pipeline
│   ├── tools.py              # Action tools (suggest_problem, get_weak_topics, log_submission)
│   ├── requirements.txt      # Python dependencies
│   └── chroma_db/            # Local persistent ChromaDB files
└── frontend/
    ├── index.html            # HTML entrypoint
    ├── vite.config.js        # Vite configuration
    ├── package.json          # Node dependencies
    └── src/
        ├── App.jsx           # Root layout component
        └── components/
            ├── ChatWindow.jsx   # Streaming state orchestration & error handling
            ├── MessageList.jsx  # Markdown messages, code blocks & diagnostic cards
            ├── MessageInput.jsx # Input textarea, keybindings & audio recorder
            └── Sidebar.jsx      # Conversation thread drawer & history management
```

---

## ⚠️ Limitations and Future Work

- **Curated Note Corpus**: The RAG knowledge base currently indexes 4 core DSA topics (`binary_search.md`, `dynamic_programming.md`, `graph_algorithms.md`, `trees_and_heaps.md`). Expanding to Bit Manipulation, Trie, Backtracking, and Segment Trees is planned.
- **Ephemeral Storage on Free Tier**: On free-tier cloud hosting (Render), disk storage is ephemeral; local SQLite and ChromaDB data reset if the container is redeployed. Transitioning to managed PostgreSQL (e.g., Supabase / Neon) and managed cloud vector search (e.g., Qdrant Cloud / Pinecone) will provide durable multi-region persistence.
- **Single-User Architecture**: Conversations are stored locally without user authentication or multi-tenant isolation.
- **Future Roadmap**:
  - [ ] User authentication (OAuth / JWT via Supabase or Clerk).
  - [ ] Multi-tenant isolation for conversations and submissions.
  - [ ] Direct LeetCode API / Codeforces profile synchronization.
  - [ ] Hybrid sparse/dense retrieval (BM25 + vector search reranking).
