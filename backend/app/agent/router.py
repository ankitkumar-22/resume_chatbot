"""
agent/router.py

1. route(query)         → which tool or "llm_qa"
2. run(session, query)  → AssistantResponse
"""

import json
import re
from app.schemas import AssistantResponse, ResumeData
from app.tools.resume_tools import skill_matcher, keyword_extractor
from app.llm.provider import chat
from app.llm.prompts import build_qa_system, build_skill_match_prompt


# ── 1. Routing decision ────────────────────────────────────────────────────────

def route(query: str) -> str:
    """
    Rule-based router.
    Returns one of: "skill_matcher" | "keyword_extractor" | "llm_qa"
    """
    q = query.lower()

    if any(k in q for k in (
        "match", "fit for", "suitable for", "required skills",
        "missing skills", "skill gap", "qualify", "job requirements",
        "do i have", "does the candidate have",
    )):
        return "skill_matcher"

    if any(k in q for k in (
        "keywords", "ats", "key terms", "extract terms",
        "what technologies", "what tools", "tech stack",
    )):
        return "keyword_extractor"

    return "llm_qa"


# ── 2. Tool execution ──────────────────────────────────────────────────────────

def _run_skill_matcher(resume: ResumeData, query: str) -> AssistantResponse:
    """
    Extract target skills from the query via the LLM, then run deterministic
    set-math via skill_matcher.
    """
    # Ask LLM to pull the skill list out of the query
    extract_msgs = [
        {
            "role": "system",
            "content": (
                "Extract the list of required skills from the user query. "
                "Return ONLY a JSON array of skill strings, e.g. [\"Python\", \"SQL\"]. "
                "No explanation."
            ),
        },
        {"role": "user", "content": query},
    ]
    raw = chat(extract_msgs, json_mode=True)

    try:
        target_skills: list[str] = json.loads(raw)
        if not isinstance(target_skills, list):
            target_skills = []
    except Exception:
        target_skills = []

    result = skill_matcher(resume, target_skills)

    if not target_skills:
        answer = (
            "I couldn't identify specific skills in your query. "
            "Please list the required skills explicitly, e.g. 'Does the candidate know Python, SQL, and Docker?'"
        )
        return AssistantResponse(answer=answer, source="resume", missing_data=[])

    matched_str  = ", ".join(result["matched"])  if result["matched"]  else "none"
    missing_str  = ", ".join(result["missing"])  if result["missing"]  else "none"
    coverage_pct = int(result["coverage_score"] * 100)

    answer = (
        f"Skill match analysis:\n"
        f"- Matched ({len(result['matched'])}): {matched_str}\n"
        f"- Missing ({len(result['missing'])}): {missing_str}\n"
        f"- Coverage: {coverage_pct}%"
    )

    return AssistantResponse(
        answer=answer,
        source="resume",
        missing_data=result["missing"],
    )


def _run_keyword_extractor(resume: ResumeData) -> AssistantResponse:
    result = keyword_extractor(resume)
    keywords = result["keywords"]

    if not keywords:
        return AssistantResponse(
            answer="No technical keywords found in the resume.",
            source="resume",
            missing_data=[],
        )

    answer = f"Technical keywords extracted from resume ({result['count']} total):\n" + ", ".join(keywords)
    return AssistantResponse(answer=answer, source="resume", missing_data=[])


def _run_llm_qa(resume: ResumeData, query: str, history: list[dict]) -> AssistantResponse:
    """
    Open-ended Q&A via LLM, grounded against structured resume data.
    Parses [SOURCE:...] token from the reply.
    """
    resume_json = resume.model_dump_json(indent=2)

    messages = [{"role": "system", "content": build_qa_system(resume_json)}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})

    raw_answer = chat(messages, json_mode=False)

    # Parse the [SOURCE:...] token appended by the prompt
    source_match = re.search(r"\[SOURCE:(resume|inference)\]", raw_answer)
    source = source_match.group(1) if source_match else "inference"

    # Strip the token from the visible answer
    clean_answer = re.sub(r"\s*\[SOURCE:(resume|inference)\]", "", raw_answer).strip()

    # Grounding check: if LLM claims "resume" but references something that
    # looks like it isn't in the structured data, downgrade to "inference"
    if source == "resume":
        source = _grounding_check(clean_answer, resume) or "inference"

    return AssistantResponse(
        answer=clean_answer,
        source=source,
        missing_data=[],
    )


# ── 3. Grounding check ─────────────────────────────────────────────────────────

def _grounding_check(answer: str, resume: ResumeData) -> str | None:
    """
    Light check: if the answer says 'not present in the resume' it's still
    source:resume (we acknowledged the gap).  Otherwise verify at least one
    substantive term in the answer exists somewhere in the resume text.
    Returns "resume" if grounded, None (→ caller will use "inference") if not.
    """
    if "not present in the resume" in answer.lower():
        return "resume"

    resume_blob = resume.model_dump_json().lower()
    # Take the first 10 non-trivial words from the answer and check if at
    # least one appears in the resume JSON
    words = [w.lower().strip(".,;:\"'()") for w in answer.split() if len(w) > 4]
    for word in words[:10]:
        if word in resume_blob:
            return "resume"

    return None


# ── 4. Main entry point ────────────────────────────────────────────────────────

def run(resume: ResumeData, query: str, history: list[dict]) -> tuple[str, AssistantResponse]:
    """
    Returns (intent, AssistantResponse).
    intent is logged by the caller for debugging / README demos.
    """
    intent = route(query)
    print(f"[router] intent={intent!r}  query={query[:80]!r}")

    if intent == "skill_matcher":
        response = _run_skill_matcher(resume, query)
    elif intent == "keyword_extractor":
        response = _run_keyword_extractor(resume)
    else:
        response = _run_llm_qa(resume, query, history)

    return intent, response
