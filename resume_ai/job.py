"""Runs a whole screening in a BACKGROUND THREAD; the page only reads the job's state
(so reloading the browser never loses a run)."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from . import exporters
from .analyzer import analyze_resume
from .config import OUT, READ_WORKERS
from .matcher import JobSpec, prepare_job
from .predictor import models_available, predict_roles
from .readers import ReadError, read_file

WEIGHT = {"queued": 0.0, "reading": 0.15, "analysing": 0.6, "done": 1.0, "failed": 1.0, "skipped": 1.0}
LABEL = {"queued": "⏳ Queued", "reading": "📖 Reading", "analysing": "🧭 Analysing", "done": "✅ Done",
         "failed": "❌ Failed", "skipped": "↪ Duplicate"}
COLOR = {"queued": "#cbd5e1", "reading": "#38bdf8", "analysing": "#6366f1", "done": "#10b981",
         "failed": "#ef4444", "skipped": "#f59e0b"}
BUSY = ("reading", "analysing")


class Job:
    def __init__(self, items: List[Tuple[str, bytes]], jd_text: str, cfg: dict, embedder=None):
        self.items = dict(items)                         # file name -> bytes (released as soon as it is read)
        self.jd_text, self.cfg, self.embedder = (jd_text or "").strip(), cfg, embedder
        self.files = {n: dict(name=n, status="queued", words=0, score=None, sec=0.0, error="")
                      for n in self.items}
        self.aliases = {n: f"Candidate {i:03d}" for i, n in enumerate(self.items, 1)}
        self.results: Dict[str, dict] = {}
        self.timing: Dict[str, float] = {}
        self.meta: dict = {}
        self.phase, self.frac, self.error = "Starting ...", 0.0, ""
        self.t0, self.t1, self.out_dir, self.zip = time.time(), None, "", b""
        self.cancel, self.lock = threading.Event(), threading.RLock()
        threading.Thread(target=self._main, daemon=True, name="cv-job").start()

    done = property(lambda self: self.t1 is not None)
    elapsed = property(lambda self: (self.t1 or time.time()) - self.t0)

    def upd(self, name: str, **kw) -> None:
        with self.lock:
            self.files[name].update(kw)

    def say(self, text: str, frac: float) -> None:
        self.phase, self.frac = text, max(self.frac, min(frac, 0.99))

    def snapshot(self) -> List[dict]:
        with self.lock:
            return [dict(f) for f in self.files.values()]

    # ------------------------------------------------------------------
    def _main(self) -> None:
        try:
            self._run()
            if self.results:
                self._save()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            for n, f in self.files.items():
                if f["status"] not in ("done", "failed", "skipped"):
                    self.upd(n, status="failed", error=self.error)
        finally:
            self.t1, self.phase, self.frac = time.time(), "Done", 1.0

    def _read_one(self, name: str, ocr: bool):
        if self.cancel.is_set():
            return name, None, "stopped by the user"
        self.upd(name, status="reading")
        try:
            r = read_file(name, self.items[name], ocr=ocr)
            return name, r, ""
        except ReadError as e:
            return name, None, str(e)
        except Exception as e:
            return name, None, f"{type(e).__name__}: {e}"
        finally:
            self.items[name] = b""                        # free the memory

    def _run(self) -> None:
        cfg, t = self.cfg, time.time()
        spec: Optional[JobSpec] = prepare_job(self.jd_text) if self.jd_text else None
        if spec and cfg.get("roles", True) and models_available():
            try:
                spec.role = predict_roles(self.jd_text, 1, with_skills=False)[0]["category"]
            except Exception:
                pass
        self.meta = dict(
            has_job=spec is not None, required=spec.required if spec else [], preferred=spec.preferred if spec else [],
            need_years=spec.need_years if spec else None, need_education=spec.need_label if spec else None,
            job_role=spec.role if spec else None, weights=cfg.get("weights"),
            shortlist=cfg.get("shortlist"), review=cfg.get("review"),
            semantic=bool(self.embedder and getattr(self.embedder, "model", None)),
        )

        # ---- 1. read all files in parallel
        self.say(f"Reading {len(self.items)} files ...", 0.02)
        texts: Dict[str, str] = {}
        notes: Dict[str, str] = {}
        kinds: Dict[str, str] = {}
        finished = 0
        with ThreadPoolExecutor(max_workers=min(READ_WORKERS, max(1, len(self.items)))) as pool:
            futs = [pool.submit(self._read_one, n, cfg.get("ocr", True)) for n in list(self.items)]
            for fu in as_completed(futs):
                n, r, err = fu.result()
                finished += 1
                self.say(f"Reading files ... {finished}/{len(self.items)}", 0.02 + 0.4 * finished / len(self.items))
                if r is None:
                    self.upd(n, status="failed", error=err)
                    continue
                texts[n], notes[n], kinds[n] = r.text, r.warning, r.kind
                self.upd(n, status="analysing", words=len(r.text.split()))
        self.timing["read"] = time.time() - t
        if self.cancel.is_set():
            for n, f in self.files.items():
                if f["status"] not in ("done", "failed", "skipped"):
                    self.upd(n, status="failed", error="stopped by the user")
            return

        # keep the original upload order, drop exact duplicates
        order = [n for n in self.items if n in texts]
        seen: Dict[str, str] = {}
        for n in order:
            key = hashlib.md5(re.sub(r"\W+", "", texts[n].lower()).encode()).hexdigest()
            if key in seen:
                self.upd(n, status="skipped", error=f"Same content as {seen[key]}")
                texts.pop(n)
            else:
                seen[key] = n
        order = [n for n in order if n in texts]
        if not order:
            return

        # ---- 2. optional meaning-based similarity, all CVs in one batch
        sims: Dict[str, float] = {}
        if spec and self.embedder is not None and getattr(self.embedder, "model", None) is not None:
            t = time.time()
            self.say(f"Embedding {len(order)} CVs ({self.embedder.name}) ...", 0.45)
            E = self.embedder.encode_docs([self.jd_text] + [texts[n] for n in order])
            if E is not None:
                sims = {n: float(E[i + 1] @ E[0]) for i, n in enumerate(order)}
            self.timing["embed"] = time.time() - t

        # ---- 3. analyse every CV
        t = time.time()
        for k, n in enumerate(order):
            if self.cancel.is_set():
                break
            self.say(f"Analysing {n} ({k + 1}/{len(order)}) ...", 0.5 + 0.45 * k / len(order))
            t1 = time.time()
            try:
                res = analyze_resume(texts[n], spec, cfg.get("weights"), sims.get(n), cfg.get("roles", True))
            except Exception as e:
                self.upd(n, status="failed", error=f"{type(e).__name__}: {e}")
                continue
            res.update(name=n, alias=self.aliases[n], kind=kinds[n], note=notes[n], words=len(texts[n].split()))
            self.results[n] = res
            self.upd(n, status="done", sec=time.time() - t1, error=notes[n],
                     score=res["match"]["score"] if res["match"] else None)
        self.timing["analyse"] = time.time() - t
        if self.cancel.is_set():
            for n, f in self.files.items():
                if f["status"] not in ("done", "failed", "skipped"):
                    self.upd(n, status="failed", error="stopped by the user")
        self.timing["total"] = sum(self.timing.values())

    def _save(self) -> None:
        d = OUT / time.strftime("%Y%m%d-%H%M%S")
        d.mkdir(parents=True, exist_ok=True)
        self.out_dir = str(d)
        rs = exporters.rows(self.results, self.cfg.get("shortlist", 65), self.cfg.get("review", 40))
        (d / "ranking.csv").write_text(exporters.ranking_csv(rs), encoding="utf-8")
        self.zip = exporters.build_zip(self.results, rs)
        (d / "reports.zip").write_bytes(self.zip)
        meta = {**self.meta, "seconds": round(self.elapsed, 1), "n_files": len(self.files)}
        (d / "results.json").write_text(json.dumps({"meta": meta, "results": self.results}), encoding="utf-8")
