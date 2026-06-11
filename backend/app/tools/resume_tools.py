"""
tools/

Each tool is a plain function with typed in/out.
Deterministic tools → source: "resume", high reliability.
"""

from app.schemas import ResumeData


# ── skill_matcher ──────────────────────────────────────────────────────────────

def skill_matcher(resume: ResumeData, target_skills: list[str]) -> dict:
    """
    Pure set-math comparison between resume skills and a target skill list.
    Returns matched, missing, and a coverage score.
    source is always "resume" because this is deterministic.
    """
    skills = resume.technical_skills

    # Flatten all skill sub-lists into one normalised set
    all_resume_skills: set[str] = set()
    for skill_list in [
        skills.languages,
        skills.frameworks,
        skills.tools,
        skills.platforms,
        skills.other,
    ]:
        all_resume_skills.update(s.lower().strip() for s in skill_list)

    # Also pick up tech_used from projects
    for project in resume.projects:
        all_resume_skills.update(t.lower().strip() for t in project.tech_used)

    normalised_targets = [t.lower().strip() for t in target_skills]

    matched = [t for t in normalised_targets if t in all_resume_skills]
    missing = [t for t in normalised_targets if t not in all_resume_skills]
    coverage = len(matched) / len(normalised_targets) if normalised_targets else 0.0

    return {
        "matched": matched,
        "missing": missing,
        "coverage_score": round(coverage, 2),
        "source": "resume",
    }


# ── keyword_extractor ──────────────────────────────────────────────────────────

def keyword_extractor(resume: ResumeData) -> dict:
    """
    Extract notable technical keywords from the resume without LLM.
    Pulls from skills, project tech_used, and experience responsibilities.
    source is always "resume".
    """
    keywords: set[str] = set()
    skills = resume.technical_skills

    for skill_list in [
        skills.languages,
        skills.frameworks,
        skills.tools,
        skills.platforms,
        skills.other,
    ]:
        keywords.update(s.strip() for s in skill_list if s.strip())

    for project in resume.projects:
        keywords.update(t.strip() for t in project.tech_used if t.strip())

    # Pull single capitalised/uppercase tokens from responsibilities
    # (catches things like "REST", "CI/CD", "AWS" buried in bullet points)
    for exp in resume.experience:
        for line in exp.responsibilities:
            for word in line.split():
                clean = word.strip(".,;:()")
                if len(clean) >= 2 and (clean.isupper() or clean[0].isupper()):
                    keywords.add(clean)

    return {
        "keywords": sorted(keywords),
        "count": len(keywords),
        "source": "resume",
    }
