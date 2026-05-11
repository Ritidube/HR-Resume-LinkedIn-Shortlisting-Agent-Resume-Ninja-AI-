from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Job Description ───────────────────────────────────────────────────────────

class JDProfile(BaseModel):
    title: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_years_experience: int
    domain: str
    education_requirement: str
    key_responsibilities: list[str]
    role_title: str = ""
    nice_to_have_skills: list[str] = Field(default_factory=list)


# ── Candidate ─────────────────────────────────────────────────────────────────

class EducationEntry(BaseModel):
    degree: str = ""
    field: str = ""          # LLM may return null for school-level entries
    institution: str = ""


class ProjectEntry(BaseModel):
    title: str
    summary: str


class CandidateProfile(BaseModel):
    name: str
    skills: list[str]
    years_experience: float
    domain_history: list[str]
    education: str = ""
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    raw_text: str = ""

    # Richer fields
    email: Optional[str] = None
    linkedin_url: Optional[str] = None        # extracted from resume text
    current_role: Optional[str] = None
    education_entries: list[EducationEntry] = Field(default_factory=list)
    project_entries: list[ProjectEntry] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    linkedin_extra: Optional[str] = None     # summary text fetched from LinkedIn


# ── Scoring ───────────────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    score: float = Field(ge=0, le=10)
    justification: str


class CandidateResult(BaseModel):
    name: str
    skills_match: DimensionScore
    experience_relevance: DimensionScore
    education_certs: DimensionScore
    project_portfolio: DimensionScore
    communication_quality: DimensionScore
    weighted_total: float
    recommendation: str


# ── Human-in-the-Loop Override ────────────────────────────────────────────────

class ScoreOverride(BaseModel):
    """Logged whenever HR manually changes a dimension score."""
    candidate_name: str
    dimension: str                           # e.g. "skills_match"
    original_score: float
    new_score: float
    reason: str
    overridden_by: str = "HR"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())