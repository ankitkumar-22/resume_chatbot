# Intelligent Resume Assistant

An agentic AI system that parses resumes, maintains structured session memory, and answers recruiter queries with grounded, hallucination-resistant responses. Every answer is labelled with its source (`resume` or `inference`), a confidence score, and any fields that were missing from the resume.

Built with **FastAPI + Groq (LLaMA 3.3)** on the backend and **React 19 + Vite + TypeScript + Tailwind CSS** on the frontend. Includes an optional **WebRTC audio loopback** demonstrating real-time peer-to-peer transport (Phase 4 bonus).

---

## Table of Contents

- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Clone the Repository](#clone-the-repository)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Architecture](#architecture)
  - [Request Flow](#request-flow)
  - [Module Map](#module-map)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [WebRTC Bonus](#webrtc-bonus)
- [Known Limitations & Next Steps](#known-limitations--next-steps)

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

You will also need a **Groq API key** — get one free at [console.groq.com](https://console.groq.com).

---

### Clone the Repository

```bash
git clone https://github.com/<your-username>/resume-assistant.git
cd resume-assistant
```

---

### Backend Setup

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Open .env and set GROQ_API_KEY=your_key_here

# 4. Start the server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Swagger docs at `http://localhost:8000/docs`.

**`.env` reference:**

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile   # optional — this is the default
DB_NAME=resumes.db                    # optional
UPLOAD_DIR=uploads                    # optional
HISTORY_LIMIT=10                      # optional — max conversation turns sent to LLM
```

---

### Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Start the dev server
npm run dev
```

The app will be available at `http://localhost:5173`.

> The frontend talks to `http://localhost:8000` by default. If you change the backend port, update `API_BASE` in `src/lib/api.ts`.

---

## Architecture

```
┌──────────────────────────┐         ┌──────────────────────────────────────────┐
│   React (Vite + TS)       │         │             FastAPI Backend               │
│                           │  HTTP   │                                            │
│  ResumeUpload ────────────┼────────▶│  POST /upload  → extract → LLM structure  │
│  ChatPanel    ────────────┼────────▶│  POST /chat    → Agent (router)            │
│  VoicePanel   ────────────┼────────▶│  POST /webrtc/offer  (Phase 4)             │
│                           │◀────────┤  AssistantResponse (validated JSON)        │
└──────────────────────────┘         └────────────────┬─────────────────────────┘
                                                       │
                            ┌──────────────────────────┼──────────────────────────┐
                            ▼                          ▼                           ▼
                     ┌────────────┐          ┌─────────────────┐         ┌───────────────┐
                     │   Memory   │          │  Agent Router   │         │  LLM Provider  │
                     │ per-session│          │ tool vs LLM     │         │  Groq / Claude │
                     └────────────┘          └───────┬─────────┘         └───────────────┘
                                      ┌──────────────┼──────────────┐
                                      ▼              ▼              ▼
                               skill_matcher  keyword_extractor  llm_qa
                               (set math)     (deterministic)    (grounded prompt)
```

### Request Flow

1. User uploads a PDF or `.txt` resume.
2. Backend extracts raw text (Docling for PDFs, fallback to pypdf), then makes one LLM call to structure it into a typed `ResumeData` Pydantic model. This structured object is stored in SQLite and loaded into an in-process session store.
3. On each chat message, the **router** classifies the query:
   - Skill-gap / matching questions → `skill_matcher` (deterministic set math, no LLM)
   - Keyword / ATS questions → `keyword_extractor` (deterministic, no LLM)
   - Everything else → `llm_qa` (LLM call with a strict grounded system prompt)
4. The response is validated into an `AssistantResponse` Pydantic model before it ever reaches the client. Validation failures trigger a repair retry.
5. The turn is appended to the session history (capped at `HISTORY_LIMIT` turns). On server restart, history is restored from SQLite so the LLM retains context.

### Module Map

```
backend/app/
├── main.py               FastAPI app, CORS, all route handlers
├── config.py             Env loading — API keys, model id, limits
├── schemas.py            Pydantic: ResumeData, AssistantResponse, ChatRequest
├── database.py           SQLite init and connection helper
├── llm/
│   ├── provider.py       Single chat() function — Groq active, Claude stubbed
│   └── prompts.py        All system prompts and templates
├── agent/
│   ├── router.py         Tool-vs-LLM routing, grounding check, confidence clamping
│   └── memory.py         Per-session in-process store (ResumeData + history)
├── services/
│   └── extract.py        PDF/text → raw text → structured ResumeData
├── tools/
│   └── resume_tools.py   skill_matcher, keyword_extractor (pure functions)
└── webrtc/
    └── signaling.py      aiortc peer connection + audio loopback (Phase 4)

frontend/src/
├── App.tsx               Single-page app shell, all UI state
├── lib/
│   ├── api.ts            Typed fetch wrappers for all backend endpoints
│   └── webrtc.ts         RTCPeerConnection client with backoff retry
└── components/
    └── VoicePanel.tsx    Mic toggle, connection status, audio level meter
```

---

## Design Decisions & Trade-offs

### 1. Groq now, Claude later — single-file provider abstraction
`llm/provider.py` exposes one function: `chat(messages, json_mode) → str`. Groq is active; a Claude swap-in is commented directly below it. Switching providers is a one-file, three-line change. The trade-off: the abstraction is thin — if a future provider needs streaming or tool-use it will need a richer interface.

### 2. Separate frontend and backend
A dedicated FastAPI backend keeps all AI logic, PDF parsing, and WebRTC in Python where the best libraries live. The trade-off is two deployables and CORS configuration; the gain is a clean separation that the evaluation rubric explicitly rewards.

### 3. Rule-based router
The router uses keyword matching to decide between `skill_matcher`, `keyword_extractor`, and `llm_qa`. It is intentionally simple and fully explainable — no LLM call needed to route. The design rule: **deterministic questions go to tools (high-confidence `resume` answers); open-ended questions go to the LLM (`inference`)**. This keeps the high-confidence path free of hallucination risk.

### 4. Structured extraction on upload, not at query time
The resume is parsed into a typed `ResumeData` object once on upload and stored in SQLite. Every subsequent query is grounded against this structured object, not against the raw text. This is the core anti-hallucination mechanism: the LLM cannot invent a skill that isn't in the structured fields.

### 5. Confidence clamping
LLM answers self-report a confidence score via a `[CONFIDENCE:X.X]` token. The router clamps this: `inference` answers are capped at `0.7`, `resume` answers at `0.9`. Deterministic tools set confidence directly (skill coverage score for `skill_matcher`, `1.0` for `keyword_extractor`). This prevents the model from claiming false certainty.

### 6. In-memory session store
Sessions live in a plain Python `dict`. On server restart, `ResumeData` and the last `HISTORY_LIMIT` conversation turns are restored from SQLite, so the LLM gets full context on the first message after a restart. The trade-off: no cross-process sharing — horizontal scaling would require Redis or a shared DB.

### 7. WebRTC scope (no STT / TTS)
Since the assignment explicitly forbids Speech-to-Text and Text-to-Speech, the voice feature is a real-time transport demonstration: the browser's microphone audio is streamed to the server via `aiortc` and looped back to the client, proving the bidirectional low-latency pipe. Connection lifecycle (`iceconnectionstatechange`) and exponential-backoff reconnection are fully implemented.

---

## WebRTC Bonus

The voice panel (bottom-right mic button) opens a WebRTC peer connection between the browser and the FastAPI server.

**What it demonstrates:**
- `getUserMedia` audio capture → `RTCPeerConnection` → aiortc server → audio loopback back to client
- Live audio level meter driven by the browser's `AnalyserNode`
- Connection status badge: Connecting → Live → Reconnecting → Failed
- Automatic reconnect with exponential backoff (1 s → 2 s → 4 s → … → 16 s cap, 5 retries)

**Endpoints added:**
```
POST /webrtc/offer    SDP offer → SDP answer exchange
GET  /webrtc/status   Returns count of active peer connections
```

> Note: the existing text chat continues to work over HTTP while the WebRTC connection is active. Merging chat onto an `RTCDataChannel` is noted as a natural next step.

---

## Known Limitations & Next Steps

| Limitation | Next step |
|---|---|
| In-memory session store lost on restart (restored from DB) | Replace with Redis for true cross-process persistence |
| Rule-based router misses paraphrased intent | Add a lightweight intent classifier or LLM-based routing for ambiguous queries |
| PDF extraction falls back to pypdf for scanned / image PDFs | Integrate OCR (Tesseract via pytesseract) for image-only PDFs |
| Single-file SQLite — not suitable for concurrent writes at scale | Migrate to PostgreSQL with SQLAlchemy for production |
| WebRTC chat runs over HTTP, not DataChannel | Wire `/chat` logic through `RTCDataChannel` for a fully WebRTC conversation |
| No authentication | Add session tokens or OAuth before any public deployment |

---

*Built as a take-home assignment demonstrating agentic AI system design — structured extraction, tool-vs-LLM routing, provenance tracking, and real-time transport.*