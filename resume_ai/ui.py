"""The Streamlit page: sidebar, job + upload panel, live progress and results.

Everything - the job description, the CV files, the settings - is entered in the browser.
There is nothing to edit or upload in code.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from . import exporters, semantic
from .config import MAX_DOCS, MAX_FILE_MB, REVIEW_AT, ROOT, SHORTLIST_AT, UPLOAD_TYPES, WEIGHTS
from .exporters import safe
from .job import BUSY, COLOR, LABEL, WEIGHT, Job
from .predictor import models_available
from .readers import ReadError, expand_zip

CSS = """<style>
.block-container{padding-top:1.3rem;max-width:1650px}
header[data-testid="stHeader"]{background:transparent}
.hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;padding:1.35rem 1.8rem;border-radius:1.1rem;color:#fff;background:linear-gradient(120deg,#0f766e 0%,#4f46e5 55%,#0ea5e9 100%);box-shadow:0 10px 28px rgba(79,70,229,.25);margin-bottom:1.1rem}
.hero-t{font-size:1.85rem;font-weight:800;letter-spacing:-.02em;line-height:1.2}.hero-s{opacity:.92;margin-top:.25rem;font-size:.95rem}
.chips{display:flex;gap:.5rem;flex-wrap:wrap}.chip{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);padding:.3rem .85rem;border-radius:2rem;font-size:.8rem;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;margin:.35rem 0 .8rem}
.kpi{background:#fff;border:1px solid #e5e7eb;border-top:3px solid var(--accent,#4f46e5);border-radius:.8rem;padding:.65rem .95rem;box-shadow:0 1px 3px rgba(15,23,42,.06)}
.kpi-l{font-size:.78rem;color:#64748b;font-weight:700}.kpi-v{font-size:1.5rem;font-weight:800;color:#0f172a;line-height:1.3}.kpi-s{font-size:.78rem;color:#64748b}
.sec{font-size:.9rem;color:#475569;font-weight:700;margin:1rem 0 .4rem}
.tiles{display:flex;flex-wrap:wrap;gap:.3rem}.tile{width:2.15rem;height:2.15rem;border-radius:.55rem;color:#fff;font-size:.7rem;font-weight:700;display:flex;align-items:center;justify-content:center}
.tile.busy{animation:pulse 1.2s ease-in-out infinite}@keyframes pulse{50%{opacity:.55}}
.legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.45rem;font-size:.75rem;color:#64748b}.legend i{display:inline-block;width:.7rem;height:.7rem;border-radius:.2rem;margin-right:.3rem}
.shero{display:flex;gap:1.6rem;align-items:center;background:#fff;border:1px solid #e5e7eb;border-left:8px solid var(--c);border-radius:.8rem;padding:1.1rem 1.5rem;margin:.4rem 0 .8rem;color:#0f172a}
.shero.good{--c:#0e8a5f}.shero.ok{--c:#6b8e23}.shero.mid{--c:#b87a0a}.shero.low{--c:#c2410c}
.snum{font-size:4rem;font-weight:800;line-height:1;color:var(--c);letter-spacing:-.04em}.snum small{font-size:1.6rem;margin-left:2px}
.sver{font-size:1.35rem;font-weight:800}.ssub{color:#475569;margin-top:.15rem}
.strip{display:flex;gap:6px;margin:.2rem 0 .6rem}.seg{min-width:105px}.seg-bar{height:13px;background:#dfe4ec;border-radius:3px;overflow:hidden}
.seg-fill{height:100%;background:var(--c)}.seg-fill.good{--c:#0e8a5f}.seg-fill.ok{--c:#6b8e23}.seg-fill.mid{--c:#b87a0a}.seg-fill.low{--c:#c2410c}
.seg-name{font-size:.84rem;margin-top:5px;color:#0f172a}.seg-detail{font-size:.74rem;color:#64748b;line-height:1.3}
.srow{display:grid;grid-template-columns:140px 1fr;gap:10px;padding:.5rem 0;border-top:1px solid #eceff3;align-items:start}.srow:first-of-type{border-top:0}
.slbl{font-size:.84rem;font-weight:700;color:#475569;padding-top:3px}
.sk{display:inline-block;font-size:.83rem;padding:2px 10px;margin:0 6px 6px 0;border-radius:99px;border:1px solid transparent}
.sk.have{background:#e3f4ec;color:#0a6444;border-color:#b5dfcb}.sk.need{background:#fdebe3;color:#9a3412;border-color:#f2c4ae}
.sk.nice{background:#fff4d6;color:#8a5a00;border-color:#efd88f}.sk.extra{background:#eef1f5;color:#475569;border-color:#dde2ea}
.sk.kw{background:#fff;color:#0f172a;border-color:#b9c1ce;border-style:dashed}
@media (max-width:1100px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.strip{flex-direction:column}.seg{flex:none!important}}
</style>"""

TYPE_HELP = "PDF, DOCX, DOC, RTF, ODT, TXT, HTML, scanned images (JPG/PNG), or a ZIP full of CVs"


# ---------------------------------------------------------------- shared state / helpers
@st.cache_resource(show_spinner=False)
def registry() -> dict:
    return {"job": None, "loaded": None}              # shared by every browser tab, survives page reloads


@st.cache_resource(show_spinner=False)
def get_embedder(name: str):
    return semantic.Embedder(name)


def fmt_dur(sec: float) -> str:
    sec = int(round(max(sec or 0.0, 0.0)))
    h, rem = divmod(sec, 3600)
    return f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60}:{rem % 60:02d}"


def show_table(rows, **kw) -> None:
    try:
        st.dataframe(rows, width="stretch", hide_index=True, **kw)
    except Exception:
        st.dataframe(rows, use_container_width=True, hide_index=True, **kw)


def kpi(label: str, value: str, sub: str = "", accent: str = "#4f46e5") -> str:
    return (f'<div class="kpi" style="--accent:{accent}"><div class="kpi-l">{html.escape(label)}</div>'
            f'<div class="kpi-v">{html.escape(value)}</div><div class="kpi-s">{html.escape(sub)}</div></div>')


def kpi_row(*cards: str) -> None:
    st.markdown('<div class="kpis">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def level(score: float) -> str:
    return "good" if score >= 75 else "ok" if score >= 55 else "mid" if score >= 35 else "low"


def chips(items: List[str], cls: str, empty: str = "none") -> str:
    if not items:
        return f'<span style="color:#64748b;font-size:.85rem">{empty}</span>'
    return "".join(f'<span class="sk {cls}">{html.escape(i)}</span>' for i in items)


def srow(label: str, inner: str) -> str:
    return f'<div class="srow"><div class="slbl">{html.escape(label)}</div><div>{inner}</div></div>'


def tiles_html(files: List[dict]) -> str:
    tiles = "".join(f'<div class="tile{" busy" if f["status"] in BUSY else ""}" style="background:{COLOR[f["status"]]}" '
                    f'title="{html.escape(f["name"])} - {LABEL[f["status"]][2:]}">{i}</div>' for i, f in enumerate(files, 1))
    legend = "".join(f'<span><i style="background:{COLOR[s]}"></i>{LABEL[s].split(" ", 1)[1]}</span>' for s in COLOR)
    return f'<div class="tiles">{tiles}</div><div class="legend">{legend}</div>'


# ---------------------------------------------------------------- live progress
def live_panel(watching: bool) -> None:
    job: Optional[Job] = registry()["job"]
    if job is None:
        st.info("Progress for every CV appears here when you press **Analyze**.")
        return
    files = job.snapshot()
    n_done = sum(f["status"] == "done" for f in files)
    n_bad = sum(f["status"] in ("failed", "skipped") for f in files)
    finished = n_done + n_bad
    st.progress(min(max(job.frac, 0.0), 1.0), text=f"{job.phase}  ·  {finished}/{len(files)} files  ·  {fmt_dur(job.elapsed)} elapsed")
    if job.error:
        st.error(f"The run stopped unexpectedly: {job.error}")
    rate = f"{60 * n_done / job.elapsed:,.0f} CVs/min" if job.elapsed > 0 and n_done else "-"
    kpi_row(kpi("Files finished", f"{finished} / {len(files)}", f"{n_done} analysed"),
            kpi("Elapsed time", fmt_dur(job.elapsed), "running" if not job.done else "finished", "#0ea5e9"),
            kpi("Speed", rate, "analysed CVs only", "#10b981"),
            kpi("Problems", str(n_bad), "unreadable or duplicate files", "#e11d48" if n_bad else "#94a3b8"))
    st.markdown('<div class="sec">Files</div>' + tiles_html(files), unsafe_allow_html=True)
    cc = st.column_config
    show_table([{"#": i, "File": f["name"], "Status": LABEL[f["status"]], "Progress": round(100 * WEIGHT[f["status"]]),
                 "Words": f["words"] or None, "Match %": f["score"], "Time (s)": round(f["sec"], 2) or None, "Note": f["error"]}
                for i, f in enumerate(files, 1)],
               column_config={"Progress": cc.ProgressColumn("Progress", min_value=0, max_value=100, format="%d%%"),
                              "Match %": cc.NumberColumn("Match %", format="%.0f")})
    if job.timing:
        with st.expander("Where the time went"):
            show_table([{"Step": k, "Seconds": round(v, 2)} for k, v in job.timing.items()])
    if watching and job.done:
        st.rerun()


# ---------------------------------------------------------------- results
def render_cv(r: dict, meta: dict, title: str) -> None:
    m, p = r["match"], r["profile"]
    if r.get("note"):
        st.info(r["note"])
    if m:
        miss = len(m["missing_required"])
        sub = (f"Missing {miss} of the {len(m['required_skills'])} required skills." if miss else
               "Every required skill in the posting appears in this CV." if m["required_skills"] else
               "No specific skills were recognised in the posting, so wording and experience carry the score.")
        st.markdown(f'<div class="shero {level(m["score"])}"><div class="snum">{m["score"]:.0f}<small>%</small></div>'
                    f'<div><div class="sver">{html.escape(m["verdict"])}</div><div class="ssub">{html.escape(sub)}</div></div></div>',
                    unsafe_allow_html=True)
        segs = "".join(
            f'<div class="seg" style="flex:{b["weight"]}"><div class="seg-bar"><div class="seg-fill {level(b["score"])}" style="width:{b["score"]}%"></div></div>'
            f'<div class="seg-name">{html.escape(b["name"])} <b>{b["score"]}%</b></div>'
            f'<div class="seg-detail">{html.escape(b["detail"])} · counts {b["weight"]}%</div></div>'
            for b in m["breakdown"] if b["score"] is not None)
        st.markdown(f'<div class="strip">{segs}</div>', unsafe_allow_html=True)
        if meta.get("job_role") and r.get("roles"):
            best = r["roles"][0]["category"]
            same = "Same field - good sign." if best == meta["job_role"] else "Different fields - expect a harder fit."
            st.caption(f"This job reads like **{meta['job_role']}**; this CV reads most like **{best}**. {same}")
        st.markdown('<div class="sec">Skills the job asks for</div>' +
                    srow("CV has", chips(m["matched_required"] + m["matched_preferred"], "have")) +
                    srow("Required, missing", chips(m["missing_required"], "need", "nothing missing")) +
                    srow("Preferred, missing", chips(m["missing_preferred"], "nice", "nothing missing")) +
                    (srow("Also on the CV", chips(m["extra_skills"], "extra")) if m["extra_skills"] else "") +
                    (srow("Words to consider", chips(m["missing_keywords"][:10], "kw")) if m["missing_keywords"] else ""),
                    unsafe_allow_html=True)
    else:
        st.info("No job description was given, so there is no match score. Profile, ATS check and role fit are shown below.")

    kpi_row(kpi("Experience", f"{p['years_experience']:g} yrs", "found in the CV", "#8b5cf6"),
            kpi("Education", p["education_label"] or "not found", "highest level", "#e11d48"),
            kpi("Skills found", str(len(r["skills_found"])), "from the skill vocabulary", "#0ea5e9"),
            kpi("ATS readability", f"{r['ats']['score']} / 100", f"{p['word_count']} words", "#10b981"))

    st.markdown('<div class="sec">What to do next</div>', unsafe_allow_html=True)
    st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate(r["advice"], 1)) or "Nothing urgent - this CV reads well.")

    with st.expander("ATS readability checks"):
        icon = {"pass": "✅ Pass", "partial": "🟡 Partly", "fail": "❌ Fix"}
        show_table([{"Check": c["name"], "Result": icon[c["status"]], "Points": f"{c['points']}/{c['max']}",
                     "Tip": c["tip"] if c["status"] != "pass" else ""} for c in r["ats"]["checks"]])
    with st.expander("All skills found in this CV"):
        st.markdown(chips(r["skills_found"], "extra"), unsafe_allow_html=True)
    if r.get("roles"):
        with st.expander("Best-fit roles (ML model)"):
            show_table([{"Role": x["category"], "Confidence %": x["confidence"], "Skills it has": ", ".join(x["matched_skills"]),
                         "Skills to build": ", ".join(x["missing_skills"])} for x in r["roles"]])
    st.download_button("⬇ This CV's report (.md)", exporters.to_markdown(r, title), f"{safe(title)}.md", "text/markdown",
                       key=f"md_{safe(title)}")


def render_results(ds: dict) -> None:
    reg = registry()
    job: Optional[Job] = reg["job"]
    if job is not None and job.done and job.results:
        results, meta = job.results, {**job.meta, "seconds": job.elapsed}
    elif job is None and reg["loaded"]:
        results, meta = reg["loaded"]["results"], reg["loaded"]["meta"]
    else:
        st.info("Results appear here when the run finishes: a ranked table, filters, and a full report for every CV.")
        return

    blind, has_job = ds["blind"], meta.get("has_job")
    allrows = exporters.rows(results, ds["shortlist"], ds["review"])
    disp = (lambda r: r["alias"]) if blind else (lambda r: r["name"])
    n_sl = sum(r["suggestion"] == "Shortlist" for r in allrows)
    n_rv = sum(r["suggestion"] == "Review" for r in allrows)
    avg = sum(r["score"] for r in allrows) / len(allrows) if has_job else None
    kpi_row(kpi("CVs analysed", str(len(allrows)), f"in {fmt_dur(meta.get('seconds', 0))}"),
            kpi("Shortlist", str(n_sl) if has_job else "-", f"match ≥ {ds['shortlist']}%", "#10b981"),
            kpi("Review", str(n_rv) if has_job else "-", f"match {ds['review']}–{ds['shortlist']}%", "#d97706"),
            kpi("Average match", f"{avg:.0f}%" if avg is not None else "-", "all analysed CVs", "#0ea5e9"))

    if has_job:
        bits = [f"Required skills read from the job: **{', '.join(meta['required']) or 'none recognised'}**"]
        if meta.get("preferred"):
            bits.append(f"Preferred: {', '.join(meta['preferred'])}")
        if meta.get("need_years") is not None:
            bits.append(f"Experience asked: {meta['need_years']:g}+ yrs")
        st.caption(" · ".join(bits))
    if blind:
        st.caption("🕶️ Blind screening is on - CVs are shown as Candidate numbers. Turn it off in the sidebar to see file names.")

    # ---- filters
    shown = allrows
    if has_job:
        c1, c2 = st.columns([1.2, 1.2])
        min_score = c1.slider("Minimum match %", 0, 100, 0)
        keep = c2.multiselect("Show", ["Shortlist", "Review", "Low match"], default=["Shortlist", "Review", "Low match"])
        shown = [r for r in shown if r["score"] >= min_score and r["suggestion"] in keep]
        if meta.get("required"):
            must = st.multiselect("Only CVs that have ALL of these required skills", meta["required"])
            shown = [r for r in shown if all(s in r["matched_required"] for s in must)]
    q = st.text_input("Search by name", placeholder="type part of a file name" if not blind else "search disabled in blind mode",
                      disabled=blind).strip().lower()
    if q:
        shown = [r for r in shown if q in r["name"].lower()]

    cc = st.column_config
    st.caption(f"Showing {len(shown)} of {len(allrows)} CVs")
    show_table([{"#": r["rank"], "CV": disp(r), "Match %": r["score"], "Suggestion": r["suggestion"],
                 "Skills": f"{r['skills_matched']}/{r['skills_total']}" if has_job else None,
                 "Missing required": ", ".join(r["missing_required"]), "Years": r["years"], "Education": r["education"],
                 "ATS": r["ats"], "Best-fit role": r["role"], "Note": r["note"]} for r in shown],
               column_config={"Match %": cc.ProgressColumn("Match %", min_value=0, max_value=100, format="%.0f%%"),
                              "ATS": cc.ProgressColumn("ATS", min_value=0, max_value=100, format="%d")})
    d1, d2 = st.columns(2)
    d1.download_button(f"⬇ This table ({len(shown)} CVs, .csv)", exporters.ranking_csv(shown, blind), "ranking.csv", "text/csv",
                       disabled=not shown)
    d2.download_button(f"📦 All {len(allrows)} reports + ranking (.zip)", exporters.build_zip(results, allrows, blind),
                       "cv_reports.zip", "application/zip")

    if shown:
        st.markdown('<div class="sec">Open one CV</div>', unsafe_allow_html=True)
        names = {disp(r): r["name"] for r in shown}
        pick = st.selectbox("CV", list(names), label_visibility="collapsed")
        render_cv(results[names[pick]], meta, pick)


# ---------------------------------------------------------------- sidebar + upload
def sidebar() -> dict:
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        with st.expander("Match score weights"):
            st.caption("How much each part counts. Parts a job does not mention are skipped automatically.")
            w = {"skills": st.slider("Skills", 0, 100, int(WEIGHTS["skills"] * 100)),
                 "text": st.slider("Text similarity", 0, 100, int(WEIGHTS["text"] * 100)),
                 "experience": st.slider("Experience", 0, 100, int(WEIGHTS["experience"] * 100)),
                 "education": st.slider("Education", 0, 100, int(WEIGHTS["education"] * 100))}
            if sum(w.values()) == 0:
                w = {k: v * 100 for k, v in WEIGHTS.items()}
        sem = st.toggle("Meaning-based similarity", value=False, disabled=not semantic.available(),
                        help="Understands that 'built ML models' ≈ 'machine learning engineer'. Needs sentence-transformers "
                             "(downloads ~90 MB the first time).")
        if not semantic.available():
            st.caption("Install `sentence-transformers` to enable this.")
        roles = st.toggle("Suggest best-fit role", value=models_available(), disabled=not models_available(),
                          help="Uses the trained model in models/. Run train.py to create it.")
        has_ocr = shutil.which("tesseract") is not None
        ocr = st.toggle("Read scanned CVs (OCR)", value=has_ocr, disabled=not has_ocr,
                        help="Only used for image files and PDFs without text. Slower: a few seconds per page.")
        if not has_ocr:
            st.caption("Install `tesseract-ocr` to read scanned CVs.")
        st.divider()
        shortlist = st.slider("Shortlist from match %", 30, 95, SHORTLIST_AT)
        review = min(st.slider("Review from match %", 5, 90, REVIEW_AT), shortlist)
        blind = st.toggle("Blind screening", value=False,
                          help="Show Candidate 001, 002 ... instead of file names (names often contain the person's name).")
        st.divider()
        if st.button("Load last saved run"):
            data = exporters.load_last_run()
            if data:
                registry().update(job=None, loaded=data)
                st.rerun()
            st.warning("No saved run found.")
        st.caption(f"Up to **{MAX_DOCS}** CVs per run · {MAX_FILE_MB} MB per file")
    return dict(weights={k: v / 100 for k, v in w.items()}, semantic=sem, roles=roles, ocr=ocr,
                shortlist=shortlist, review=review, blind=blind)


def _unique(name: str, taken: set) -> str:
    base, stem, i = name, Path(name).stem, 2
    suffix = Path(name).suffix
    while name in taken:
        name, i = f"{stem} ({i}){suffix}", i + 1
    return name


def start_job(files, jd: str, cfg: dict) -> None:
    items, taken, problems = [], set(), []
    with st.status("Unpacking files ...", expanded=False) as status:
        for f in files:
            data = f.getvalue()
            if f.name.lower().endswith(".zip"):
                try:
                    inner = expand_zip(data, MAX_DOCS + 1 - len(items))
                    problems.append(f"{f.name}: {len(inner)} files inside")
                except ReadError as e:
                    problems.append(f"{f.name}: {e}")
                    continue
                batch = inner
            else:
                batch = [(f.name, data)]
            for n, d in batch:
                n = _unique(n, taken)
                taken.add(n)
                items.append((n, d))
        status.update(label=f"{len(items)} files ready", state="complete")
    for p in problems:
        st.caption(p)
    if not items:
        st.error("No readable files found.")
        return
    if len(items) > MAX_DOCS:
        st.error(f"{len(items)} files found - the limit is {MAX_DOCS} per run. Split them into batches "
                 f"(or raise CV_MAX_DOCS).")
        return
    emb = None
    if cfg["semantic"] and jd.strip():
        with st.status("Loading the meaning model ... (first run downloads it)", expanded=False) as status:
            emb = get_embedder(semantic.MODEL)
            if emb.model is None:
                st.warning(f"Meaning model unavailable ({emb.error[:120]}); using word-based similarity only.")
            status.update(label="Model ready", state="complete")
    registry().update(job=Job(items, jd, cfg, emb), loaded=None)
    st.session_state.uploader_key += 1                      # empties the uploader so the files stop using RAM
    st.rerun()


def _example_job() -> None:
    p = ROOT / "samples" / "jd_data_scientist.txt"
    if p.exists():
        st.session_state.jd = p.read_text(encoding="utf-8")


def upload_panel(running: bool, cfg: dict) -> None:
    ss = st.session_state
    ss.setdefault("uploader_key", 0)
    ss.setdefault("jd", "")
    st.subheader("1 · Job description")
    st.text_area("Paste the job posting", key="jd", height=230, disabled=running, label_visibility="collapsed",
                 placeholder="Paste the full job posting here. Leave empty to only profile the CVs (no match score).")
    st.button("Use an example job", on_click=_example_job, disabled=running)

    st.subheader("2 · Upload CVs")
    files = st.file_uploader(f"Drop up to {MAX_DOCS} CVs (or one ZIP of many)", type=UPLOAD_TYPES, accept_multiple_files=True,
                             disabled=running, key=f"up_{ss.uploader_key}") or []
    st.caption(TYPE_HELP)
    if files:
        st.caption(f"{len(files)} selected · {sum(f.size for f in files) / 1e6:.1f} MB")
    go = st.button("🚀 Analyze", type="primary", disabled=not files or running)
    if running:
        job = registry()["job"]
        if st.button("⏹ Stop after the current step"):
            job.cancel.set()
        st.caption("Stopping..." if job.cancel.is_set() else "Running in the background - you can switch tabs or reload the page.")
    if go:
        start_job(files, ss.jd, cfg)
    job = registry()["job"]
    if job is not None and job.done and job.out_dir:
        st.success(f"Finished {len(job.results)} CV(s) in {fmt_dur(job.elapsed)}. Saved in {job.out_dir}")


def main() -> None:
    st.set_page_config(page_title="CV Match Studio", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    cfg = sidebar()
    st.markdown('<div class="hero"><div><div class="hero-t">🎯 CV Match Studio</div><div class="hero-s">Rank up to '
                f'{MAX_DOCS} CVs against one job - explainable scores, skill gaps and an ATS check for each CV</div></div>'
                '<div class="chips"><span class="chip">PDF · DOCX · DOC · TXT · RTF · ODT · images · ZIP</span>'
                '<span class="chip">Match %</span><span class="chip">Skill gaps</span><span class="chip">ATS check</span></div></div>',
                unsafe_allow_html=True)
    reg = registry()
    left, right = st.columns([1, 2.3], gap="large")
    with left:
        upload_panel(reg["job"] is not None and not reg["job"].done, cfg)
    job = reg["job"]
    running = job is not None and not job.done
    with right:
        tab_live, tab_res = st.tabs(["📊 Live progress", "📄 Results"])
        with tab_live:
            st.fragment(run_every=1.0 if running else None)(live_panel)(running)
        with tab_res:
            render_results(cfg)
