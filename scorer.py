# import json
# from models import JDProfile, CandidateProfile, CandidateResult, DimensionScore
# from embeddings import skills_similarity, portfolio_similarity
# from parsers import safe_parse_json
# from llm_client import CALL_LLM_HERE

# WEIGHTS = {
#     "skills_match": 0.30,
#     "experience_relevance": 0.25,
#     "education_certs": 0.15,
#     "project_portfolio": 0.20,
#     "communication_quality": 0.10,
# }

# SCORE_PROMPT = """You are an HR evaluation engine. Score this candidate ONLY on these 3 dimensions.
# Return ONLY valid JSON — no markdown, no extra text:
# {{
#   "experience_relevance": {{"score": 0, "justification": "one line"}},
#   "education_certs":      {{"score": 0, "justification": "one line"}},
#   "communication_quality":{{"score": 0, "justification": "one line"}}
# }}

# RUBRIC:
# - experience_relevance: 0=unrelated, 5=adjacent domain, 10=exact domain+seniority (JD needs {min_years}yrs in {domain})
# - education_certs: 0=does not meet minimum, 5=meets, 10=exceeds+extra certs (JD requires: {edu_req})
# - communication_quality: judge clarity and structure of resume text itself

# CANDIDATE PROFILE:
# {candidate_json}
# """

# def score_candidate(jd: JDProfile, candidate: CandidateProfile) -> CandidateResult:
#     # Embedding-based scores
#     skills_sim = skills_similarity(jd, candidate)
#     portfolio_sim = portfolio_similarity(jd, candidate)
#     skills_score = round(skills_sim * 10, 1)
#     portfolio_score = round(portfolio_sim * 10, 1)

#     # LLM-based scores (3 dims in one call)
#     candidate_summary = candidate.model_dump(exclude={"raw_text"})
#     prompt = SCORE_PROMPT.format(
#         min_years=jd.min_years_experience,
#         domain=jd.domain,
#         edu_req=jd.education_requirement,
#         candidate_json=str(candidate_summary),
#     )
#     raw = CALL_LLM_HERE(prompt)
#     llm_scores = safe_parse_json(raw)

#     # Weighted total
#     dims = {
#         "skills_match": skills_score,
#         "experience_relevance": llm_scores["experience_relevance"]["score"],
#         "education_certs": llm_scores["education_certs"]["score"],
#         "project_portfolio": portfolio_score,
#         "communication_quality": llm_scores["communication_quality"]["score"],
#     }
#     total = sum(dims[k] * WEIGHTS[k] for k in dims)
#     rec = "HIRE" if total >= 7.5 else ("MAYBE" if total >= 5.5 else "NO HIRE")

#     return CandidateResult(
#         name=candidate.name,
#         skills_match=DimensionScore(
#             score=skills_score,
#             justification=f"Embedding similarity: {skills_sim:.0%} vs JD skills"
#         ),
#         experience_relevance=DimensionScore(**llm_scores["experience_relevance"]),
#         education_certs=DimensionScore(**llm_scores["education_certs"]),
#         project_portfolio=DimensionScore(
#             score=portfolio_score,
#             justification=f"Portfolio-JD similarity: {portfolio_sim:.0%}"
#         ),
#         communication_quality=DimensionScore(**llm_scores["communication_quality"]),
#         weighted_total=round(total, 2),
#         recommendation=rec,
#     )
import json
from models import JDProfile, CandidateProfile, CandidateResult, DimensionScore
from embeddings import skills_similarity, portfolio_similarity
from parsers import safe_parse_json
from llm_client import CALL_LLM_HERE

WEIGHTS = {
    "skills_match":          0.30,
    "experience_relevance":  0.25,
    "education_certs":       0.15,
    "project_portfolio":     0.20,
    "communication_quality": 0.10,
}

# ── Full 5-dimension scoring prompt (one LLM call) ────────────────────────────
# The JD and candidate objects are passed as compact JSON so the prompt stays
# small and cheap.  All 5 dimensions are scored in a single round-trip.

