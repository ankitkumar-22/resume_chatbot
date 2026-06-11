import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# SQLite
DB_NAME: str = os.getenv("DB_NAME", "resumes.db")

# File uploads directory
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")

# Max conversation turns kept in history sent to the LLM
HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10"))
