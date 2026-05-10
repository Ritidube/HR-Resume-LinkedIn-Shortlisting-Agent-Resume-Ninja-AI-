from sentence_transformers import SentenceTransformer
from models import JDProfile, CandidateProfile
import numpy as np

_model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def cosine(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def skills_similarity(jd: JDProfile, candidate: CandidateProfile) -> float:
    jd_text = " ".join(jd.required_skills + jd.preferred_skills)
    cand_text = " ".join(candidate.skills)
    if not cand_text.strip() or not jd_text.strip():
        return 0.0
    vecs = _model.encode([jd_text, cand_text])
    return cosine(vecs[0], vecs[1])

def portfolio_similarity(jd: JDProfile, candidate: CandidateProfile) -> float:
    jd_text = " ".join(jd.key_responsibilities)
    cand_text = " ".join(candidate.projects)
    if not cand_text.strip() or not jd_text.strip():
        return 0.0
    vecs = _model.encode([jd_text, cand_text])
    return cosine(vecs[0], vecs[1])