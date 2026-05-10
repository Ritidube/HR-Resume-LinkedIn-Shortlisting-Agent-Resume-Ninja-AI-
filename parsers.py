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



import fitz  # PyMuPDF
import docx
import json
import re
from models import JDProfile, CandidateProfile
from llm_client import CALL_LLM_HERE


def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join(page.get_text() for page in doc)
    elif file_path.endswith(".docx"):
        d = docx.Document(file_path)
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"Unsupported format: {file_path}")


def safe_parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    return json.loads(cleaned)


JD_PARSE_PROMPT = """Extract a structured JD profile from the text below.
Return ONLY valid JSON matching this schema exactly — no markdown, no explanation:
{{
  "title": "...",
  "required_skills": [],
  "preferred_skills": [],
  "min_years_experience": 0,
  "domain": "...",
  "education_requirement": "...",
  "key_responsibilities": []
}}
JD TEXT:
{jd_text}"""

RESUME_PARSE_PROMPT = """Extract a candidate profile from the resume below.
Return ONLY valid JSON — no markdown, no extra text:
{{
  "name": "...",
  "skills": [],
  "years_experience": 0.0,
  "domain_history": [],
  "education": "...",
  "certifications": [],
  "projects": []
}}
RESUME TEXT:
{resume_text}"""


def parse_jd(jd_text: str) -> JDProfile:
    prompt = JD_PARSE_PROMPT.format(jd_text=jd_text[:4000])
    raw = CALL_LLM_HERE(prompt)
    return JDProfile.model_validate(safe_parse_json(raw))


def parse_resume(resume_text: str) -> CandidateProfile:
    prompt = RESUME_PARSE_PROMPT.format(resume_text=resume_text[:4000])
    raw = CALL_LLM_HERE(prompt)
    data = CandidateProfile.model_validate(safe_parse_json(raw))
    data.raw_text = resume_text
    return data