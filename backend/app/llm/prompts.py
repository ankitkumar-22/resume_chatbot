"""All prompt templates live here. No business logic."""

# ── Extraction prompt ──────────────────────────────────────────────────────────

EXTRACTION_SYSTEM = """You are a resume parser.
Your only job is to read the raw resume text and return a single JSON object
that strictly follows the schema provided.

Rules:
- Output ONLY valid JSON — no preamble, no markdown fences, no explanation.
- If a field is not present in the resume, omit it or use null / [].
- For technical_skills, distribute items across languages / frameworks / tools /
  platforms / other as best you can. When in doubt, use "other".
- Preserve exact wording from the resume; do not paraphrase.
- Put anything that genuinely has no other home in "miscellaneous".
"""

EXTRACTION_SCHEMA_HINT = """
Return JSON matching this structure exactly:
{
  "personal_info": {
    "name": str | null,
    "email": str | null,
    "phone": str | null,
    "location": str | null,
    "linkedin": str | null,
    "github": str | null,
    "website": str | null
  },
  "education": [
    {
      "institution": str | null,
      "degree": str | null,
      "major": str | null,
      "minor": str | null,
      "cgpa": str | null,
      "dates": str | null,
      "extra": str | null
    }
  ],
  "experience": [
    {
      "company": str | null,
      "role": str | null,
      "duration": str | null,
      "responsibilities": [str],
      "extra": str | null
    }
  ],
  "projects": [
    {
      "name": str | null,
      "links": [str],
      "description": str | null,
      "tech_used": [str],
      "extra": str | null
    }
  ],
  "technical_skills": {
    "languages": [str],
    "frameworks": [str],
    "tools": [str],
    "platforms": [str],
    "other": [str]
  },
  "certifications": [
    {
      "name": str | null,
      "issuer": str | null,
      "date": str | null,
      "extra": str | null
    }
  ],
  "achievements": [
    {
      "title": str | null,
      "description": str | null,
      "extra": str | null
    }
  ],
  "miscellaneous": str | null
}
"""


# ── Chat / QA prompt ───────────────────────────────────────────────────────────

def build_qa_system(resume_json: str) -> str:
    return f"""You are a professional resume assistant.

The candidate's structured resume data is provided below as JSON.
Answer questions ONLY using information present in this data.

Resume data:
{resume_json}

Rules:
- If the answer is clearly present in the resume data, answer factually and
  end your response with  [SOURCE:resume]
- If you are making an inference or evaluation beyond what the data states,
  end your response with  [SOURCE:inference]
- If information is missing, say exactly:
  "This information is not present in the resume." and end with  [SOURCE:resume]
- Do NOT fabricate details. Do NOT hallucinate.
- Keep answers concise and factual.
- After the SOURCE token, add a CONFIDENCE token: [CONFIDENCE:X.X]
  where X.X is a float between 0.0 and 1.0 reflecting how certain you are.
  Base it on how directly the resume data supports your answer.

Example ending: [SOURCE:resume] [CONFIDENCE:0.9]
"""


# ── Skill-matching prompt ──────────────────────────────────────────────────────

def build_skill_match_prompt(resume_skills: dict, target_skills: list[str]) -> str:
    return f"""You are a skill-gap analyser.

Candidate skills (from resume):
{resume_skills}

Target skills required for the role:
{target_skills}

Return a JSON object with:
{{
  "matched": [list of skills present in both],
  "missing": [list of target skills not found in resume],
  "coverage_score": float between 0 and 1
}}

Output ONLY valid JSON. No explanation.
"""