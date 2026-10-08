"""Table rows, CSV / Markdown reports, ZIP bundles and saved runs."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from typing import Dict, List, Optional

from .config import OUT, REVIEW_AT, SHORTLIST_AT


def safe(name: str) -> str:
    return re.sub(r"[^\w.\-() ]", "_", name) or "document"


def suggestion(score: Optional[float], shortlist: float = SHORTLIST_AT, review: float = REVIEW_AT) -> str:
    if score is None:
        return "-"
    return "Shortlist" if score >= shortlist else "Review" if score >= review else "Low match"


def rows(results: Dict[str, dict], shortlist: float = SHORTLIST_AT, review: float = REVIEW_AT) -> List[dict]:
    """One flat row per CV, best match first (or by file name when there is no job description)."""
    out = []
    for n, r in results.items():
        m, p = r["match"], r["profile"]
        score = m["score"] if m else None
        out.append({
            "name": n, "alias": r["alias"], "score": score,
            "verdict": m["verdict"] if m else "-", "suggestion": suggestion(score, shortlist, review),
            "skills_matched": (len(m["matched_required"]) + len(m["matched_preferred"])) if m else None,
            "skills_total": (len(m["required_skills"]) + len(m["preferred_skills"])) if m else None,
            "matched_required": m["matched_required"] if m else [],
            "missing_required": m["missing_required"] if m else [],
            "years": p["years_experience"], "education": p["education_label"] or "-",
            "ats": r["ats"]["score"], "role": r["roles"][0]["category"] if r.get("roles") else "-",
            "n_skills": len(r["skills_found"]), "note": r.get("note", ""),
        })
    out.sort(key=lambda x: (-(x["score"] if x["score"] is not None else -1), x["name"].lower()))
    for i, x in enumerate(out, 1):
        x["rank"] = i
    return out


def ranking_csv(rs: List[dict], blind: bool = False) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Rank", "CV", "Match %", "Verdict", "Suggestion", "Skills matched", "Skills asked",
                "Missing required skills", "Years experience", "Education", "ATS score", "Best-fit role", "Note"])
    for r in rs:
        w.writerow([r["rank"], r["alias"] if blind else r["name"], r["score"] if r["score"] is not None else "",
                    r["verdict"], r["suggestion"], r["skills_matched"] if r["skills_matched"] is not None else "",
                    r["skills_total"] if r["skills_total"] is not None else "", "; ".join(r["missing_required"]),
                    r["years"], r["education"], r["ats"], r["role"], r["note"]])
    return buf.getvalue()


def to_markdown(r: dict, title: Optional[str] = None) -> str:
    """A readable one-CV report."""
    m, p = r["match"], r["profile"]
    L = [f"# {title or r['name']}", ""]
    if m:
        L += [f"**Match: {m['score']:.0f}% - {m['verdict']}**", "", "| Part | Score | Weight | Detail |", "|---|---|---|---|"]
        L += [f"| {b['name']} | {b['score']}% | {b['weight']}% | {b['detail']} |" for b in m["breakdown"] if b["score"] is not None]
        L += ["", f"- Skills you have: {', '.join(m['matched_required'] + m['matched_preferred']) or 'none'}",
              f"- Required skills missing: {', '.join(m['missing_required']) or 'none'}",
              f"- Preferred skills missing: {', '.join(m['missing_preferred']) or 'none'}", ""]
    L += [f"**Read from CV:** {p['years_experience']:g} years experience, education: {p['education_label'] or 'not found'}, "
          f"{p['word_count']} words, {len(r['skills_found'])} skills", "",
          f"**ATS readability:** {r['ats']['score']}/100", ""]
    L += [f"- {c['name']}: {c['status']}" + (f" - {c['tip']}" if c["status"] != "pass" else "") for c in r["ats"]["checks"]]
    L += ["", "## What to do next", ""] + [f"{i}. {t}" for i, t in enumerate(r["advice"], 1)]
    if r.get("roles"):
        L += ["", "## Best-fit roles", ""] + [f"- {x['category']} ({x['confidence']}%)" for x in r["roles"]]
    return "\n".join(L) + "\n"


def build_zip(results: Dict[str, dict], rs: List[dict], blind: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ranking.csv", ranking_csv(rs, blind))
        for n, r in results.items():
            label = r["alias"] if blind else n
            z.writestr(f"reports/{safe(label)}.md", to_markdown(r, label))
    return buf.getvalue()


def load_last_run() -> Optional[dict]:
    files = sorted(OUT.glob("*/results.json")) if OUT.exists() else []
    try:
        return json.loads(files[-1].read_text(encoding="utf-8")) if files else None
    except Exception:
        return None
