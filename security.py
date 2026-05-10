"""
security.py
───────────
One-shot LLM call that generates the "Security Risk Mitigation" section
for the project README.  Call generate_security_docs() once after your
pipeline is ready; the output is written to SECURITY.md.
"""

from llm_client import CALL_LLM_HERE

SECURITY_PROMPT = """\
I have built an HR Resume Shortlisting Agent in Python using LangChain and a \
cloud LLM (Groq / LLaMA-3). Risks I must cover: prompt injection, data \
privacy/PII, API key exposure, hallucination risk, unauthorized access.

Write a short, clear section for my README titled "Security Risk Mitigation" \
with 1–2 sentences per risk and specific mitigations using `.env`, structured \
outputs, input validation, and limited logging of PII.

Keep the total length under 250 words. Use plain Markdown with a level-2 heading \
and one sub-bullet per mitigation."""


def generate_security_docs(out_path: str = "SECURITY.md") -> str:
    """
    Calls the LLM once to produce a Security Risk Mitigation section and
    writes it to `out_path`.  Returns the generated text.
    """
    print("Generating security documentation (one LLM call)…")
    content = CALL_LLM_HERE(SECURITY_PROMPT)

    with open(out_path, "w") as f:
        f.write(content)

    print(f"Security docs saved → {out_path}")
    return content