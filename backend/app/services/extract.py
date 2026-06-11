"""
services/extract.py

Two responsibilities:
1. raw_text_from_file  — Docling (PDF) or plain read (txt) → raw string
2. structure_resume    — raw text → ResumeData via one LLM pass
"""

import json
import os
from app.schemas import ResumeData
from app.llm.provider import chat
from app.llm.prompts import EXTRACTION_SYSTEM, EXTRACTION_SCHEMA_HINT


# ── 1. Raw text extraction ─────────────────────────────────────────────────────

def raw_text_from_file(file_path: str) -> str:
    """Return plain text from a PDF (via Docling) or .txt file."""
    ext = file_path.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return _extract_with_docling(file_path)
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


def _extract_with_docling(file_path: str) -> str:
    """
    Use Docling for structured PDF extraction.
    Falls back to pypdf if Docling is not installed.
    """
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        # Export as markdown — preserves headings, tables, lists
        return result.document.export_to_markdown()

    except ImportError:
        # Graceful fallback so the app works even without Docling installed
        print("⚠  Docling not installed — falling back to pypdf")
        return _extract_with_pypdf(file_path)


def _extract_with_pypdf(file_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text


# ── 2. Structured extraction ───────────────────────────────────────────────────

def structure_resume(raw_text: str) -> ResumeData:
    """
    Send raw resume text to the LLM and parse the response into ResumeData.
    Retries once if the first parse fails.
    """
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM + "\n" + EXTRACTION_SCHEMA_HINT},
        {"role": "user",   "content": f"Parse this resume:\n\n{raw_text}"},
    ]

    for attempt in range(2):
        raw_json = chat(messages, json_mode=True)
        try:
            data = json.loads(raw_json)
            return ResumeData.model_validate(data)
        except Exception as e:
            if attempt == 0:
                # Ask the LLM to fix its own output
                messages.append({"role": "assistant", "content": raw_json})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The JSON you returned failed validation: {e}\n"
                        "Please return only valid JSON matching the schema."
                    ),
                })
            else:
                print(f"⚠  Resume structuring failed after retry: {e}")
                # Return an empty ResumeData rather than crashing
                return ResumeData()
