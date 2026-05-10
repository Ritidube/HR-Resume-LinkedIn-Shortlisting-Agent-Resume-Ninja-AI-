import json
from models import JDProfile, CandidateProfile, CandidateResult, DimensionScore
from embeddings import skills_similarity, portfolio_similarity
from parsers import safe_parse_json
from llm_client import CALL_LLM_HERE

WEIGHTS = {
    "skills_match": 0.30,
    "experience_relevance": 0.25,
    "education_certs": 0.15,
    "project_portfolio": 0.20,
    "communication_quality": 0.10,
}

SCORE_PROMPT = """You are an HR evaluation engine. Score this candidate ONLY on these 3 dimensions.
Return ONLY valid JSON — no markdown, no extra text:
{{
  "experience_relevance": {{"score": 0, "justification": "one line"}},
  "education_certs":      {{"score": 0, "justification": "one line"}},
  "communication_quality":{{"score": 0, "justification": "one line"}}
}}

RUBRIC:
- experience_relevance: 0=unrelated, 5=adjacent domain, 10=exact domain+seniority (JD needs {min_years}yrs in {domain})
- education_certs: 0=does not meet minimum, 5=meets, 10=exceeds+extra certs (JD requires: {edu_req})
- communication_quality: judge clarity and structure of resume text itself

CANDIDATE PROFILE:
{candidate_json}
"""

def score_candidate(jd: JDProfile, candidate: CandidateProfile) -> CandidateResult:
    # Embedding-based scores
    skills_sim = skills_similarity(jd, candidate)
    portfolio_sim = portfolio_similarity(jd, candidate)
    skills_score = round(skills_sim * 10, 1)
    portfolio_score = round(portfolio_sim * 10, 1)

    # LLM-based scores (3 dims in one call)
    candidate_summary = candidate.model_dump(exclude={"raw_text"})
    prompt = SCORE_PROMPT.format(
        min_years=jd.min_years_experience,
        domain=jd.domain,
        edu_req=jd.education_requirement,
        candidate_json=str(candidate_summary),
    )
    raw = CALL_LLM_HERE(prompt)
    llm_scores = safe_parse_json(raw)

    # Weighted total
    dims = {
        "skills_match": skills_score,
        "experience_relevance": llm_scores["experience_relevance"]["score"],
        "education_certs": llm_scores["education_certs"]["score"],
        "project_portfolio": portfolio_score,
        "communication_quality": llm_scores["communication_quality"]["score"],
    }
    total = sum(dims[k] * WEIGHTS[k] for k in dims)
    rec = "HIRE" if total >= 7.5 else ("MAYBE" if total >= 5.5 else "NO HIRE")

    return CandidateResult(
        name=candidate.name,
        skills_match=DimensionScore(
            score=skills_score,
            justification=f"Embedding similarity: {skills_sim:.0%} vs JD skills"
        ),
        experience_relevance=DimensionScore(**llm_scores["experience_relevance"]),
        education_certs=DimensionScore(**llm_scores["education_certs"]),
        project_portfolio=DimensionScore(
            score=portfolio_score,
            justification=f"Portfolio-JD similarity: {portfolio_sim:.0%}"
        ),
        communication_quality=DimensionScore(**llm_scores["communication_quality"]),
        weighted_total=round(total, 2),
        recommendation=rec,
    )