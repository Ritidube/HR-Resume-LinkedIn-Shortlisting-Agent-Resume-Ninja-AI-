"""
app.py  —  HR Resume Shortlisting Agent · Streamlit UI
Run:  streamlit run app.py
"""

import streamlit as st
import json, os, io, csv, tempfile, re
from pathlib import Path
from datetime import datetime

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HR Shortlisting Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── load dotenv so llm_client works ──────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── lazy imports (heavy) ──────────────────────────────────────────────────────
from parsers import extract_text, parse_jd, parse_resume, parse_linkedin_json
from scorer  import score_candidate
from models  import CandidateResult, JDProfile
from override import apply_override, VALID_DIMENSIONS

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

WEIGHTS = {"skills_match":0.30,"experience_relevance":0.25,
           "education_certs":0.15,"project_portfolio":0.20,"communication_quality":0.10}

def save_upload(uploaded_file) -> str:
    """Save a Streamlit UploadedFile to a temp path and return the path."""
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(uploaded_file.read())
        return f.name

def badge(rec: str) -> str:
    colors = {"HIRE":"#d4edda:#155724", "MAYBE":"#fff3cd:#856404", "NO HIRE":"#f8d7da:#721c24"}
    bg, fg = colors.get(rec, "#eee:#333").split(":")
    return f'<span style="background:{bg};color:{fg};padding:3px 12px;border-radius:12px;font-weight:700;font-size:0.8rem">{rec}</span>'

def score_color(s: float) -> str:
    if s >= 7: return "#155724"
    if s >= 4: return "#856404"
    return "#721c24"

def score_bg(s: float) -> str:
    if s >= 7: return "#d4edda"
    if s >= 4: return "#fff3cd"
    return "#f8d7da"

def get_dims(r: CandidateResult):
    return [
        ("Skills Match",          r.skills_match,          "30%"),
        ("Experience Relevance",  r.experience_relevance,  "25%"),
        ("Education & Certs",     r.education_certs,       "15%"),
        ("Project / Portfolio",   r.project_portfolio,     "20%"),
        ("Communication Quality", r.communication_quality, "10%"),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Export helpers
# ─────────────────────────────────────────────────────────────────────────────

def to_csv_bytes(results: list[CandidateResult]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Rank","Name","Skills Match","Experience","Education","Portfolio",
                "Communication","Weighted Total","Recommendation"])
    for i, r in enumerate(results, 1):
        w.writerow([i, r.name,
                    r.skills_match.score, r.experience_relevance.score,
                    r.education_certs.score, r.project_portfolio.score,
                    r.communication_quality.score, r.weighted_total, r.recommendation])
    return buf.getvalue().encode()

def to_json_bytes(results: list[CandidateResult]) -> bytes:
    return json.dumps([r.model_dump() for r in results], indent=2).encode()

