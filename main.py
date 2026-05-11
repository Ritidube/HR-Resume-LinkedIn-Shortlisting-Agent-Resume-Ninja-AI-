"""
main.py
───────
Entry point for the HR Resume Shortlisting Agent.

Usage:
    python main.py                     # normal run
    python main.py --override          # run + interactive HR override session
    python main.py --linkedin path.json  # add one LinkedIn profile to the batch
    python main.py --security-docs     # regenerate SECURITY.md only
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
from parsers import extract_text, parse_jd, parse_resume, parse_linkedin_json
from scorer import score_candidate
from models import CandidateResult
from override import interactive_override
from report_generator import generate_html_report
from security import generate_security_docs


def run_pipeline(
    jd_path: str,
    resume_paths: list[str],
    linkedin_paths: list[str] | None = None,
) -> list[CandidateResult]:
    print("\n── Parsing JD ──────────────────────────────────────────")
    jd_text = extract_text(jd_path)
    jd = parse_jd(jd_text)
    print(f"  Role : {jd.title}")
    print(f"  Domain: {jd.domain}  |  Min exp: {jd.min_years_experience} yrs")

    results: list[CandidateResult] = []

    # ── Resumes ──────────────────────────────────────────────────
    print("\n── Processing Resumes ──────────────────────────────────")
    for path in resume_paths:
        print(f"  {path}")
        text = extract_text(path)
        candidate = parse_resume(text)
        # If LinkedIn URL found in resume and a matching JSON file was supplied, merge it
        result = score_candidate(jd, candidate)
        print(f"  → {candidate.name}: {result.weighted_total} ({result.recommendation})")
        results.append(result)

    # ── LinkedIn JSON profiles (optional) ────────────────────────
    if linkedin_paths:
        print("\n── Processing LinkedIn Profiles ────────────────────────")
        for path in linkedin_paths:
            print(f"  {path}")
            candidate = parse_linkedin_json(path)
            result = score_candidate(jd, candidate)
            print(f"  → {candidate.name}: {result.weighted_total} ({result.recommendation})")
            results.append(result)

    results.sort(key=lambda r: r.weighted_total, reverse=True)
    return results


def export_json(results: list[CandidateResult], out_path: str = "report.json") -> None:
    with open(out_path, "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    print(f"\nJSON report  → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="HR Resume Shortlisting Agent")
    parser.add_argument("--override",      action="store_true", help="Interactive HR override session after scoring")
    parser.add_argument("--linkedin",      nargs="*", default=[], metavar="JSON", help="LinkedIn exported JSON file(s)")
    parser.add_argument("--security-docs", action="store_true", help="Regenerate SECURITY.md and exit")
    args = parser.parse_args()

    if args.security_docs:
        generate_security_docs("SECURITY.md")
        return

    try:
        results = run_pipeline(
            jd_path="data/jd.pdf",
            resume_paths=[
                "data/resume/candidate1.pdf",
                "data/resume/candidate2.docx",
                "data/resume/Riti__Dubey_Resume.pdf",
            ],
            linkedin_paths=args.linkedin or [],
        )

        # ── Human-in-the-Loop override ────────────────────────
        if args.override:
            results = interactive_override(results)

        # ── Export both formats ───────────────────────────────
        export_json(results)
        generate_html_report(results, "shortlist_report.html")

        # ── Security docs (generated once) ───────────────────
        generate_security_docs("SECURITY.md")

        print("\n── Done ─────────────────────────────────────────────────")
        print("  report.json          (machine-readable)")
        print("  shortlist_report.html (open in browser)")
        print("  SECURITY.md          (README security section)")
        if args.override:
            print("  override_log.json    (HR audit trail)")

    except Exception:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()