"""Resume <-> Job-description matching.

The final match % is a weighted blend of four understandable parts:

    Skills match        50 %   skills the JD asks for vs skills found in the resume
                               ("required" = 1.0, "preferred" = 0.5, soft skills count half)
    Text similarity     25 %   TF-IDF cosine (+ semantic embeddings if enabled)
    Experience          15 %   resume years vs years the JD asks for
    Education           10 %   resume degree level vs degree the JD asks for

If the JD does not mention a part (e.g. no years stated) that part is dropped and the
remaining weights are re-scaled. The job description is read ONCE (prepare_job) and then
reused for every CV, so ranking hundreds of CVs stays fast.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import WEIGHTS
from .extractor import education_level, required_years, years_of_experience
from .preprocessing import clean_text
from .skills import extract_skills, is_soft

TFIDF_FULL_SCORE_AT = 0.45     # cosine that we treat as a "perfect" text match
_PREF_HINT = re.compile(r"preferred|nice to have|good to have|bonus|desirable|a plus|optional", re.I)
_REQ_HEAD = re.compile(r"requirements?|required|must have|qualifications|responsibilit|what you|you will|you have", re.I)
_JD_FILLER = {
    "role", "hiring", "requirement", "requirements", "year", "years", "strong",
    "preferred", "experience", "ability", "work", "skill", "skills", "team",
    "looking", "join", "candidate", "responsibility", "responsibilities",
    "familiarity", "excellent", "knowledge", "understanding", "nice", "have",
    "using", "company", "position", "job", "opportunity", "about", "must",
    "required", "plus", "bonus", "good", "great", "including", "within",
    "across", "highly", "proven", "demonstrated", "degree", "field", "ideal",
    "build", "building", "business", "environment", "will", "want", "bachelor",
    "bachelors", "master", "masters", "quantitative",
}


@dataclass
class JobSpec:
    """Everything we read from the job description, computed once."""
    text: str
    clean: str
    required: List[str]
    preferred: List[str]
    need_years: Optional[float]
    need_lvl: Optional[int]
    need_label: Optional[str]
    role: Optional[str] = None          # job family the JD reads like (filled in by the Job)


def verdict(score: float) -> str:
    if score >= 75:
        return "Excellent match"
    if score >= 55:
        return "Good match"
    if score >= 35:
        return "Partial match"
    return "Weak match"


def split_jd_skills(jd_text: str):
    """Return (required, preferred) skill lists found in a job description."""
    required, preferred = set(), set()
    mode = "required"
    for line in jd_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        short = len(stripped) < 80
        if short and _PREF_HINT.search(stripped):
            mode = "preferred"
        elif short and _REQ_HEAD.search(stripped):
            mode = "required"
        line_mode = "preferred" if _PREF_HINT.search(stripped) else mode
        for s in extract_skills(stripped):
            (required if line_mode == "required" else preferred).add(s)
    preferred -= required
    return sorted(required), sorted(preferred)


def prepare_job(jd_text: str) -> JobSpec:
    req, pref = split_jd_skills(jd_text)
    lvl, label = education_level(jd_text, lowest=True)
    return JobSpec(text=jd_text, clean=clean_text(jd_text), required=req, preferred=pref,
                   need_years=required_years(jd_text), need_lvl=lvl, need_label=label)


def _tfidf_cosine(a_clean: str, b_clean: str) -> float:
    if not a_clean or not b_clean:
        return 0.0
    try:
        m = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform([a_clean, b_clean])
        return float(cosine_similarity(m[0], m[1])[0][0])
    except ValueError:
        return 0.0


def _missing_keywords(resume_clean: str, jd_clean: str, skill_words: set, top: int = 12) -> List[str]:
    resume_tokens = set(resume_clean.split())
    counts = Counter(t for t in jd_clean.split() if len(t) > 3)
    out = []
    for word, _ in counts.most_common(60):
        if word in resume_tokens or word in skill_words or word in _JD_FILLER:
            continue
        out.append(word)
        if len(out) >= top:
            break
    return out


def match(resume_text: str, job, weights: Optional[Dict[str, float]] = None,
          sem: Optional[float] = None, resume_clean: Optional[str] = None) -> dict:
    """Compare one resume with a job (JobSpec or raw text). `sem` = optional embedding cosine."""
    spec = job if isinstance(job, JobSpec) else prepare_job(job)
    W = {**WEIGHTS, **(weights or {})}
    required, preferred = spec.required, spec.preferred
    resume_skills = set(extract_skills(resume_text))

    # ---- 1. skills
    skill_weights = {s: (1.0 if s in required else 0.5) * (0.5 if is_soft(s) else 1.0)
                     for s in required + preferred}
    skills_score, matched_req, missing_req, matched_pref, missing_pref = None, [], [], [], []
    if skill_weights:
        got = sum(w for s, w in skill_weights.items() if s in resume_skills)
        skills_score = got / sum(skill_weights.values())
        matched_req = [s for s in required if s in resume_skills]
        missing_req = [s for s in required if s not in resume_skills]
        matched_pref = [s for s in preferred if s in resume_skills]
        missing_pref = [s for s in preferred if s not in resume_skills]

    # ---- 2. text similarity
    r_clean = resume_clean if resume_clean is not None else clean_text(resume_text)
    tfidf_cos = _tfidf_cosine(r_clean, spec.clean)
    text_score = min(1.0, tfidf_cos / TFIDF_FULL_SCORE_AT)
    if sem is not None:
        text_score = 0.5 * text_score + 0.5 * max(0.0, min(1.0, (sem - 0.15) / 0.55))

    # ---- 3. experience
    have_years = years_of_experience(resume_text)
    need_years = spec.need_years
    exp_score = None if need_years is None else (min(1.0, have_years / need_years) if need_years else 1.0)

    # ---- 4. education
    have_lvl, have_label = education_level(resume_text)
    edu_score = None
    if spec.need_lvl is not None:
        edu_score = 0.0 if have_lvl is None else (1.0 if have_lvl >= spec.need_lvl
                                                   else (have_lvl + 1) / (spec.need_lvl + 1))

    parts = {"skills": skills_score, "text": text_score, "experience": exp_score, "education": edu_score}
    active = {k: v for k, v in parts.items() if v is not None and W.get(k, 0) > 0}
    total_w = sum(W[k] for k in active) or 1.0
    score = 100 * sum(W[k] * v for k, v in active.items()) / total_w

    details = {
        "skills": (f"{len(matched_req) + len(matched_pref)} of {len(skill_weights)} skills from the JD found"
                   if skill_weights else "No recognisable skills in the job description"),
        "text": "Wording overlap" + (" + meaning similarity" if sem is not None else ""),
        "experience": ("JD does not state years" if need_years is None
                       else f"{have_years:g} yrs found vs {need_years:g} asked"),
        "education": ("JD does not state a degree" if spec.need_lvl is None
                      else f"{have_label or 'none found'} vs {spec.need_label} asked"),
    }
    names = {"skills": "Skills", "text": "Text similarity", "experience": "Experience", "education": "Education"}
    breakdown = [{
        "key": k, "name": names[k], "detail": details[k],
        "weight": round(100 * W[k] / total_w) if k in active else 0,
        "score": round(100 * parts[k]) if parts[k] is not None else None,
    } for k in names]

    skill_words = {w for s in required + preferred for w in s.split()}
    return {
        "score": round(score, 1), "verdict": verdict(score), "breakdown": breakdown,
        "required_skills": required, "preferred_skills": preferred,
        "matched_required": matched_req, "missing_required": missing_req,
        "matched_preferred": matched_pref, "missing_preferred": missing_pref,
        "extra_skills": sorted(resume_skills - set(required) - set(preferred))[:25],
        "missing_keywords": _missing_keywords(r_clean, spec.clean, skill_words),
        "years_have": have_years, "years_need": need_years,
        "semantic_used": sem is not None, "tfidf_cosine": round(tfidf_cos, 3),
    }
