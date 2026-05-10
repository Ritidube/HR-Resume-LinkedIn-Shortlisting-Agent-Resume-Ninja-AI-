# from pydantic import BaseModel, Field


# class JDProfile(BaseModel):
#     title: str
#     required_skills: list[str]
#     preferred_skills: list[str]
#     min_years_experience: int
#     domain: str
#     education_requirement: str
#     key_responsibilities: list[str]


# class CandidateProfile(BaseModel):
#     name: str
#     skills: list[str]
#     years_experience: float
#     domain_history: list[str]
#     education: str
#     certifications: list[str]
#     projects: list[str]
#     raw_text: str = ""


# class DimensionScore(BaseModel):
#     score: float = Field(ge=0, le=10)
#     justification: str


# class CandidateResult(BaseModel):
#     name: str
#     skills_match: DimensionScore
#     experience_relevance: DimensionScore
#     education_certs: DimensionScore
#     project_portfolio: DimensionScore
#     communication_quality: DimensionScore
#     weighted_total: float
#     recommendation: str

from pydantic import BaseModel, Field
from typing import Optional


# ── Job Description ──────────────────────────────────────────────────────────

class JDProfile(BaseModel):
    # Core fields (used by existing embeddings / scorer)
    title: str
    required_skills: list[str]
    preferred_skills: list[str]          # maps to nice_to_have_skills in prompt
    min_years_experience: int
    domain: str
    education_requirement: str
    key_responsibilities: list[str]

    # New token-efficient prompt fields
    role_title: str = ""                 # duplicate of title, populated by new prompt
    nice_to_have_skills: list[str] = Field(default_factory=list)


# ── Candidate ────────────────────────────────────────────────────────────────

class EducationEntry(BaseModel):
    degree: str
    field: str
    institution: str


class ProjectEntry(BaseModel):
    title: str
    summary: str


class CandidateProfile(BaseModel):
    name: str
    skills: list[str]
    years_experience: float
    domain_history: list[str]
    education: str = ""                  # legacy flat string (kept for back-compat)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)   # legacy flat list
    raw_text: str = ""

    # New richer fields from improved resume prompt
    email: Optional[str] = None
    current_role: Optional[str] = None
    education_entries: list[EducationEntry] = Field(default_factory=list)
    project_entries: list[ProjectEntry] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


# ── Scoring ──────────────────────────────────────────────────────────────────

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