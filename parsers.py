# import fitz  # PyMuPDF
# import docx
# import json
# import re
# from models import JDProfile, CandidateProfile
# from llm_client import CALL_LLM_HERE

# def extract_text(file_path: str) -> str:
#     if file_path.endswith(".pdf"):
#         doc = fitz.open(file_path)
#         return "\n".join(page.get_text() for page in doc)
#     elif file_path.endswith(".docx"):
#         d = docx.Document(file_path)
#         return "\n".join(p.text for p in d.paragraphs)
#     raise ValueError(f"Unsupported format: {file_path}")

# def safe_parse_json(raw: str) -> dict:
#     cleaned = re.sub(r"```json|```", "", raw).strip()
#     return json.loads(cleaned)

# JD_PARSE_PROMPT = """Extract a structured JD profile from the text below.
# Return ONLY valid JSON matching this schema exactly — no markdown, no explanation:
# {{
#   "title": "...",
#   "required_skills": [],
#   "preferred_skills": [],
#   "min_years_experience": 0,
#   "domain": "...",
#   "education_requirement": "...",
#   "key_responsibilities": []
# }}
# JD TEXT:
# {jd_text}"""

# RESUME_PARSE_PROMPT = """Extract a candidate profile from the resume below.
# Return ONLY valid JSON — no markdown, no extra text:
# {{
#   "name": "...",
#   "skills": [],
#   "years_experience": 0.0,
#   "domain_history": [],
#   "education": "...",
#   "certifications": [],
#   "projects": []
# }}
# RESUME TEXT:
# {resume_text}"""

# def parse_jd(jd_text: str) -> JDProfile:
#     prompt = JD_PARSE_PROMPT.format(jd_text=jd_text[:4000])
#     raw = CALL_LLM_HERE(prompt)
#     return JDProfile.model_validate(safe_parse_json(raw))

# def parse_resume(resume_text: str) -> CandidateProfile:
#     prompt = RESUME_PARSE_PROMPT.format(resume_text=resume_text[:4000])
#     raw = CALL_LLM_HERE(prompt)
#     data = CandidateProfile.model_validate(safe_parse_json(raw))
#     data.raw_text = resume_text
#     return data

import fitz       # PyMuPDF
import docx
import json
import re
from models import JDProfile, CandidateProfile, EducationEntry, ProjectEntry
from llm_client import CALL_LLM_HERE

# ── Security: input sanitisation ─────────────────────────────────────────────
_INJECTION_PATTERNS = re.compile(
    r"(ignore (all |previous |above )?(instructions?|prompts?|rules?)"
    r"|you are now|disregard|forget (everything|all)|system\s*:|<\s*/?system\s*>)",
    re.IGNORECASE,
)

def sanitise_input(text: str, max_chars: int = 4000) -> str:
    text = text[:max_chars]
    text = _INJECTION_PATTERNS.sub("[REDACTED]", text)
    return text


# ── File extraction ───────────────────────────────────────────────────────────

def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join(page.get_text() for page in doc)
    elif file_path.endswith(".docx"):
        d = docx.Document(file_path)
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"Unsupported format: {file_path}")


# ── LinkedIn JSON ingestion ───────────────────────────────────────────────────
# Accepts a manually exported LinkedIn JSON (from linkedin.com/in/<>/detail/export)
# OR a dict with keys: summary, headline, skills, experience, education, projects

LINKEDIN_PARSE_PROMPT = """\
I will give you a LinkedIn profile exported as JSON. Extract a concise JSON object with these fields:
- "name"
- "email" (null if not present)
- "headline" (current role/title string)
- "total_experience_years" (number, approximate from positions)
- "skills" (list of skill strings)
- "education" (list of objects with "degree", "field", "institution")
- "projects" (list of up to 5 objects with "title" and "summary")
- "domains" (list of domain strings like "fintech", "saas", "edtech")
- "summary" (the About/summary section, max 300 chars)

Output ONLY valid JSON, no extra text. If a field is missing use null or empty list.

LinkedIn JSON:
{linkedin_json}"""

