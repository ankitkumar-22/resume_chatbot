import hashlib
import json
import os
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.config import UPLOAD_DIR
from app.database import init_db, get_connection
from app.schemas import ChatRequest, AssistantResponse
from app.services.extract import raw_text_from_file, structure_resume
from app.agent import memory as mem
from app.agent.router import run as agent_run

app = FastAPI(title="Resume Assistant API")

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"ok": True, "message": "Backend is alive!"}


# ── Upload ─────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are accepted.")

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    conn = get_connection()
    cur = conn.cursor()

    # ── Duplicate check ────────────────────────────────────────────────────────
    cur.execute("SELECT id FROM resumes WHERE file_hash = ?", (file_hash,))
    existing = cur.fetchone()

    if existing:
        session_id = existing["id"]

        # Reload structured data into memory if not already there
        if mem.get_session(session_id) is None:
            cur.execute(
                "SELECT structured FROM resumes WHERE id = ?", (session_id,)
            )
            row = cur.fetchone()
            if row and row["structured"]:
                from app.schemas import ResumeData
                resume_data = ResumeData.model_validate_json(row["structured"])
                mem.create_session(session_id, resume_data)

        conn.close()
        print(f"♻  Duplicate resume — reusing session {session_id}")
        return {"session_id": session_id}

    # ── New resume ─────────────────────────────────────────────────────────────
    session_id = str(uuid.uuid4())
    file_ext = file.filename.rsplit(".", 1)[-1].lower()
    file_path = f"{UPLOAD_DIR}/{session_id}.{file_ext}"

    with open(file_path, "wb") as f:
        f.write(contents)

    # 1. Extract raw text
    raw_text = raw_text_from_file(file_path)

    # 2. Structure via LLM
    resume_data = structure_resume(raw_text)
    structured_json = resume_data.model_dump_json()

    # 3. Persist to SQLite
    cur.execute(
        """
        INSERT INTO resumes (id, filename, filepath, file_hash, raw_text, structured)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, file.filename, file_path, file_hash, raw_text, structured_json),
    )
    conn.commit()
    conn.close()

    # 4. Warm the in-memory session
    mem.create_session(session_id, resume_data)

    print(f"✅  Uploaded {file.filename}  |  session={session_id}  |  chars={len(raw_text)}")
    return {"session_id": session_id}


# ── Chat ───────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=AssistantResponse)
async def chat_with_resume(request: ChatRequest):

    # Reload session from DB if not in memory (e.g. after server restart)
    session = mem.get_session(request.session_id)
    if session is None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT structured FROM resumes WHERE id = ?", (request.session_id,)
        )
        row = cur.fetchone()
        conn.close()

        if not row or not row["structured"]:
            raise HTTPException(status_code=404, detail="Session not found.")

        from app.schemas import ResumeData
        resume_data = ResumeData.model_validate_json(row["structured"])
        mem.create_session(request.session_id, resume_data)
        session = mem.get_session(request.session_id)

    # Persist user message to DB
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (request.session_id, "user", request.query),
    )
    conn.commit()

    try:
        intent, response = agent_run(
            resume=session.resume_data,
            query=request.query,
            history=session.history,
        )

        # Update in-memory history
        mem.append_turn(request.session_id, "user", request.query)
        mem.append_turn(request.session_id, "assistant", response.answer)
        mem.set_intent(request.session_id, intent)

        # Persist assistant reply to DB
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (request.session_id, "assistant", response.answer),
        )
        conn.commit()

    except Exception as e:
        print(f"Agent error: {e}")
        response = AssistantResponse(
            answer="The AI service is temporarily unavailable. Please try again.",
            source="resume",
            missing_data=[],
        )

    conn.close()
    return response


# ── History ────────────────────────────────────────────────────────────────────
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    )
    messages = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"session_id": session_id, "messages": messages}
