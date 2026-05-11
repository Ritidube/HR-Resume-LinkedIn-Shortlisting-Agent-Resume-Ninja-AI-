"""
override.py
───────────
Human-in-the-Loop score override system.

HR can call apply_override() to adjust any dimension score on a
CandidateResult.  Every change is logged to override_log.json so
there is a full audit trail.

Usage example (interactive CLI built into main.py):
    python main.py --override

Or call directly from your own code:
    from override import apply_override
    result = apply_override(result, "skills_match", new_score=8.5, reason="Verified on GitHub")
"""

import json
import os
from models import CandidateResult, DimensionScore, ScoreOverride

OVERRIDE_LOG = "override_log.json"

VALID_DIMENSIONS = [
    "skills_match",
    "experience_relevance",
    "education_certs",
    "project_portfolio",
    "communication_quality",
]

WEIGHTS = {
    "skills_match":          0.30,
    "experience_relevance":  0.25,
    "education_certs":       0.15,
    "project_portfolio":     0.20,
    "communication_quality": 0.10,
}


def _recalculate_total(result: CandidateResult) -> float:
    """Recompute weighted_total from current dimension scores."""
    dim_map = {
        "skills_match":          result.skills_match.score,
        "experience_relevance":  result.experience_relevance.score,
        "education_certs":       result.education_certs.score,
        "project_portfolio":     result.project_portfolio.score,
        "communication_quality": result.communication_quality.score,
    }
    return round(sum(dim_map[k] * WEIGHTS[k] for k in dim_map), 2)


def _recommendation(total: float) -> str:
    return "HIRE" if total >= 7.5 else ("MAYBE" if total >= 5.5 else "NO HIRE")


def _log_override(override: ScoreOverride) -> None:
    """Append the override record to override_log.json."""
    log: list[dict] = []
    if os.path.exists(OVERRIDE_LOG):
        with open(OVERRIDE_LOG, "r") as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []
    log.append(override.model_dump())
    with open(OVERRIDE_LOG, "w") as f:
        json.dump(log, f, indent=2)
    print(f"  [log] Override recorded → {OVERRIDE_LOG}")


def apply_override(
    result: CandidateResult,
    dimension: str,
    new_score: float,
    reason: str,
    overridden_by: str = "HR",
) -> CandidateResult:
    """
    Apply an HR override to one dimension of a CandidateResult.
    Returns the updated CandidateResult with recalculated total & recommendation.
    Logs the change to override_log.json.
    """
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"Unknown dimension '{dimension}'. Valid: {VALID_DIMENSIONS}")
    if not (0 <= new_score <= 10):
        raise ValueError("Score must be between 0 and 10.")

    # Get old score
    old_dim: DimensionScore = getattr(result, dimension)
    original_score = old_dim.score

    # Build new DimensionScore — keep justification, append override note
    new_justification = f"{old_dim.justification} [HR override: {reason}]"
    new_dim = DimensionScore(score=new_score, justification=new_justification)

    # Rebuild result with updated dimension
    updated_data = result.model_dump()
    updated_data[dimension] = {"score": new_score, "justification": new_justification}
    updated_result = CandidateResult(**updated_data)

    # Recalculate total & recommendation
    new_total = _recalculate_total(updated_result)
    updated_result.weighted_total = new_total
    updated_result.recommendation = _recommendation(new_total)

    # Log the change
    override = ScoreOverride(
        candidate_name=result.name,
        dimension=dimension,
        original_score=original_score,
        new_score=new_score,
        reason=reason,
        overridden_by=overridden_by,
    )
    _log_override(override)

    print(f"  ✓ {result.name} | {dimension}: {original_score} → {new_score} | total: {new_total} ({updated_result.recommendation})")
    return updated_result


def interactive_override(results: list[CandidateResult]) -> list[CandidateResult]:
    """
    CLI loop: lets HR review each candidate and optionally override scores.
    Called from main.py when --override flag is passed.
    """
    print("\n" + "═" * 60)
    print("  HUMAN-IN-THE-LOOP OVERRIDE MODE")
    print("  Press Enter to skip any prompt.")
    print("═" * 60)

    for i, result in enumerate(results):
        print(f"\n[{i+1}] {result.name}  |  Total: {result.weighted_total}  |  {result.recommendation}")
        print(f"     skills_match:         {result.skills_match.score:>4}  – {result.skills_match.justification[:60]}")
        print(f"     experience_relevance: {result.experience_relevance.score:>4}  – {result.experience_relevance.justification[:60]}")
        print(f"     education_certs:      {result.education_certs.score:>4}  – {result.education_certs.justification[:60]}")
        print(f"     project_portfolio:    {result.project_portfolio.score:>4}  – {result.project_portfolio.justification[:60]}")
        print(f"     communication_quality:{result.communication_quality.score:>4}  – {result.communication_quality.justification[:60]}")

        ans = input("\n  Override a score? (y/N): ").strip().lower()
        if ans != "y":
            continue

        print(f"  Dimensions: {', '.join(VALID_DIMENSIONS)}")
        dim = input("  Which dimension? ").strip()
        if dim not in VALID_DIMENSIONS:
            print("  Invalid dimension — skipping.")
            continue

        try:
            new_score = float(input("  New score (0–10): ").strip())
        except ValueError:
            print("  Invalid score — skipping.")
            continue

        reason = input("  Reason for override: ").strip() or "No reason provided"
        hr_name = input("  Your name (HR): ").strip() or "HR"

        results[i] = apply_override(result, dim, new_score, reason, hr_name)

    # Re-sort after any overrides
    results.sort(key=lambda r: r.weighted_total, reverse=True)
    print("\n  Override session complete. Results re-ranked.\n")
    return results