def to_pdf_bytes(results: list[CandidateResult], jd: JDProfile | None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rlc
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    navy   = rlc.HexColor("#1a3c5e")
    green  = rlc.HexColor("#155724")
    amber  = rlc.HexColor("#856404")
    red    = rlc.HexColor("#721c24")

    h1  = ParagraphStyle("h1",  fontSize=18, textColor=navy,  spaceAfter=4,  fontName="Helvetica-Bold")
    h2  = ParagraphStyle("h2",  fontSize=13, textColor=navy,  spaceAfter=4,  fontName="Helvetica-Bold")
    sub = ParagraphStyle("sub", fontSize=9,  textColor=rlc.grey, spaceAfter=12)
    bod = ParagraphStyle("bod", fontSize=9,  spaceAfter=4,  leading=13)
    sml = ParagraphStyle("sml", fontSize=8,  textColor=rlc.HexColor("#555"))

    story = []
    story.append(Paragraph("HR Candidate Shortlist Report", h1))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}  ·  "
        f"{len(results)} candidate(s) evaluated", sub))
    story.append(HRFlowable(width="100%", thickness=1, color=navy, spaceAfter=10))

    # Summary table
    hire = sum(1 for r in results if r.recommendation=="HIRE")
    maybe= sum(1 for r in results if r.recommendation=="MAYBE")
    noh  = sum(1 for r in results if r.recommendation=="NO HIRE")
    avg  = sum(r.weighted_total for r in results)/len(results) if results else 0
    sum_data = [["Total","HIRE","MAYBE","NO HIRE","Avg Score"],
                [str(len(results)), str(hire), str(maybe), str(noh), f"{avg:.2f}"]]
    st_tbl = Table(sum_data, colWidths=[35*mm]*5)
    st_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), navy),
        ("TEXTCOLOR",(0,0),(-1,0), rlc.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1), 9),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[rlc.HexColor("#f4f6f9"), rlc.white]),
        ("BOX",(0,0),(-1,-1),0.5, rlc.lightgrey),
        ("GRID",(0,0),(-1,-1),0.3, rlc.lightgrey),
    ]))
    story.append(st_tbl)
    story.append(Spacer(1, 12))

    for i, r in enumerate(results, 1):
        rc = {"HIRE": green, "MAYBE": amber, "NO HIRE": red}.get(r.recommendation, rlc.grey)
        story.append(Paragraph(f"#{i}  {r.name}", h2))
        story.append(Paragraph(
            f"Weighted Total: <b>{r.weighted_total}/10</b>  ·  "
            f'<font color="#{rc.hexval()[2:] if hasattr(rc,"hexval") else "333333"}">'
            f'<b>{r.recommendation}</b></font>', bod))

        dim_data = [["Dimension","Score","Weight","Justification"]]
        for dname, dim, wt in get_dims(r):
            just = dim.justification
            if "[HR override:" in just:
                just = just.split("[HR override:")[0].strip() + " [HR override]"
            dim_data.append([dname, f"{dim.score}/10", wt,
                             Paragraph(just[:120], sml)])
        dim_tbl = Table(dim_data, colWidths=[42*mm, 18*mm, 14*mm, 86*mm])
        dim_tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), rlc.HexColor("#f0f4f8")),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1), 8),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[rlc.white, rlc.HexColor("#fafafa")]),
            ("BOX",(0,0),(-1,-1),0.4, rlc.lightgrey),
            ("GRID",(0,0),(-1,-1),0.3, rlc.lightgrey),
        ]))
        story.append(dim_tbl)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.4, color=rlc.lightgrey, spaceAfter=8))

    story.append(Paragraph(
        "Scores are AI-generated. Human review is recommended before final hiring decisions.", sub))
    doc.build(story)
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# AI Summary helper
# ─────────────────────────────────────────────────────────────────────────────
def generate_ai_summary(r: CandidateResult, jd_title: str) -> str:
    from llm_client import CALL_LLM_HERE
    prompt = f"""You are an HR assistant. Write a 2-sentence recommendation summary for this candidate.
Be specific, reference their actual scores, and give a clear hiring rationale.
End with one concrete next step (e.g. "Recommended for technical interview", "Consider for junior role", "Not suitable at this time").

Candidate: {r.name}
Role: {jd_title}
Weighted Score: {r.weighted_total}/10
Recommendation: {r.recommendation}
Skills Match: {r.skills_match.score}/10 — {r.skills_match.justification[:80]}
Experience: {r.experience_relevance.score}/10 — {r.experience_relevance.justification[:80]}
Education: {r.education_certs.score}/10 — {r.education_certs.justification[:80]}
Portfolio: {r.project_portfolio.score}/10 — {r.project_portfolio.justification[:80]}
Communication: {r.communication_quality.score}/10 — {r.communication_quality.justification[:80]}

Write only the summary, no labels, no JSON."""
    return CALL_LLM_HERE(prompt)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="stSidebar"] { background: #1a3c5e; }
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stFileUploader label { color: #cce0f5 !important; }
.card { background:white; border-radius:10px; padding:22px 26px;
        box-shadow:0 2px 10px rgba(0,0,0,.07); margin-bottom:18px; }
.metric-card { background:white; border-radius:8px; padding:16px;
               text-align:center; box-shadow:0 1px 5px rgba(0,0,0,.06); }
.metric-num { font-size:2rem; font-weight:800; color:#1a3c5e; }
.metric-lbl { font-size:0.75rem; color:#888; margin-top:2px; }
.dim-row { display:flex; gap:8px; align-items:flex-start;
           padding:8px 0; border-bottom:1px solid #f0f0f0; }
.dim-name { font-weight:600; font-size:0.85rem; min-width:170px; }
.dim-badge { padding:2px 10px; border-radius:8px; font-weight:700;
             font-size:0.82rem; min-width:46px; text-align:center; }
.dim-just { font-size:0.82rem; color:#444; line-height:1.4; flex:1; }
.override-note { font-size:0.72rem; color:#888; font-style:italic; }
.jd-tag { display:inline-block; background:#e8f0fe; color:#1a3c5e;
          border-radius:12px; padding:2px 10px; margin:2px;
          font-size:0.78rem; font-weight:600; }
.summary-box { background:#f0f7ff; border-left:4px solid #1a3c5e;
               border-radius:0 8px 8px 0; padding:14px 18px;
               font-size:0.9rem; line-height:1.6; color:#222; }
</style>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────────────────────
for key in ["results","jd","jd_text","processing","summaries"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "summaries" not in st.session_state or st.session_state.summaries is None:
    st.session_state.summaries = {}

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — inputs
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 HR Shortlisting Agent")
    st.markdown("---")

    st.markdown("### 📄 Job Description")
    jd_file = st.file_uploader("Upload JD (PDF or DOCX)", type=["pdf","docx"], key="jd_upload")

    st.markdown("### 👤 Resumes")
    resume_files = st.file_uploader("Upload Resumes (PDF / DOCX)",
                                     type=["pdf","docx"], accept_multiple_files=True, key="resume_upload")

    st.markdown("### 🔗 LinkedIn")
    linkedin_url_input = st.text_input("LinkedIn URL (optional)",
                                        placeholder="https://linkedin.com/in/username")
    linkedin_json_file = st.file_uploader("LinkedIn JSON Export (optional)",
                                           type=["json"], key="linkedin_upload")

    st.markdown("---")
    run_btn = st.button("🚀 Run Pipeline", use_container_width=True, type="primary")
    st.markdown("---")
    st.markdown("**Stack:** LLaMA-3.3-70B · Groq · BGE Embeddings · Pydantic")

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("# 🤖 HR Resume Shortlisting Agent")
st.markdown("Upload a Job Description and candidate resumes — the agent scores, ranks, and explains every decision.")

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline execution
# ─────────────────────────────────────────────────────────────────────────────
if run_btn:
    if not jd_file:
        st.error("Please upload a Job Description first.")
    elif not resume_files and not linkedin_json_file:
        st.error("Please upload at least one resume or LinkedIn JSON.")
    else:
        with st.spinner("Running pipeline…"):
            progress = st.progress(0, text="Parsing JD…")
            try:
                # Parse JD
                jd_path = save_upload(jd_file)
                jd_text = extract_text(jd_path)
                jd      = parse_jd(jd_text)
                st.session_state.jd      = jd
                st.session_state.jd_text = jd_text
                progress.progress(15, "JD parsed ✓  —  processing resumes…")

                results = []
                total_files = len(resume_files) + (1 if linkedin_json_file else 0)

                for idx, rf in enumerate(resume_files):
                    progress.progress(15 + int(70 * idx / max(total_files,1)),
                                      f"Scoring {rf.name}…")
                    rpath     = save_upload(rf)
                    rtext     = extract_text(rpath)
                    candidate = parse_resume(rtext)
                    # attach LinkedIn URL if provided and no json
                    if linkedin_url_input and not linkedin_json_file:
                        candidate.linkedin_url = linkedin_url_input
                    result = score_candidate(jd, candidate)
                    results.append(result)

                if linkedin_json_file:
                    progress.progress(85, "Processing LinkedIn profile…")
                    lpath     = save_upload(linkedin_json_file)
                    candidate = parse_linkedin_json(lpath)
                    if linkedin_url_input:
                        candidate.linkedin_url = linkedin_url_input
                    result = score_candidate(jd, candidate)
                    results.append(result)

                results.sort(key=lambda r: r.weighted_total, reverse=True)
                st.session_state.results   = results
                st.session_state.summaries = {}
                progress.progress(100, "Done ✓")

            except Exception as e:
                st.error(f"Pipeline error: {e}")
                import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# Results display
# ─────────────────────────────────────────────────────────────────────────────
results: list[CandidateResult] = st.session_state.results or []
jd: JDProfile | None           = st.session_state.jd

if not results:
    st.info("Upload a JD and resumes in the sidebar, then click **Run Pipeline**.")
    st.stop()

# ── 1. JD PARSED DISPLAY ─────────────────────────────────────────────────────
with st.expander("📋 Parsed Job Description", expanded=True):
    if jd:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Role:** {jd.title}")
            st.markdown(f"**Domain:** {jd.domain}")
            st.markdown(f"**Min Experience:** {jd.min_years_experience} years")
            st.markdown(f"**Education Required:** {jd.education_requirement}")
        with c2:
            st.markdown("**Required Skills:**")
            skills_html = " ".join(f'<span class="jd-tag">{s}</span>' for s in jd.required_skills)
            st.markdown(skills_html, unsafe_allow_html=True)
            if jd.preferred_skills:
                st.markdown("**Nice to Have:**")
                nice_html = " ".join(f'<span class="jd-tag" style="background:#fef9e7;color:#856404">{s}</span>'
                                     for s in jd.preferred_skills)
                st.markdown(nice_html, unsafe_allow_html=True)
        if jd.key_responsibilities:
            st.markdown("**Key Responsibilities:**")
            for r in jd.key_responsibilities:
                st.markdown(f"- {r}")

# ── 2. SUMMARY METRICS ───────────────────────────────────────────────────────
st.markdown("## 📊 Results Summary")
hire_n   = sum(1 for r in results if r.recommendation=="HIRE")
maybe_n  = sum(1 for r in results if r.recommendation=="MAYBE")
nohire_n = sum(1 for r in results if r.recommendation=="NO HIRE")
avg_sc   = sum(r.weighted_total for r in results) / len(results)

m1,m2,m3,m4,m5 = st.columns(5)
for col, num, lbl, color in [
    (m1, len(results), "Total Evaluated", "#1a3c5e"),
    (m2, hire_n,       "HIRE",            "#155724"),
    (m3, maybe_n,      "MAYBE",           "#856404"),
    (m4, nohire_n,     "NO HIRE",         "#721c24"),
    (m5, f"{avg_sc:.2f}", "Avg Score",    "#1a3c5e"),
]:
    col.markdown(
        f'<div class="metric-card"><div class="metric-num" style="color:{color}">{num}</div>'
        f'<div class="metric-lbl">{lbl}</div></div>', unsafe_allow_html=True)

# ── 3. CHARTS ────────────────────────────────────────────────────────────────
st.markdown("## 📈 Visual Analytics")
try:
    import plotly.graph_objects as go
    import plotly.express as px

    ch1, ch2, ch3 = st.columns(3)

    # Pie chart
    with ch1:
        labels = ["HIRE","MAYBE","NO HIRE"]
        vals   = [hire_n, maybe_n, nohire_n]
        fig_pie = go.Figure(go.Pie(
            labels=labels, values=vals,
            marker_colors=["#28a745","#ffc107","#dc3545"],
            hole=0.45, textinfo="label+value"
        ))
        fig_pie.update_layout(title="Hire Decision Split", height=300,
                              margin=dict(t=40,b=0,l=0,r=0), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Bar chart — candidate scores
    with ch2:
        names  = [r.name.split()[0] for r in results]
        scores = [r.weighted_total for r in results]
        bar_colors = ["#28a745" if r.recommendation=="HIRE"
                      else "#ffc107" if r.recommendation=="MAYBE"
                      else "#dc3545" for r in results]
        fig_bar = go.Figure(go.Bar(x=names, y=scores, marker_color=bar_colors,
                                    text=scores, textposition="outside"))
        fig_bar.update_layout(title="Candidate Scores", height=300,
                               yaxis=dict(range=[0,10.5]),
                               margin=dict(t=40,b=0,l=0,r=0))
        st.plotly_chart(fig_bar, use_container_width=True)

    # Radar chart — top candidate
    with ch3:
        top = results[0]
        dim_labels = ["Skills","Experience","Education","Portfolio","Communication"]
        dim_vals   = [top.skills_match.score, top.experience_relevance.score,
                      top.education_certs.score, top.project_portfolio.score,
                      top.communication_quality.score]
        fig_rad = go.Figure(go.Scatterpolar(
            r=dim_vals + [dim_vals[0]],
            theta=dim_labels + [dim_labels[0]],
            fill="toself", fillcolor="rgba(26,60,94,0.15)",
            line=dict(color="#1a3c5e", width=2)
        ))
        fig_rad.update_layout(title=f"Top Candidate: {top.name.split()[0]}",
                               polar=dict(radialaxis=dict(range=[0,10])),
                               height=300, margin=dict(t=40,b=0,l=0,r=0))
        st.plotly_chart(fig_rad, use_container_width=True)
except ImportError:
    st.info("Install plotly for charts: `pip install plotly`")

# ── 4. CANDIDATE CARDS ───────────────────────────────────────────────────────
st.markdown("## 🏆 Ranked Candidates")

for rank, r in enumerate(results, 1):
    pct = int(r.weighted_total / 10 * 100)
    with st.container():
        st.markdown(f"""
        <div class="card">
          <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">
            <span style="font-size:1.6rem;font-weight:800;color:#1a3c5e">#{rank}</span>
            <span style="font-size:1.2rem;font-weight:700;flex:1">{r.name}</span>
            <span style="font-size:0.95rem;color:#555">Score: <b>{r.weighted_total}</b>/10</span>
            {badge(r.recommendation)}
          </div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <span style="font-size:0.78rem;color:#888;min-width:100px">Weighted Total</span>
            <div style="flex:1;background:#eee;border-radius:6px;height:12px;overflow:hidden">
              <div style="width:{pct}%;height:12px;border-radius:6px;
                background:linear-gradient(90deg,#1a3c5e,#3b82c4)"></div>
            </div>
            <span style="font-weight:700;color:#1a3c5e;min-width:36px">{r.weighted_total}</span>
          </div>
        </div>""", unsafe_allow_html=True)

        # Dimension table
        with st.expander(f"📊 Score Breakdown — {r.name}", expanded=(rank==1)):
            for dname, dim, wt in get_dims(r):
                just = dim.justification
                override_note = ""
                if "[HR override:" in just:
                    parts = just.split("[HR override:")
                    just  = parts[0].strip()
                    override_note = f'<div class="override-note">✎ HR override: {parts[1].rstrip("]")}</div>'
                bg = score_bg(dim.score); fg = score_color(dim.score)
                st.markdown(f"""
                <div class="dim-row">
                  <div class="dim-name">{dname} <span style="font-weight:400;color:#aaa;font-size:0.75rem">{wt}</span></div>
                  <div class="dim-badge" style="background:{bg};color:{fg}">{dim.score}</div>
                  <div class="dim-just">{just}{override_note}</div>
                </div>""", unsafe_allow_html=True)

        # AI Summary
        col_sum, col_btn = st.columns([5, 1])
        with col_btn:
            if st.button("✨ AI Summary", key=f"sum_{r.name}_{rank}"):
                with st.spinner("Generating…"):
                    summary = generate_ai_summary(r, jd.title if jd else "this role")
                    st.session_state.summaries[r.name] = summary

        if r.name in st.session_state.summaries:
            with col_sum:
                st.markdown(
                    f'<div class="summary-box">{st.session_state.summaries[r.name]}</div>',
                    unsafe_allow_html=True)

        # HR Override
        with st.expander(f"✏️ HR Override — {r.name}"):
            ov_col1, ov_col2, ov_col3, ov_col4 = st.columns([2,1,2,1])
            with ov_col1:
                dim_choice = st.selectbox("Dimension", VALID_DIMENSIONS, key=f"dim_{r.name}_{rank}")
            with ov_col2:
                new_score  = st.number_input("New Score", 0.0, 10.0, step=0.5, key=f"sc_{r.name}_{rank}")
            with ov_col3:
                reason     = st.text_input("Reason", key=f"rs_{r.name}_{rank}")
            with ov_col4:
                hr_name    = st.text_input("Your Name", value="HR", key=f"hr_{r.name}_{rank}")
            if st.button("Apply Override", key=f"ov_{r.name}_{rank}"):
                idx = next(i for i,x in enumerate(results) if x.name==r.name)
                results[idx] = apply_override(results[idx], dim_choice, new_score, reason, hr_name)
                results.sort(key=lambda x: x.weighted_total, reverse=True)
                st.session_state.results = results
                st.success(f"Override applied! New total: {results[idx].weighted_total}")
                st.rerun()

        st.markdown("---")

# ── 5. EXPORT ────────────────────────────────────────────────────────────────
st.markdown("## 💾 Export Report")
ex1, ex2, ex3 = st.columns(3)

with ex1:
    st.download_button("⬇️ Download CSV", data=to_csv_bytes(results),
                       file_name="shortlist_report.csv", mime="text/csv",
                       use_container_width=True)
with ex2:
    st.download_button("⬇️ Download JSON", data=to_json_bytes(results),
                       file_name="shortlist_report.json", mime="application/json",
                       use_container_width=True)
with ex3:
    try:
        import reportlab
        pdf_bytes = to_pdf_bytes(results, jd)
        st.download_button("⬇️ Download PDF", data=pdf_bytes,
                           file_name="shortlist_report.pdf", mime="application/pdf",
                           use_container_width=True)
    except ImportError:
        st.info("Install reportlab for PDF: `pip install reportlab`")