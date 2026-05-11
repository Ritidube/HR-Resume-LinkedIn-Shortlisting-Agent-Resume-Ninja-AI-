"""
llm_client.py
─────────────
LangChain wrapper around Groq LLaMA-3.3-70B.

Uses only langchain-groq and langchain-core — no langchain base package needed.
Response caching is handled via a simple file-based cache to avoid the
langchain-community SQLiteCache version conflict.
"""

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import logging, os, re, json, hashlib

load_dotenv()

# ── Simple file-based LLM cache (replaces SQLiteCache) ───────────────────────
# Avoids langchain version conflicts entirely.
_CACHE_FILE = ".llm_cache.json"

def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict) -> None:
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass

# ── PII-safe logger ───────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")

class PIISafeFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        msg = _EMAIL_RE.sub("[EMAIL]", msg)
        msg = _PHONE_RE.sub("[PHONE]", msg)
        return msg

_handler = logging.StreamHandler()
_handler.setFormatter(PIISafeFormatter("%(asctime)s %(levelname)s %(message)s"))
logger = logging.getLogger("hr_agent")
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# ── LLM ──────────────────────────────────────────────────────────────────────
llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0,
)

_SYSTEM_GUARDRAIL = """You are a precise HR evaluation assistant.
Rules you MUST follow on every response:
1. Return ONLY valid JSON — no markdown fences, no preamble, no explanation.
2. Never invent candidate data not present in the input.
3. Scores must be numbers between 0 and 10.
4. If information is missing, use null or empty list — never fabricate."""


def CALL_LLM_HERE(prompt: str) -> str:
    """
    Single LLM entry point with file-based caching and PII-safe logging.
    Applies system guardrail on every call.
    """
    # Cache key = hash of prompt
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    cache = _load_cache()
    if cache_key in cache:
        logger.info(f"LLM cache hit | prompt_chars={len(prompt)}")
        return cache[cache_key]

    logger.info(f"LLM call | prompt_chars={len(prompt)}")
    messages = [
        SystemMessage(content=_SYSTEM_GUARDRAIL),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    result = response.content
    logger.info(f"LLM response | response_chars={len(result)}")

    # Cache the result
    cache[cache_key] = result
    _save_cache(cache)
    return result