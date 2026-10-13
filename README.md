# Personal AI — Competitive Programming & DSA Coach

> **Milestone:** Chat & generation powered by Groq (`llama-3.3-70b-versatile`), RAG knowledge base pipeline using ChromaDB (persistent vector store) powered by built-in `DefaultEmbeddingFunction` (ONNX `all-MiniLM-L6-v2`), configurable text chunking with paragraph awareness, automated & manual indexing CLI (`scripts/index_data.py`), sample topic notes in `/data`, and context-augmented streaming chat.

---

## 📁 Project Structure

```text
Personal_AI/
├── .env.example              # Example environment variables (API key)
├── README.md                 # Setup, run commands, RAG testing & architecture
├── data/                     # DSA topic notes for RAG indexing
│   ├── dynamic_programming.md
│   ├── graph_algorithms.md
│   ├── binary_search.md
│   └── trees_and_heaps.md
├── eval/                     # RAG evaluation benchmark dataset & metrics
│   ├── questions.json        # 24 benchmark questions covering all notes
│   └── results.json          # Exported evaluation metrics & rankings
├── scripts/
│   ├── index_data.py         # CLI script to (re)index notes & test retrieval
│   └── eval_retrieval.py     # Retrieval evaluation harness (Top-1, Top-3 accuracy)
├── backend/
│   ├── main.py               # FastAPI application, CORS setup & router registration
│   ├── chat.py               # Groq streaming logic (llama-3.3-70b-versatile), multi-turn context, RAG injection
│   ├── db.py                 # SQLite database persistence (conversations & messages)
│   ├── rag.py                # RAG pipeline: ChromaDB vector store & ONNX DefaultEmbeddingFunction
│   ├── tools.py              # Placeholder for Day 5: Code Execution Sandbox & Tools
│   ├── chroma_db/            # Persistent ChromaDB vector database files
│   ├── requirements.txt      # Python dependencies (groq, chromadb, fastapi)
│   └── .env.example          # Backend-local env template
└── frontend/
    ├── index.html            # Main HTML with Google Fonts (Inter, JetBrains Mono)
    ├── package.json          # Frontend dependencies & scripts
    ├── vite.config.js        # Vite config with Tailwind CSS plugin & port 5173
    └── src/
        ├── main.jsx          # React DOM entrypoint
        ├── App.jsx           # Root application component
        ├── index.css         # Tailwind directives, animations & custom scrollbars
        └── components/
            ├── Sidebar.jsx      # Conversation history drawer, new chat & deletion
            ├── ChatWindow.jsx   # Top-level state orchestration, DB sync & streaming
            ├── MessageList.jsx  # Conversation bubbles, markdown formatting, copy code
            └── MessageInput.jsx # Input textarea, keybindings (Enter/Shift+Enter), send/stop
```


