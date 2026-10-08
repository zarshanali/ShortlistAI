"""End-to-end: many files through the background job, including bad and duplicate ones."""
import os
import tempfile
import time
import zipfile
import io
from pathlib import Path

from resume_ai import exporters
from resume_ai.job import Job

S = Path(__file__).resolve().parent.parent / "samples"
CFG = dict(weights=None, roles=True, ocr=False, shortlist=65, review=40)


def _run(items, jd, cfg=CFG):
    os.chdir(tempfile.mkdtemp())                       # outputs/ is written to the working folder
    job = Job(items, jd, cfg)
    t0 = time.time()
    while not job.done and time.time() - t0 < 120:
        time.sleep(0.05)
    assert job.done and not job.error, job.error
    return job


def _cv(i):
    base = (S / "resume_data_scientist.txt").read_text(encoding="utf-8")
    return (base + f"\nPersonal project number {i}.\n").encode()


def test_many_files_with_failures_and_duplicates():
    items = [(f"cv_{i:03d}.txt", _cv(i)) for i in range(60)]
    items += [("web.txt", (S / "resume_web_developer.txt").read_bytes()),
              ("copy_of_web.txt", (S / "resume_web_developer.txt").read_bytes()),
              ("empty.txt", b""), ("junk.bin", bytes(range(256)) * 4)]
    job = _run(items, (S / "jd_data_scientist.txt").read_text(encoding="utf-8"))
    status = {f["name"]: f["status"] for f in job.snapshot()}
    assert sum(s == "done" for s in status.values()) == 61
    assert status["copy_of_web.txt"] == "skipped"                      # exact duplicate
    assert status["empty.txt"] == status["junk.bin"] == "failed"       # one bad file never stops the rest
    rows = exporters.rows(job.results)
    assert [r["rank"] for r in rows] == list(range(1, 62))
    assert rows[0]["score"] >= rows[-1]["score"] and rows[-1]["name"] == "web.txt"
    assert len({r["alias"] for r in rows}) == len(rows)                # blind-screening aliases are unique


def test_outputs_are_saved_and_exportable():
    job = _run([("a.txt", _cv(1)), ("b.txt", _cv(2))], (S / "jd_data_scientist.txt").read_text(encoding="utf-8"))
    out = Path(job.out_dir)
    assert {p.name for p in out.iterdir()} == {"ranking.csv", "reports.zip", "results.json"}
    rows = exporters.rows(job.results)
    csv_text = exporters.ranking_csv(rows, blind=True)
    assert csv_text.startswith("Rank,CV,Match %") and "Candidate 001" in csv_text and "a.txt" not in csv_text
    with zipfile.ZipFile(io.BytesIO(exporters.build_zip(job.results, rows))) as z:
        assert "ranking.csv" in z.namelist() and any(n.startswith("reports/") for n in z.namelist())
    assert exporters.load_last_run()["results"].keys() == job.results.keys()


def test_works_without_a_job_description():
    job = _run([("a.txt", _cv(1))], "")
    r = job.results["a.txt"]
    assert r["match"] is None and r["ats"]["score"] > 0 and r["skills_found"]
    assert exporters.rows(job.results)[0]["suggestion"] == "-"


def test_zip_upload_is_unpacked_by_the_app_helper():
    from resume_ai.readers import expand_zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(25):
            z.writestr(f"sub/{i}.txt", _cv(i))
    assert len(expand_zip(buf.getvalue(), 500)) == 25
