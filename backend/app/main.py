from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import uuid

from app.schemas import ChatRequest, AssistantResponse

app = FastAPI(title="Resume Assistant API")

# --- CORS Configuration ---
# This strictly allows your Vite React app to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Store (Phase 1 MVP) ---
# Maps session_id to filename/parsed text
session_memory: Dict[str, dict] = {}

# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Simple endpoint to verify the server is running."""
    return {"ok": True, "message": "Backend is alive!"}

@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Receives the PDF/TXT from React and creates a session."""
    if not file.filename.endswith(('.pdf', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # 1. Generate a unique session ID
    session_id = str(uuid.uuid4())
    
    # 2. In Phase 1, you would extract text here. For now, we mock it.
    session_memory[session_id] = {
        "filename": file.filename,
        "raw_text": "Mock extracted text would go here."
    }
    
    print(f"✅ Uploaded {file.filename} into session: {session_id}")
    
    # 3. Return the exact key the React frontend is expecting
    return {"session_id": session_id}

@app.post("/chat", response_model=AssistantResponse)
async def chat_with_resume(request: ChatRequest):
    """Receives the query, checks memory, and returns formatted AI response."""
    
    if request.session_id not in session_memory:
        raise HTTPException(status_code=404, detail="Session not found. Please upload again.")
    
    print(f"💬 Received query: '{request.query}' using model: '{request.model}'")
    
    # --- MOCK ROUTER LOGIC ---
    # In Phase 2, this is where your Groq LLM and Tool Router will live.
    # For now, we return valid Pydantic models to test the React UI.
    
    query_lower = request.query.lower()
    
    if "gpa" in query_lower or "salary" in query_lower:
        return AssistantResponse(
            answer="Not mentioned in the resume. I only state what the document supports.",
            confidence=0.9,
            source="inference",
            missing_data=["GPA", "Expected Salary"]
        )
        
    if "skill" in query_lower:
        return AssistantResponse(
            answer="The candidate has strong experience in Python, React, and FastAPI.",
            confidence=0.95,
            source="resume",
            missing_data=[]
        )
        
    return AssistantResponse(
        answer=f"I received your question about '{request.query}'. Once you plug in the Groq API, I will analyze the actual PDF!",
        confidence=0.6,
        source="inference",
        missing_data=[]
    )