---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- **Python 3.10+** (tested on Python 3.14)
- **Node.js 18+** & **npm** (tested on Node v25 / npm 11)
- A Groq API key from [Groq Console](https://console.groq.com/keys)

---

### 2. Backend Setup

#### A. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### B. Install Python Dependencies
```bash
pip install -r backend/requirements.txt
```

#### C. Configure Environment Variables
Copy `.env.example` to `.env` in the root directory:

```bash
cp .env.example .env
```

Open `.env` and set your Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

---

### 3. Frontend Setup

Navigate into the `frontend/` folder and install dependencies:

```bash
cd frontend
npm install
```

---

## 🏃 Running Backend + Frontend Together

To run both services concurrently, open two terminal windows:

### Terminal 1: Start Backend (FastAPI on Port 8000)

**From project root:**
```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000
```

```bash
# macOS / Linux
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

*The backend will be live at [http://localhost:8000](http://localhost:8000).*

---

### Terminal 2: Start Frontend (Vite on Port 5173)

**From project root:**
```bash
cd frontend
npm run dev
```

*The frontend UI will be live at [http://localhost:5173](http://localhost:5173).*

Open your browser to [http://localhost:5173](http://localhost:5173) to start practicing competitive programming with your AI coach!

---

## 🧪 Testing the Streaming Endpoint with `curl`

> **Note on Windows PowerShell:** Use `curl.exe` instead of `curl` (to avoid PowerShell's `Invoke-WebRequest` alias). The `-N` (or `--no-buffer`) flag is **critical** because it instructs curl to output incoming chunks immediately rather than buffering them.

### Option A: Chunked Plain Text Streaming (Default)

Streams tokens directly to the terminal as words arrive:

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain Dijkstra algorithm in 3 short bullet points."}'
```

**Windows PowerShell:**
```powershell
curl.exe -N -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{\"message\": \"Explain Dijkstra algorithm in 3 short bullet points.\"}'
```

---

### Option B: Server-Sent Events (SSE) Streaming

Include `Accept: text/event-stream` to receive streaming Server-Sent Events frames:

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message": "What is the time complexity of QuickSort best vs worst case?"}'
```

**Windows PowerShell:**
```powershell
curl.exe -N -X POST http://localhost:8000/chat -H "Content-Type: application/json" -H "Accept: text/event-stream" -d '{\"message\": \"What is the time complexity of QuickSort best vs worst case?\"}'
```

---

## 🧠 How Streaming Works: End-to-End Deep Dive

### 1. The Core Problem with Standard HTTP
In standard HTTP/REST requests, the client issues a request and waits while the server finishes generating the entire text. For an LLM answering a complex algorithmic problem, this causes a 3 to 10 second delay with an empty screen before displaying a wall of text.

```text
Standard HTTP:
[User Prompt] ──> [Server waits 6s for LLM to finish] ──> [Single Large Response Payload]
```

### 2. How the Frontend Consumes the Stream Incrementally

With streaming, tokens are rendered in the browser in real time as they leave the model:

```text
Streaming Architecture:
[User Prompt] ──> [FastAPI opens HTTP connection]
                    │
                    ├──> Chunk 1 ("To")     ──> [Browser ReadableStream reader.read()] ──> State += "To"     ──> [Renders]
                    ├──> Chunk 2 (" solve") ──> [Browser ReadableStream reader.read()] ──> State += " solve" ──> [Renders]
                    ├──> Chunk 3 (" this,") ──> [Browser ReadableStream reader.read()] ──> State += " this," ──> [Renders]
                    │    ...
                    └──> Stream Done (Connection closes)
```

Here is the exact step-by-step mechanism in `frontend/src/components/ChatWindow.jsx`:

1. **`fetch` without buffering:**
   ```javascript
   const response = await fetch('http://localhost:8000/chat', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ message: promptText }),
     signal: abortController.signal,
   });
   ```
   Unlike `await response.text()` or `await response.json()` (which deliberately buffer the full payload until EOF), the browser's `response.body` exposes a raw `ReadableStream`.

2. **Reading the stream with `ReadableStreamDefaultReader`:**
   ```javascript
   const reader = response.body.getReader();
   const decoder = new TextDecoder('utf-8');
   ```
   The `reader.read()` method returns a Promise that resolves whenever **at least one TCP network packet with payload bytes arrives**, rather than waiting for connection termination.

3. **Incremental loop & React State updates:**
   ```javascript
   let accumulated = '';
   while (true) {
     const { done, value } = await reader.read();
     if (done) break;

     // Decode byte array Uint8Array to string
     const chunkText = decoder.decode(value, { stream: true });
     accumulated += chunkText;

     // Update assistant message state
     setMessages((prev) =>
       prev.map((msg) =>
         msg.id === assistantMessageId
           ? { ...msg, content: accumulated }
           : msg
       )
     );
   }
   ```
   - `{ value }` is a `Uint8Array` containing the bytes emitted by FastAPI in that HTTP chunk.
   - `decoder.decode(value, { stream: true })` turns raw bytes into text without cutting multi-byte UTF-8 code points in half.
   - Each iteration updates React state (`messages`), triggering an immediate component re-render.
   - Users visually see each word and code snippet appear in real time with virtually zero latency.

---

## 📚 RAG Pipeline, Indexing & Verification

> ℹ️ **Embedding Provider Notice:** The embedding provider uses ChromaDB's built-in `DefaultEmbeddingFunction` (ONNX `all-MiniLM-L6-v2`, 384 dimensions) with lazy client loading for fast startup and low memory usage (<512MB RAM). Re-indexing can be performed anytime via `python scripts/index_data.py`.

### 1. (Re)Index DSA Notes into ChromaDB
To rebuild the collection from scratch with the local embedding model:

```bash
# Clean rebuild with default chunking (chunk_size=600, overlap=120):
python scripts/index_data.py
```

### 2. Verify Semantic Retrieval from the Terminal
Test which chunks are retrieved for any question without starting the full server:

```bash
python scripts/index_data.py --query "How do I choose between BFS and DFS for graphs?" --test-only
```

### 3. Experiment with Custom Chunking Parameters
```bash
python scripts/index_data.py --chunk-size 800 --chunk-overlap 150 --query "What is 0/1 knapsack space optimization?"
```

### 4. RAG & Tools REST API Inspection Endpoints
- **Check vector store status & count:**
  `curl http://localhost:8000/rag/status`
