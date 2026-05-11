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

SCORE_PROMPT = """\
You are a senior HR evaluation assistant. Score this candidate against the JD on ALL 5 dimensions.

STRICT RUBRIC — follow these anchors exactly:

skills_match (0–10):
  0 = < 30% skills match
  5 = 50–70% skills match
  10 = > 85% skills match (also count related/transferable skills)

experience_relevance (0–10):
  IMPORTANT — internships, freelance, and project-based work COUNT as real experience.
  A student with strong internships in the right domain should score 4–6, not 0.
  0  = completely unrelated domain, no relevant work at all
  3  = some adjacent work or strong personal projects but no internships
  5  = internship(s) in adjacent domain OR solid project experience in exact domain
  7  = internship(s) in exact domain, slightly below required years
  10 = exact domain + full seniority (JD needs {min_years} yrs in {domain})

education_and_certs (0–10):
  0  = does not meet minimum
  5  = meets minimum requirement exactly
  8  = meets minimum + relevant certifications
  10 = exceeds minimum + multiple strong certifications
  (JD requires: {edu_req})
  Note: A B.Tech/B.E. in CS from a reputed university IS a strong education match.
  Certifications from DeepLearning.AI, Google, AWS, IBM should boost this score.

project_portfolio (0–10):
  0  = no evidence of projects
  3  = 1–2 generic or unrelated projects
  6  = 2–3 relevant projects with decent complexity
  8  = strong relevant portfolio — deployed apps, ML pipelines, real-world use cases
  10 = exceptional portfolio directly matching JD responsibilities
  Note: Count deployed projects, GitHub activity, and real-world complexity.

communication_quality (0–10):
  0  = poor grammar, unstructured
  5  = adequate clarity
  10 = crisp, structured, impactful — clear summaries, quantified achievements

Be FAIR and ACCURATE. Do not penalise candidates for being early-career if their
skills and projects are genuinely strong. Justify each score in one specific line
referencing actual candidate details — never write generic justifications.

Return STRICTLY this JSON, no markdown, no extra keys:
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
    """
    Rich candidate summary — includes certifications, current role, domains,
    and structured project details so the LLM can score accurately.
    Excludes raw_text to avoid PII leakage and token bloat.
    """
    # Build structured project list: prefer rich project_entries, fall back to flat
    if candidate.project_entries:
        projects = [
            {"title": p.title, "summary": p.summary}
            for p in candidate.project_entries[:5]
        ]
    else:
        projects = candidate.projects[:5]

    # Build structured education list
    if candidate.education_entries:
        education = [
            {
                "degree": e.degree,
                "field": e.field,
                "institution": e.institution,
            }
            for e in candidate.education_entries
        ]
    else:
        education = candidate.education

    return {
        "name": candidate.name,
        "current_role": candidate.current_role,
        "total_experience_years": candidate.years_experience,
        "skills": candidate.skills,
        "certifications": candidate.certifications,   # ← was missing before
        "domains": candidate.domains or candidate.domain_history,
        "education": education,                        # ← structured now
        "projects": projects,                          # ← structured now
        "linkedin_summary": candidate.linkedin_extra,  # ← bonus context if present
    }


def score_candidate(jd: JDProfile, candidate: CandidateProfile) -> CandidateResult:
    # ── Embedding-based scores ────────────────────────────────────────────────
    skills_sim    = skills_similarity(jd, candidate)
    portfolio_sim = portfolio_similarity(jd, candidate)
    embedding_skills_score    = round(skills_sim * 10, 1)
    embedding_portfolio_score = round(portfolio_sim * 10, 1)

    # ── LLM scores — all 5 dims in one call ──────────────────────────────────
    jd_json        = json.dumps(_build_jd_summary(jd), separators=(",", ":"))
    candidate_json = json.dumps(_build_candidate_summary(candidate), separators=(",", ":"))

    prompt = SCORE_PROMPT.format(
        min_years      = jd.min_years_experience,
        domain         = jd.domain,
        edu_req        = jd.education_requirement,
        jd_json        = jd_json,
        candidate_json = candidate_json,
    )
    raw        = CALL_LLM_HERE(prompt)
    llm_scores = safe_parse_json(raw)

    # ── Merge strategy ────────────────────────────────────────────────────────
    # For skills: average embedding + LLM so neither dominates alone.
    # For portfolio: same averaging — embedding catches semantic similarity,
    #   LLM catches real-world complexity and deployment evidence.
    # For experience/education/communication: LLM only (needs reasoning).
    llm_skills_score    = llm_scores["skills_match"]["score"]
    llm_portfolio_score = llm_scores["project_portfolio"]["score"]

    # Average embedding and LLM scores (both on 0–10 scale)
    final_skills_score    = round((embedding_skills_score + llm_skills_score) / 2, 1)
    final_portfolio_score = round((embedding_portfolio_score + llm_portfolio_score) / 2, 1)

    dims = {
        "skills_match":          final_skills_score,
        "experience_relevance":  llm_scores["experience_relevance"]["score"],
        "education_certs":       llm_scores["education_and_certs"]["score"],
        "project_portfolio":     final_portfolio_score,
        "communication_quality": llm_scores["communication_quality"]["score"],
    }
    total = round(sum(dims[k] * WEIGHTS[k] for k in dims), 2)
    rec   = "HIRE" if total >= 7.5 else ("MAYBE" if total >= 5.5 else "NO HIRE")

    # Build justification strings — combine embedding insight with LLM reasoning
    skills_just = (
        f"{llm_scores['skills_match']['justification']} "
        f"(embedding similarity: {skills_sim:.0%})"
    )
    portfolio_just = (
        f"{llm_scores['project_portfolio']['justification']} "
        f"(semantic similarity: {portfolio_sim:.0%})"
    )

    return CandidateResult(
        name=candidate.name,
        skills_match=DimensionScore(
            score=final_skills_score,
            justification=skills_just,
        ),
        experience_relevance=DimensionScore(**llm_scores["experience_relevance"]),
        education_certs=DimensionScore(**llm_scores["education_and_certs"]),
        project_portfolio=DimensionScore(
            score=final_portfolio_score,
            justification=portfolio_just,
        ),
        communication_quality=DimensionScore(**llm_scores["communication_quality"]),
        weighted_total=total,
        recommendation=rec,
    )