SCORE_PROMPT = """\
You are an HR evaluation assistant. Given a JD object and a candidate object, \
score the candidate on ALL 5 dimensions below.

RUBRIC:
- skills_match (0–10): overlap between candidate skills and required/nice-to-have skills
- experience_relevance (0–10): 0=unrelated domain, 5=adjacent, 10=exact domain+seniority \
(JD needs {min_years} yrs in {domain})
- education_and_certs (0–10): 0=does not meet minimum, 5=meets, 10=exceeds+extra certs \
(JD requires: {edu_req})
- project_portfolio (0–10): relevance of candidate projects to JD responsibilities
- communication_quality (0–10): clarity and structure of the resume text itself

WEIGHTS (for your reference, do NOT compute weighted_total yourself — just score each dim):
- skills_match 30%  |  experience_relevance 25%  |  education_and_certs 15%
- project_portfolio 20%  |  communication_quality 10%

For each dimension add a ONE-LINE justification.
Return STRICTLY this JSON shape, no markdown, no extra keys:
{{
  "skills_match":          {{"score": 0, "justification": ""}},
  "experience_relevance":  {{"score": 0, "justification": ""}},
  "education_and_certs":   {{"score": 0, "justification": ""}},
  "project_portfolio":     {{"score": 0, "justification": ""}},
  "communication_quality": {{"score": 0, "justification": ""}}
}}

JD JSON:
{jd_json}

Candidate JSON:
{candidate_json}"""


def _build_jd_summary(jd: JDProfile) -> dict:
    """Compact JD dict sent to scorer — only fields the LLM needs."""
    return {
        "role_title": jd.title,
        "required_skills": jd.required_skills,
        "nice_to_have_skills": jd.preferred_skills,
        "min_experience_years": jd.min_years_experience,
        "domain": jd.domain,
        "education_required": jd.education_requirement,
        "key_responsibilities": jd.key_responsibilities,
    }


def _build_candidate_summary(candidate: CandidateProfile) -> dict:
    """Compact candidate dict sent to scorer — excludes raw_text (PII / tokens)."""
    return {
        "name": candidate.name,
        "current_role": candidate.current_role,
        "total_experience_years": candidate.years_experience,
        "skills": candidate.skills,
        "domains": candidate.domains or candidate.domain_history,
        "education": candidate.education,
        "projects": candidate.projects[:5],   # cap at 5 to save tokens
    }


def score_candidate(jd: JDProfile, candidate: CandidateProfile) -> CandidateResult:
    # ── Embedding-based scores (fast, no LLM call) ────────────────────────────
    skills_sim    = skills_similarity(jd, candidate)
    portfolio_sim = portfolio_similarity(jd, candidate)
    skills_score    = round(skills_sim * 10, 1)
    portfolio_score = round(portfolio_sim * 10, 1)

    # ── LLM-based scores — all 5 dims in ONE call ─────────────────────────────
    jd_json        = json.dumps(_build_jd_summary(jd),        separators=(",", ":"))
    candidate_json = json.dumps(_build_candidate_summary(candidate), separators=(",", ":"))

    prompt = SCORE_PROMPT.format(
        min_years     = jd.min_years_experience,
        domain        = jd.domain,
        edu_req       = jd.education_requirement,
        jd_json       = jd_json,
        candidate_json= candidate_json,
    )
    raw       = CALL_LLM_HERE(prompt)
    llm_scores = safe_parse_json(raw)

    # ── Merge: prefer embedding scores for skills/portfolio, LLM for the rest ──
    # (Embedding scores are already computed above; we take LLM's skills/portfolio
    #  scores only as a fallback if embeddings returned 0.)
    final_skills_score    = skills_score    or llm_scores["skills_match"]["score"]
    final_portfolio_score = portfolio_score or llm_scores["project_portfolio"]["score"]

    dims = {
        "skills_match":         final_skills_score,
        "experience_relevance": llm_scores["experience_relevance"]["score"],
        "education_certs":      llm_scores["education_and_certs"]["score"],
        "project_portfolio":    final_portfolio_score,
        "communication_quality":llm_scores["communication_quality"]["score"],
    }
    total = round(sum(dims[k] * WEIGHTS[k] for k in dims), 2)
    rec   = "HIRE" if total >= 7.5 else ("MAYBE" if total >= 5.5 else "NO HIRE")

    return CandidateResult(
        name=candidate.name,
        skills_match=DimensionScore(
            score=final_skills_score,
            justification=llm_scores["skills_match"]["justification"]
            or f"Embedding similarity: {skills_sim:.0%} vs JD skills",
        ),
        experience_relevance=DimensionScore(**llm_scores["experience_relevance"]),
        education_certs=DimensionScore(**llm_scores["education_and_certs"]),
        project_portfolio=DimensionScore(
            score=final_portfolio_score,
            justification=llm_scores["project_portfolio"]["justification"]
            or f"Portfolio-JD similarity: {portfolio_sim:.0%}",
        ),
        communication_quality=DimensionScore(**llm_scores["communication_quality"]),
        weighted_total=total,
        recommendation=rec,
    )