def parse_linkedin_json(linkedin_path: str) -> CandidateProfile:
    """
    Parse a LinkedIn exported JSON file into a CandidateProfile.
    The JSON file is the raw export you download from LinkedIn Settings →
    Data Privacy → Get a copy of your data → select Profile.
    """
    with open(linkedin_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    safe_text = sanitise_input(raw_json, max_chars=5000)
    prompt = LINKEDIN_PARSE_PROMPT.format(linkedin_json=safe_text)
    raw = CALL_LLM_HERE(prompt)
    data = safe_parse_json(raw)

    edu_entries = _parse_education(data.get("education", []))
    proj_entries, flat_projects = _parse_projects(data.get("projects", []))
    flat_edu = _flat_edu(edu_entries)

    return CandidateProfile(
        name=data.get("name", "Unknown"),
        email=data.get("email"),
        current_role=data.get("headline"),
        skills=data.get("skills", []),
        years_experience=float(data.get("total_experience_years") or 0),
        domain_history=data.get("domains", []),
        domains=data.get("domains", []),
        education=flat_edu,
        education_entries=edu_entries,
        projects=flat_projects,
        project_entries=proj_entries,
        certifications=[],
        linkedin_extra=data.get("summary"),
        raw_text=raw_json[:2000],   # keep for communication_quality scoring
    )


# ── Safe JSON parsing ─────────────────────────────────────────────────────────

def safe_parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    return json.loads(cleaned)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _parse_education(edu_list: list) -> list[EducationEntry]:
    entries = []
    for e in edu_list or []:
        if isinstance(e, dict):
            entries.append(EducationEntry(
                degree=e.get("degree", ""),
                field=e.get("field", ""),
                institution=e.get("institution", ""),
            ))
    return entries

def _parse_projects(proj_list: list):
    proj_entries, flat = [], []
    for p in proj_list or []:
        if isinstance(p, dict):
            pe = ProjectEntry(title=p.get("title", ""), summary=p.get("summary", ""))
            proj_entries.append(pe)
            flat.append(f"{pe.title}: {pe.summary}")
        elif isinstance(p, str):
            flat.append(p)
    return proj_entries, flat

def _flat_edu(entries: list[EducationEntry]) -> str:
    return "; ".join(
        f"{e.degree} in {e.field} from {e.institution}" for e in entries
    )


# ── JD & Resume prompts ───────────────────────────────────────────────────────

JD_PARSE_PROMPT = """\
I will give you a job description text. Extract a concise JSON object with exactly these fields:
- "role_title" (string)
- "required_skills" (list of 5-15 key skills)
- "nice_to_have_skills" (list)
- "min_experience_years" (number, estimate if not explicit)
- "education_required" (short string)
- "domain" (e.g. "fintech", "e-commerce", "SaaS")
- "key_responsibilities" (list of up to 8 bullet strings)

Output ONLY valid minified JSON, no explanations, no markdown.

Job description:
{jd_text}"""

RESUME_PARSE_PROMPT = """\
I will give you the full text of a candidate resume. Extract a concise JSON object with these fields:
- "name"
- "email"
- "linkedin_url" (extract if present, else null)
- "total_experience_years" (number, approximate)
- "current_role"
- "skills" (list of skills/technologies)
- "education" (list of objects with "degree", "field", "institution")
- "projects" (list of up to 5 objects with "title" and "summary")
- "domains" (list of domains like "fintech", "edtech", "healthcare")

Output ONLY valid JSON, no extra text. If something is missing use null or empty list.

Resume text:
{resume_text}"""


def parse_jd(jd_text: str) -> JDProfile:
    safe_text = sanitise_input(jd_text, max_chars=4000)
    prompt = JD_PARSE_PROMPT.format(jd_text=safe_text)
    raw = CALL_LLM_HERE(prompt)
    data = safe_parse_json(raw)
    return JDProfile(
        title=data.get("role_title", ""),
        role_title=data.get("role_title", ""),
        required_skills=data.get("required_skills", []),
        preferred_skills=data.get("nice_to_have_skills", []),
        nice_to_have_skills=data.get("nice_to_have_skills", []),
        min_years_experience=int(data.get("min_experience_years", 0)),
        domain=data.get("domain", ""),
        education_requirement=data.get("education_required", ""),
        key_responsibilities=data.get("key_responsibilities", []),
    )


def parse_resume(resume_text: str) -> CandidateProfile:
    safe_text = sanitise_input(resume_text, max_chars=4000)
    prompt = RESUME_PARSE_PROMPT.format(resume_text=safe_text)
    raw = CALL_LLM_HERE(prompt)
    data = safe_parse_json(raw)

    edu_entries = _parse_education(data.get("education", []))
    proj_entries, flat_projects = _parse_projects(data.get("projects", []))
    flat_edu = _flat_edu(edu_entries) if edu_entries else str(data.get("education", ""))

    return CandidateProfile(
        name=data.get("name", "Unknown"),
        email=data.get("email"),
        linkedin_url=data.get("linkedin_url"),
        current_role=data.get("current_role"),
        skills=data.get("skills", []),
        years_experience=float(data.get("total_experience_years") or 0),
        domain_history=data.get("domains", []),
        domains=data.get("domains", []),
        education=flat_edu,
        education_entries=edu_entries,
        projects=flat_projects,
        project_entries=proj_entries,
        certifications=[],
        raw_text=resume_text,
    )