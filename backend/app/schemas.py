from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# ── Resume sub-models ──────────────────────────────────────────────────────────

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    minor: Optional[str] = None
    cgpa: Optional[str] = None
    dates: Optional[str] = None
    extra: Optional[str] = None


class Experience(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    responsibilities: List[str] = []
    extra: Optional[str] = None


class Project(BaseModel):
    name: Optional[str] = None
    links: List[str] = []
    description: Optional[str] = None
    tech_used: List[str] = []
    extra: Optional[str] = None


class TechnicalSkills(BaseModel):
    languages: List[str] = []
    frameworks: List[str] = []
    tools: List[str] = []
    platforms: List[str] = []
    other: List[str] = []


class Certification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    extra: Optional[str] = None


class Achievement(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    extra: Optional[str] = None


class ResumeData(BaseModel):
    personal_info: PersonalInfo = PersonalInfo()
    education: List[Education] = []
    experience: List[Experience] = []
    projects: List[Project] = []
    technical_skills: TechnicalSkills = TechnicalSkills()
    certifications: List[Certification] = []
    achievements: List[Achievement] = []
    miscellaneous: Optional[str] = None


# ── Request / Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    query: str


class AssistantResponse(BaseModel):
    answer: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Literal["resume", "inference"]
    missing_data: List[str] = []