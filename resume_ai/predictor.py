"""Load the trained job-category model and predict the best-fit roles for a resume."""
from __future__ import annotations

import threading
from typing import List, Optional

import joblib

from .config import MODELS_DIR
from .preprocessing import clean_text
from .skills import match_skills

_lock = threading.Lock()
_cache: dict = {}


def models_available() -> bool:
    return (MODELS_DIR / "tfidf.pkl").exists() and (MODELS_DIR / "model.pkl").exists()


def _load():
    with _lock:
        if not _cache:
            if not models_available():
                raise FileNotFoundError("Model files not found. Run `python train.py` first.")
            _cache["tfidf"] = joblib.load(MODELS_DIR / "tfidf.pkl")
            _cache["model"] = joblib.load(MODELS_DIR / "model.pkl")
    return _cache["tfidf"], _cache["model"]


def predict_roles(text: str, top_n: int = 3, cleaned: Optional[str] = None, with_skills: bool = True) -> List[dict]:
    """[{category, confidence, matched_skills, missing_skills}, ...] best first."""
    tfidf, model = _load()
    vec = tfidf.transform([cleaned if cleaned is not None else clean_text(text)])
    classes = list(model.classes_)
    if hasattr(model, "predict_proba"):
        ranked = sorted(zip(classes, model.predict_proba(vec)[0]), key=lambda x: x[1], reverse=True)[:top_n]
    else:
        ranked = [(model.predict(vec)[0], 1.0)]
    out = []
    for cat, prob in ranked:
        matched, missing = match_skills(text, cat) if with_skills else ([], [])
        out.append({"category": cat, "confidence": round(float(prob) * 100, 1),
                    "matched_skills": matched, "missing_skills": missing})
    return out
