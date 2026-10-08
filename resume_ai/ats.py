"""ATS-readability check: would an Applicant Tracking System (and a human skimming
for 10 seconds) be able to find the important things in this resume?

Score is out of 100. Every check carries a plain-language tip.
"""
import re

from .extractor import detect_sections, extract_contacts

ACTION_VERBS = {
    "led", "developed", "built", "designed", "implemented", "managed", "created",
    "improved", "increased", "reduced", "delivered", "launched", "optimized",
    "optimised", "automated", "analyzed", "analysed", "deployed", "achieved",
    "coordinated", "trained", "negotiated", "engineered", "migrated",
    "collaborated", "mentored", "streamlined", "architected", "resolved",
    "generated", "spearheaded", "established", "maintained", "executed",
    "integrated", "tested", "researched", "presented",
}
_NUMBER_WINS = re.compile(
    r"\d+(?:\.\d+)?\s*%|[$€£₹]\s?\d|\b\d+(?:\.\d+)?\s*[kKmMx]\b|"
    r"\b\d{2,}\+?\s+(?:users|clients|customers|projects|records|models|members|"
    r"people|applications|apps|systems|reports|tickets|leads|candidates)\b")
_BULLET = re.compile(r"^\s*[•●▪◦·*\-–>]\s+", re.M)


def _status(points, max_points):
    if points >= max_points:
        return "pass"
    return "partial" if points > 0 else "fail"


def ats_check(text):
    contacts = extract_contacts(text)
    sections = detect_sections(text)
    words = text.split()
    n_words = len(words)
    low = text.lower()
    checks = []

    def add(name, points, max_points, tip):
        checks.append({"name": name, "points": points, "max": max_points,
                       "status": _status(points, max_points), "tip": tip})

    add("Email address", 10 if contacts["email"] else 0, 10,
        "Add a professional email at the top - recruiters and ATS tools look for it first.")
    add("Phone number", 10 if contacts["phone"] else 0, 10,
        "Add a phone number with country code.")
    add("LinkedIn or GitHub link", 5 if (contacts["linkedin"] or contacts["github"]) else 0, 5,
        "Link your LinkedIn or GitHub (or portfolio) so employers can verify your work.")

    for key, label in (("experience", "Experience"), ("education", "Education"),
                       ("skills", "Skills")):
        add(f"{label} section", 10 if key in sections else 0, 10,
            f"Add a clearly titled '{label}' heading - ATS parsers split resumes by heading.")
    add("Projects or certifications",
        5 if ({"projects", "certifications"} & sections) else 0, 5,
        "Add a Projects or Certifications section - it is the best way to show skills "
        "when work experience is short.")

    if 250 <= n_words <= 1100:
        pts = 10
    elif 150 <= n_words < 250 or 1100 < n_words <= 1500:
        pts = 5
    else:
        pts = 0
    add(f"Length ({n_words} words)", pts, 10,
        "Aim for roughly 300-900 words (1-2 pages). Too short looks thin; too long gets skimmed.")

    wins = len(_NUMBER_WINS.findall(text))
    add(f"Measurable results ({wins} found)", 10 if wins >= 3 else 5 if wins >= 1 else 0, 10,
        "Add numbers to your achievements, e.g. 'cut report time by 40%' or "
        "'built a model used by 200+ customers'.")

    verbs = sum(1 for w in re.findall(r"[a-z]+", low) if w in ACTION_VERBS)
    add(f"Action verbs ({verbs} found)", 10 if verbs >= 6 else 5 if verbs >= 3 else 0, 10,
        "Start bullet points with strong verbs: built, led, automated, reduced, deployed...")

    bullets = len(_BULLET.findall(text))
    lines = len([l for l in text.splitlines() if l.strip()])
    add("Scannable structure", 5 if bullets >= 4 or lines >= 25 else 0, 5,
        "Use short bullet points instead of long paragraphs.")

    pronouns = len(re.findall(r"\b(?:i|my|me)\b", low))
    add("Professional tone", 5 if pronouns <= 4 else 0, 5,
        "Avoid 'I' and 'my' - write 'Built X' instead of 'I built X'.")

    score = sum(c["points"] for c in checks)
    return {"score": score, "checks": checks}
