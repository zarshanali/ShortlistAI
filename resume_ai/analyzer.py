"""Everything we say about ONE resume (optionally against a prepared job)."""
from __future__ import annotations

from typing import Dict, Optional

from .advice import build_advice
from .ats import ats_check
from .extractor import build_profile
from .matcher import JobSpec, match, prepare_job
from .predictor import models_available, predict_roles
from .preprocessing import clean_text
from .skills import extract_skills


def analyze_resume(text: str, job: Optional[JobSpec] = None, weights: Optional[Dict[str, float]] = None,
                   sem: Optional[float] = None, roles: bool = True) -> dict:
    clean = clean_text(text)
    profile = build_profile(text)
    ats = ats_check(text)
    m = match(text, job, weights, sem, resume_clean=clean) if job is not None else None
    role_list = None
    if roles and models_available():
        try:
            role_list = predict_roles(text, 3, cleaned=clean)
        except Exception:
            role_list = None
    return {
        "profile": profile, "skills_found": extract_skills(text), "ats": ats, "match": m,
        "roles": role_list, "advice": build_advice(profile, ats, m),
    }


def analyze(resume_text: str, jd_text: str = "") -> dict:
    """Convenience wrapper: one CV, optional job description given as text."""
    job = prepare_job(jd_text.strip()) if jd_text and jd_text.strip() else None
    return analyze_resume(resume_text, job)
