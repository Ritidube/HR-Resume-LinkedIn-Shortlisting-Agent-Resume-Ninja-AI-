from pydantic import BaseModel, Field


class JDProfile(BaseModel):
    title: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_years_experience: int
    domain: str
    education_requirement: str
    key_responsibilities: list[str]


class CandidateProfile(BaseModel):
    name: str
    skills: list[str]
    years_experience: float
    domain_history: list[str]
    education: str
    certifications: list[str]
    projects: list[str]
    raw_text: str = ""


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