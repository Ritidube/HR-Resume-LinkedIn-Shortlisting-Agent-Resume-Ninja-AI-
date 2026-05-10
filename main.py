# from dotenv import load_dotenv
# load_dotenv()

# import json
# from parsers import extract_text, parse_jd, parse_resume
# from scorer import score_candidate
# from models import CandidateResult

# def run_pipeline(jd_path: str, resume_paths: list[str]) -> list[CandidateResult]:
#     print("Parsing JD...")
#     jd_text = extract_text(jd_path)
#     jd = parse_jd(jd_text)
#     print(f"JD parsed: {jd.title} | Domain: {jd.domain}")

#     results = []
#     for path in resume_paths:
#         print(f"Processing: {path}")
#         text = extract_text(path)
#         candidate = parse_resume(text)
#         result = score_candidate(jd, candidate)
#         print(f"  → {candidate.name}: {result.weighted_total} ({result.recommendation})")
#         results.append(result)

#     results.sort(key=lambda r: r.weighted_total, reverse=True)
#     return results

# def export_report(results: list[CandidateResult], out_path="report.json"):
#     with open(out_path, "w") as f:
#         json.dump([r.model_dump() for r in results], f, indent=2)
#     print(f"\nReport saved → {out_path}")

# if __name__ == "__main__":
#     try:
#         results = run_pipeline(
#             jd_path="data/jd.pdf",
#             resume_paths=[
#                 "data/resume/candidate1.pdf",
#                 "data/resume/candidate2.docx",
#             ]
#         )
#         export_report(results)
#     except Exception as e:
#         import traceback
#         traceback.print_exc()


from dotenv import load_dotenv
load_dotenv()

import json
from parsers import extract_text, parse_jd, parse_resume
from scorer import score_candidate
from models import CandidateResult
from security import generate_security_docs


def run_pipeline(jd_path: str, resume_paths: list[str]) -> list[CandidateResult]:
    print("Parsing JD…")
    jd_text = extract_text(jd_path)
    jd = parse_jd(jd_text)
    print(f"JD parsed: {jd.title} | Domain: {jd.domain}")

    results = []
    for path in resume_paths:
        print(f"Processing: {path}")
        text = extract_text(path)
        candidate = parse_resume(text)
        result = score_candidate(jd, candidate)
        print(f"  → {candidate.name}: {result.weighted_total} ({result.recommendation})")
        results.append(result)

    results.sort(key=lambda r: r.weighted_total, reverse=True)
    return results


def export_report(results: list[CandidateResult], out_path: str = "report.json") -> None:
    with open(out_path, "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    print(f"\nReport saved → {out_path}")


if __name__ == "__main__":
    try:
        results = run_pipeline(
            jd_path="data/jd.pdf",
            resume_paths=[
                "data/resume/candidate1.pdf",
                "data/resume/candidate2.docx",
            ],
        )
        export_report(results)

        # Generate security documentation once (cheap single LLM call)
        generate_security_docs("SECURITY.md")

    except Exception:
        import traceback
        traceback.print_exc()