"""
report_generator.py
───────────────────
Generates a formatted HTML shortlist report from CandidateResult objects.
Opens cleanly in any browser; no extra dependencies beyond jinja2.

Output: shortlist_report.html
"""

from jinja2 import Template
from models import CandidateResult
from datetime import datetime

# ── Jinja2 HTML template ──────────────────────────────────────────────────────
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HR Shortlist Report</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; color: #333; }
  header { background: #1a3c5e; color: white; padding: 28px 40px; }
  header h1 { font-size: 1.7rem; font-weight: 700; }
  header p  { margin-top: 4px; font-size: 0.88rem; opacity: 0.75; }
  .container { max-width: 1100px; margin: 30px auto; padding: 0 20px; }

  /* Summary bar */
  .summary { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
  .summary-card { background: white; border-radius: 8px; padding: 16px 22px;
                  flex: 1; min-width: 140px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  .summary-card .num { font-size: 2rem; font-weight: 700; color: #1a3c5e; }
  .summary-card .lbl { font-size: 0.78rem; color: #888; margin-top: 2px; }

  /* Candidate cards */
  .card { background: white; border-radius: 10px; margin-bottom: 22px;
          box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }
  .card-header { display: flex; align-items: center; justify-content: space-between;
                 padding: 18px 24px; border-bottom: 1px solid #eee; }
  .rank { font-size: 1.4rem; font-weight: 800; color: #1a3c5e; min-width: 36px; }
  .name { font-size: 1.15rem; font-weight: 600; flex: 1; padding: 0 14px; }
  .meta { font-size: 0.82rem; color: #666; }
  .badge { padding: 5px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700;
           text-transform: uppercase; letter-spacing: .5px; }
  .HIRE    { background: #d4edda; color: #155724; }
  .MAYBE   { background: #fff3cd; color: #856404; }
  .NO-HIRE { background: #f8d7da; color: #721c24; }

  .card-body { padding: 20px 24px; }

  /* Score bar */
  .total-row { display: flex; align-items: center; margin-bottom: 18px; gap: 14px; }
  .total-label { font-size: 0.82rem; color: #888; width: 110px; }
  .total-bar-wrap { flex: 1; background: #eee; border-radius: 6px; height: 14px; overflow: hidden; }
  .total-bar { height: 14px; border-radius: 6px; background: linear-gradient(90deg,#1a3c5e,#3b82c4); }
  .total-num { font-size: 1.1rem; font-weight: 700; color: #1a3c5e; width: 40px; text-align: right; }

  /* Dimensions table */
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { background: #f0f4f8; text-align: left; padding: 8px 10px; font-weight: 600;
       font-size: 0.78rem; text-transform: uppercase; color: #555; }
  td { padding: 9px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  .dim-name { font-weight: 600; white-space: nowrap; }
  .dim-score { text-align: center; font-weight: 700; border-radius: 4px; padding: 2px 8px;
               white-space: nowrap; }
  .score-high { background: #d4edda; color: #155724; }
  .score-mid  { background: #fff3cd; color: #856404; }
  .score-low  { background: #f8d7da; color: #721c24; }
  .weight-pill { font-size: 0.72rem; color: #888; }
  .justification { color: #444; line-height: 1.4; }
  .override-note { font-size: 0.72rem; color: #888; font-style: italic; margin-top: 3px; }

  footer { text-align: center; padding: 28px; font-size: 0.78rem; color: #aaa; }
</style>
</head>
<body>
<header>
  <h1>HR Candidate Shortlist Report</h1>
  <p>Generated {{ timestamp }} &nbsp;·&nbsp; {{ results|length }} candidate(s) evaluated</p>
</header>

<div class="container">

  <!-- Summary cards -->
  <div class="summary">
    <div class="summary-card">
      <div class="num">{{ results|length }}</div>
      <div class="lbl">Total Evaluated</div>
    </div>
    <div class="summary-card">
      <div class="num" style="color:#155724">{{ hire_count }}</div>
      <div class="lbl">HIRE</div>
    </div>
    <div class="summary-card">
      <div class="num" style="color:#856404">{{ maybe_count }}</div>
      <div class="lbl">MAYBE</div>
    </div>
    <div class="summary-card">
      <div class="num" style="color:#721c24">{{ nohire_count }}</div>
      <div class="lbl">NO HIRE</div>
    </div>
    <div class="summary-card">
      <div class="num">{{ "%.2f"|format(avg_score) }}</div>
      <div class="lbl">Avg Score</div>
    </div>
  </div>

  <!-- Candidate cards -->
  {% for r in results %}
  {% set pct = (r.weighted_total / 10 * 100)|int %}
  {% set badge_class = r.recommendation | replace(" ", "-") %}
  <div class="card">
    <div class="card-header">
      <div class="rank">#{{ loop.index }}</div>
      <div class="name">{{ r.name }}</div>
      <div class="meta">Score: <strong>{{ r.weighted_total }}</strong> / 10 &nbsp;</div>
      <span class="badge {{ badge_class }}">{{ r.recommendation }}</span>
    </div>
    <div class="card-body">

      <!-- Total score bar -->
      <div class="total-row">
        <div class="total-label">Weighted Total</div>
        <div class="total-bar-wrap">
          <div class="total-bar" style="width:{{ pct }}%"></div>
        </div>
        <div class="total-num">{{ r.weighted_total }}</div>
      </div>

      <!-- Dimension breakdown table -->
      <table>
        <thead>
          <tr>
            <th>Dimension</th>
            <th style="text-align:center">Score</th>
            <th>Weight</th>
            <th>Justification</th>
          </tr>
        </thead>
        <tbody>
          {% set dims = [
            ("Skills Match",          r.skills_match,          "30%"),
            ("Experience Relevance",  r.experience_relevance,  "25%"),
            ("Education & Certs",     r.education_certs,       "15%"),
            ("Project / Portfolio",   r.project_portfolio,     "20%"),
            ("Communication Quality", r.communication_quality, "10%"),
          ] %}
          {% for dname, dim, weight in dims %}
          {% set sc = dim.score %}
          {% set sc_class = "score-high" if sc >= 7 else ("score-mid" if sc >= 4 else "score-low") %}
          {% set just = dim.justification %}
          {% set is_override = "[HR override:" in just %}
          <tr>
            <td class="dim-name">{{ dname }}</td>
            <td><span class="dim-score {{ sc_class }}">{{ sc }}</span></td>
            <td><span class="weight-pill">{{ weight }}</span></td>
            <td>
              <div class="justification">
                {% if is_override %}
                  {{ just.split("[HR override:")[0].strip() }}
                  <div class="override-note">✎ HR override: {{ just.split("[HR override:")[1].rstrip("]") }}</div>
                {% else %}
                  {{ just }}
                {% endif %}
              </div>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>

    </div>
  </div>
  {% endfor %}

</div>
<footer>HR Resume Shortlisting Agent &nbsp;·&nbsp; Scores are AI-generated; human review recommended before final decisions.</footer>
</body>
</html>"""


def generate_html_report(
    results: list[CandidateResult],
    out_path: str = "shortlist_report.html",
) -> str:
    """Render results to a styled HTML report and save to out_path."""
    hire_count   = sum(1 for r in results if r.recommendation == "HIRE")
    maybe_count  = sum(1 for r in results if r.recommendation == "MAYBE")
    nohire_count = sum(1 for r in results if r.recommendation == "NO HIRE")
    avg_score    = sum(r.weighted_total for r in results) / len(results) if results else 0

    template = Template(_TEMPLATE)
    html = template.render(
        results=results,
        timestamp=datetime.utcnow().strftime("%d %b %Y, %H:%M UTC"),
        hire_count=hire_count,
        maybe_count=maybe_count,
        nohire_count=nohire_count,
        avg_score=avg_score,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report saved → {out_path}")
    return out_path