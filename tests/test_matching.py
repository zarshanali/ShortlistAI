"""Skills, experience/education extraction, the match score and the ATS check."""
from pathlib import Path

from resume_ai.ats import ats_check
from resume_ai.extractor import education_level, required_years, years_of_experience
from resume_ai.matcher import match, prepare_job
from resume_ai.skills import extract_skills

S = Path(__file__).resolve().parent.parent / "samples"
read = lambda name: (S / name).read_text(encoding="utf-8")       # noqa: E731


def test_skill_aliases_and_ambiguous_letters():
    found = extract_skills("ML, sklearn, CI/CD, Node.js, C#, k8s, team player, R programming")
    for s in ("machine learning", "scikit-learn", "ci cd", "node js", "c#", "kubernetes", "teamwork", "r"):
        assert s in found, s
    assert "r" not in extract_skills("Our R&D team and the letter R")
    assert "java" not in extract_skills("Strong JavaScript skills")        # no partial-word matches


def test_job_description_required_vs_preferred():
    spec = prepare_job(read("jd_data_scientist.txt"))
    assert "python" in spec.required and "docker" in spec.required
    assert "kubernetes" in spec.preferred and "kubernetes" not in spec.required
    assert spec.need_years == 3 and spec.need_label == "Bachelor's"        # "Bachelor's or Master's" -> lowest


def test_years_of_experience():
    assert years_of_experience("Over 5 years of experience in sales") == 5
    text = "EXPERIENCE\nAnalyst, Acme (2020 - 2022)\nEDUCATION\nB.Sc. Physics (2012 - 2016)"
    assert years_of_experience(text) == 2                                    # study years are not work years
    assert required_years("We need 3+ years of experience") == 3
    assert education_level("M.Sc. in Statistics")[1] == "Master's"


def test_better_cv_scores_higher_and_explains_why():
    job = prepare_job(read("jd_data_scientist.txt"))
    good = match(read("resume_data_scientist.txt"), job)
    weak = match(read("resume_web_developer.txt"), job)
    fresher = match(read("resume_fresher.txt"), job)
    assert good["score"] > 70 > weak["score"] > fresher["score"]
    assert good["verdict"] == "Excellent match" and not good["missing_required"]
    assert "python" in weak["missing_required"]


def test_parts_the_job_does_not_mention_are_skipped():
    m = match(read("resume_data_scientist.txt"), "We need someone who knows Python and SQL.")
    parts = {b["key"]: b["score"] for b in m["breakdown"]}
    assert parts["experience"] is None and parts["education"] is None
    assert sum(b["weight"] for b in m["breakdown"]) in (99, 100, 101)       # rounding only


def test_custom_weights_change_the_score():
    job = prepare_job(read("jd_data_scientist.txt"))
    cv = read("resume_web_developer.txt")
    skills_only = match(cv, job, weights={"skills": 1, "text": 0, "experience": 0, "education": 0})
    assert skills_only["score"] < 20


def test_ats_check_rewards_a_complete_cv():
    good, bare = ats_check(read("resume_data_scientist.txt")), ats_check(read("resume_fresher.txt"))
    assert good["score"] >= 80 and bare["score"] < 40
    assert all({"name", "status", "tip"} <= set(c) for c in good["checks"])