- **Inspect top-K retrieved chunks via HTTP:**
  `curl "http://localhost:8000/rag/query?q=Dijkstra&top_k=3"`
- **List registered action tools:**
  `curl http://localhost:8000/tools`
- **Execute an action tool:**
  `curl -X POST http://localhost:8000/tools/execute -H "Content-Type: application/json" -d '{"name": "suggest_problem", "arguments": {"topic": "dynamic_programming"}}'`
- **Response Headers:**
  Calls to `POST /chat` automatically include `X-Rag-Chunks` and `X-Rag-Sources` headers showing which notes grounded the AI coach's response.

### 5. Running the Retrieval Evaluation Harness
A dedicated benchmark evaluation suite tests retrieval accuracy across all DSA note files using local vector search (zero LLM calls or API charges):

```bash
# Run retrieval evaluation with default parameters (top_k=3, eval/questions.json):
python scripts/eval_retrieval.py

# Evaluate with custom Top-K and export structured results to JSON:
python scripts/eval_retrieval.py --top-k 3 --json-out eval/results.json

# Use a custom benchmark questions file:
python scripts/eval_retrieval.py --questions-path eval/questions.json --top-k 5
```

**Evaluation Report Includes:**
- **Top-1 Accuracy**: Percentage of questions where the expected note file is retrieved at Rank 1.
- **Top-3 Accuracy**: Percentage of questions where the expected note file appears within the Top-3 chunks.
- **Per-Question PASS/FAIL**: Summary table displaying the target document, top-1 retrieved document, similarity score, and match rank.
- **Average Similarity**: Average cosine similarity score of top-retrieved context chunks across the benchmark dataset.

---

## 🛣️ Development Roadmap

- [x] **Day 1: Backend Foundation & Streaming Chat Endpoint** (FastAPI, Groq SDK streaming with `llama-3.3-70b-versatile`, CORS, SSE & chunked HTTP).
- [x] **Day 2: Modern Frontend** (React + Vite, Tailwind CSS, streaming token-by-token rendering, markdown code blocks).
- [x] **Day 3: Database & Persistence** (SQLite conversations and messages schema, REST endpoints, multi-turn context, responsive history sidebar).
- [x] **Day 4: RAG & Problem Knowledge Base** (ChromaDB persistent vector store, local `all-MiniLM-L6-v2` embeddings, configurable chunking, notes indexing, prompt context injection).
- [x] **Day 5: Action Tools & Function Calling** (Curated problem lookup `suggest_problem`, history struggle analyzer `get_weak_topics`, persistent submission tracker `log_submission`).
- [x] **Day 6: Polish, Error Handling & System Hardening** (Loading/typing indicator before first token, 30s request timeouts, human-readable error cards, responsive collapsible drawer layout, input validation, try/except error shielding across DB/RAG/Groq, and structured Python logging).


