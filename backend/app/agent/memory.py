"""
agent/memory.py

In-process session store.
Each session holds the structured ResumeData and the last N conversation turns.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from app.schemas import ResumeData
from app.config import HISTORY_LIMIT


@dataclass
class Session:
    resume_data: ResumeData
    history: list[dict] = field(default_factory=list)   # {"role": ..., "content": ...}
    last_intent: str = "llm_qa"


# Global in-process store  {session_id: Session}
_store: dict[str, Session] = {}


def create_session(session_id: str, resume_data: ResumeData) -> None:
    _store[session_id] = Session(resume_data=resume_data)


def get_session(session_id: str) -> Session | None:
    return _store.get(session_id)


def append_turn(session_id: str, role: str, content: str) -> None:
    session = _store.get(session_id)
    if session is None:
        return
    session.history.append({"role": role, "content": content})
    # Keep only the last N turns (each turn = 1 message)
    if len(session.history) > HISTORY_LIMIT:
        session.history = session.history[-HISTORY_LIMIT:]


def set_intent(session_id: str, intent: str) -> None:
    session = _store.get(session_id)
    if session:
        session.last_intent = intent
