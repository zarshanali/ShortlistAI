"""Pull structured facts out of raw resume / job-description text:
contact info, sections, years of experience and education level.

Deliberately NOT extracted: name, gender, age, photo, address. The scoring never
sees them, which keeps the screening focused on skills and experience.
"""
import re
from datetime import date

# ---------------------------------------------------------------- contacts
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
_LINKEDIN = re.compile(r"linkedin\.com/[^\s,;]+", re.I)
_GITHUB = re.compile(r"github\.com/[^\s,;]+", re.I)


def extract_contacts(text):
    phones = [p.strip() for p in _PHONE.findall(text)
              if 10 <= len(re.sub(r"\D", "", p)) <= 15]
    return {
        "email": bool(_EMAIL.search(text)),
        "phone": bool(phones),
        "linkedin": bool(_LINKEDIN.search(text)),
        "github": bool(_GITHUB.search(text)),
    }


# ---------------------------------------------------------------- sections
SECTION_KEYWORDS = {
    "summary": ["summary", "objective", "profile", "about me", "career objective",
                "professional summary"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment history", "work history", "internship", "internships"],
    "education": ["education", "academic background", "qualifications",
                  "educational qualification", "academics"],
    "skills": ["skills", "technical skills", "key skills", "core competencies",
               "skill set", "technologies"],
    "projects": ["projects", "academic projects", "personal projects"],
    "certifications": ["certifications", "certificates", "courses"],
    "achievements": ["achievements", "awards", "accomplishments", "honors"],
}


def _heading(line):
    norm = re.sub(r"[^a-z ]", " ", line.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    if not norm or len(norm.split()) > 4:
        return None
    for name, keys in SECTION_KEYWORDS.items():
        for k in keys:
            if norm == k or norm.startswith(k + " ") or norm.endswith(" " + k):
                return name
    return None


def split_sections(text):
    """Return {section_name: text}. Lines before the first heading go to 'header'."""
    sections, current, buf = {}, "header", []
    for line in text.splitlines():
        h = _heading(line)
        if h:
            sections[current] = sections.get(current, "") + "\n".join(buf) + "\n"
            current, buf = h, []
        else:
            buf.append(line)
    sections[current] = sections.get(current, "") + "\n".join(buf)
    return sections


def detect_sections(text):
    """Set of section names present (by heading, or by the word appearing at all
    for single-block resumes that have no line breaks)."""
    found = {k for k in split_sections(text) if k != "header"}
    low = text.lower()
    for k in ("experience", "education", "skills", "projects"):
        if k not in found and re.search(r"\b" + k + r"\b", low):
            found.add(k)
    return found


# ---------------------------------------------------------------- experience
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*,?\s*"
_RANGE = re.compile(
    r"(?:" + _MONTH + r")?((?:19|20)\d{2})\s*(?:-|–|—|to)\s*(?:" + _MONTH +
    r")?((?:19|20)\d{2}|present|current|now|till date|ongoing)", re.I)
_EXPLICIT_A = re.compile(
    r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:[a-z]+\s+){0,4}?"
    r"(?:experience|exp)\b")
_EXPLICIT_B = re.compile(
    r"experience\s*(?:of|:|-)?\s*(?:over\s+|around\s+|about\s+)?(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)")


def years_of_experience(text):
    """Best-effort total years of work experience (float)."""
    low = text.lower()
    explicit = [float(m) for m in _EXPLICIT_A.findall(low) + _EXPLICIT_B.findall(low)]
    explicit = [e for e in explicit if e <= 45]
    if explicit:
        return max(explicit)

    # otherwise add up date ranges - but only inside the experience section so
    # that education years (2016-2020) are not counted as work.
    secs = split_sections(text)
    scope = secs.get("experience") or "\n".join(
        l for k, v in secs.items() if k not in ("education", "certifications")
        for l in v.splitlines())
    this_year = date.today().year
    spans = []
    for a, b in _RANGE.findall(scope):
        start = int(a)
        end = this_year if not b.isdigit() else int(b)
        if 0 <= end - start <= 40 and end >= start:
            spans.append((start, end))
    if not spans:
        return 0.0
    spans.sort()
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return float(sum(e - s for s, e in merged))


def required_years(jd_text):
    """Years of experience a job description asks for (None if not stated)."""
    low = jd_text.lower()
    for m in re.finditer(r"(\d{1,2})\s*\+?\s*(?:(?:to|-)\s*\d{1,2}\s*)?(?:years?|yrs?)", low):
        ctx = low[max(0, m.start() - 60): m.end() + 60]
        if "experience" in ctx or "exp" in ctx:
            return float(m.group(1))
    return None


# ---------------------------------------------------------------- education
EDU_LEVELS = [
    (4, "PhD", r"\b(?:ph\.?d|doctorate|doctoral)\b"),
    (3, "Master's", r"\b(?:master'?s?|m\.sc|msc|m\.tech|mtech|m\.s\b|ms in|mba|m\.e\b|mca|m\.com)"),
    (2, "Bachelor's", r"\b(?:bachelor'?s?|b\.sc|bsc|b\.tech|btech|b\.e\b|bca|bba|b\.com|b\.a\b|undergraduate|bs in)"),
    (1, "Diploma", r"\b(?:diploma|associate degree)\b"),
    (0, "High school", r"\b(?:high school|intermediate|hsc|ssc|matriculation)\b"),
]


def education_level(text, lowest=False):
    """(level_number, label) of the highest education found, or (None, None).

    lowest=True is used for job descriptions: "Bachelor's or Master's" means a
    Bachelor's is enough, so we take the lowest level mentioned.
    """
    low = text.lower()
    hits = [(lvl, label) for lvl, label, pat in EDU_LEVELS if re.search(pat, low)]
    if not hits:
        return None, None
    return min(hits) if lowest else max(hits)


def build_profile(text):
    """Everything we can say about a resume without a job description."""
    lvl, label = education_level(text)
    return {
        "years_experience": years_of_experience(text),
        "education_level": lvl,
        "education_label": label,
        "contacts": extract_contacts(text),
        "sections": sorted(detect_sections(text)),
        "word_count": len(text.split()),
    }
