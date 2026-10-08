"""Generate a PowerPoint presentation for the
AI Resume Analyzer & Job Match project (v2).

Run:  python make_presentation.py
Output:  presentation/AI_Resume_Screening_Presentation.pptx
"""
import json
import os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# ---- theme ----
BLUE = RGBColor(0x2B, 0x4E, 0xFF)
DARK = RGBColor(0x1F, 0x24, 0x30)
GREY = RGBColor(0x5A, 0x62, 0x75)
GREEN = RGBColor(0x1A, 0x7F, 0x48)
ORANGE = RGBColor(0xB5, 0x65, 0x1D)
LIGHT = RGBColor(0xF4, 0xF6, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def _set(run, size, color=DARK, bold=False):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = "Segoe UI"


def textbox(slide, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    return tf


def header(slide, title):
    """Blue accent bar + slide title."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.55),
                                 Inches(0.18), Inches(0.7))
    bar.fill.solid(); bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()
    tf = textbox(slide, Inches(0.95), Inches(0.5), Inches(11.8), Inches(0.9))
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = title; _set(r, 30, DARK, True)


def bullets_slide(title, items):
    s = prs.slides.add_slide(BLANK)
    header(s, title)
    tf = textbox(s, Inches(0.95), Inches(1.6), Inches(11.5), Inches(5.4))
    for i, item in enumerate(items):
        text, level = item if isinstance(item, tuple) else (item, 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = level
        p.space_after = Pt(10)
        bullet = "   - " if level else "•  "
        r = p.add_run(); r.text = bullet + text
        _set(r, 22 if level == 0 else 18, DARK if level == 0 else GREY,
             bold=False)
    return s


def title_slide():
    s = prs.slides.add_slide(BLANK)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    band.fill.solid(); band.fill.fore_color.rgb = BLUE
    band.line.fill.background()

    tf = textbox(s, Inches(1.0), Inches(2.2), Inches(11.3), Inches(2.2))
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "AI Resume Analyzer &\nJob Match System"
    _set(r, 40, WHITE, True)
    p2 = tf.add_paragraph()
    r2 = p2.add_run(); r2.text = "Match score  |  Skill gaps  |  ATS check  |  Recruiter ranking"
    _set(r2, 22, RGBColor(0xDD, 0xE4, 0xFF))

    tf2 = textbox(s, Inches(1.0), Inches(6.1), Inches(11.3), Inches(1.0))
    p3 = tf2.paragraphs[0]
    r3 = p3.add_run(); r3.text = "Semester Project  •  Python  •  Scikit-learn  •  Streamlit"
    _set(r3, 16, RGBColor(0xDD, 0xE4, 0xFF))


def box(slide, left, top, width, height, text, fill, txt_color=WHITE, size=13):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = fill
    tf = shp.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text; _set(r, size, txt_color, True)
    return shp


def arrow_down(slide, cx, top):
    a = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, cx - Inches(0.12), top,
                               Inches(0.24), Inches(0.3))
    a.fill.solid(); a.fill.fore_color.rgb = GREY; a.line.fill.background()


def architecture_slide():
    s = prs.slides.add_slide(BLANK)
    header(s, "System Architecture")
    steps = [
        ("1. Upload CVs (PDF / DOCX / DOC / TXT / ZIP ...) + Job Description", BLUE),
        ("2. Text Extraction", BLUE),
        ("3. Text Preprocessing (clean, stopwords, lemmatize)", BLUE),
        ("4. Extract skills, experience, education + TF-IDF features", BLUE),
        ("5. ML job-category model + 4-part match score", BLUE),
        ("6. Skill-gap analysis + ATS check + advice", GREEN),
        ("7. Streamlit UI: live progress, ranking, filters, CSV / ZIP", GREEN),
    ]
    cx = SW // 2
    top = Inches(1.55)
    bw, bh = Inches(6.6), Inches(0.55)
    gap = Inches(0.28)
    for i, (text, color) in enumerate(steps):
        box(s, cx - bw // 2, top, bw, bh, text, color, size=14)
        top = top + bh
        if i < len(steps) - 1:
            arrow_down(s, cx, top)
            top = top + gap


def _load_metrics():
    """Use the real numbers saved by train.py; fall back to the original v1 numbers."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "metrics.json")
    try:
        with open(path) as fh:
            m = json.load(fh)
        lr = m["models"]["Logistic Regression"]["test_accuracy"] * 100
        nb = m["models"]["Naive Bayes"]["test_accuracy"] * 100
        return lr, nb, True
    except Exception:
        return 99.5, 96.9, False


def chart_slide():
    lr, nb, real = _load_metrics()
    s = prs.slides.add_slide(BLANK)
    header(s, "Algorithm Comparison (Test Accuracy)")
    data = CategoryChartData()
    data.categories = ["Logistic Regression", "Naive Bayes"]
    data.add_series("Accuracy %", (round(lr, 1), round(nb, 1)))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                            Inches(2.3), Inches(1.7), Inches(8.7), Inches(4.8), data)
    chart = gf.chart
    chart.has_legend = False
    chart.has_title = False
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.number_format = '0.0"%"'
    plot.data_labels.number_format_is_linked = False
    plot.data_labels.font.size = Pt(14)
    plot.data_labels.font.bold = True
    val_axis = chart.value_axis
    val_axis.minimum_scale = max(0, int(min(lr, nb)) - 10)
    val_axis.maximum_scale = 100
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = BLUE
    tf = textbox(s, Inches(2.3), Inches(6.6), Inches(8.7), Inches(0.6))
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("Measured on unseen resumes after removing duplicates (models/metrics.json)."
              if real else
              "Run train.py to replace these placeholder numbers with your measured results.")
    _set(r, 14, GREY)


def results_placeholder_slide():
    s = prs.slides.add_slide(BLANK)
    header(s, "Results / Output")
    # dashed placeholder box for the screenshot
    ph = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.2), Inches(1.7),
                            Inches(10.9), Inches(4.6))
    ph.fill.solid(); ph.fill.fore_color.rgb = WHITE
    ph.line.color.rgb = GREY
    ph.line.dash_style = 2  # dashed
    tf = ph.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = ("[ Paste your app screenshot here ]\n\n"
              "Right-click this box -> delete, then Insert > Picture\n"
              "and add your result screenshot.")
    _set(r, 16, GREY)
    cap = textbox(s, Inches(1.2), Inches(6.5), Inches(10.9), Inches(0.7))
    pc = cap.paragraphs[0]; pc.alignment = PP_ALIGN.CENTER
    rc = pc.add_run()
    rc.text = ("Example: a Data Science CV -> 87.7% Data Science, with matched "
               "skills (green) and skills to focus on (orange).")
    _set(rc, 13, GREY)


def closing_slide():
    s = prs.slides.add_slide(BLANK)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    band.fill.solid(); band.fill.fore_color.rgb = BLUE; band.line.fill.background()
    tf = textbox(s, Inches(1.0), Inches(2.8), Inches(11.3), Inches(2.0),
                 anchor=MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Thank You"; _set(r, 48, WHITE, True)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = "Questions?"; _set(r2, 24, RGBColor(0xDD, 0xE4, 0xFF))


# ---------------- build deck ----------------
title_slide()

bullets_slide("Introduction", [
    "Recruiters receive hundreds of resumes for one job opening.",
    "Job seekers rarely know why their CV is rejected.",
    "This project reads a CV and a job description and explains the match.",
    "It shows the match %, the missing skills and what to fix first.",
])

bullets_slide("Problem Statement", [
    "Manual resume screening is slow, inconsistent and tiring.",
    "Keyword-only tools miss good candidates and reward keyword stuffing.",
    "Candidates get a rejection, not a reason.",
    "We need a fast, explainable and fair first-pass screening tool.",
])

bullets_slide("Objectives", [
    "Extract text from many file formats (PDF, DOCX, DOC, RTF, ODT, TXT, images, ZIP).",
    "Compute an explainable match % between a CV and a job description.",
    "Find the skills a job asks for and which ones the CV is missing.",
    "Check ATS readability and give plain-language improvement tips.",
    "Let recruiters rank hundreds of CVs for one job and export the result.",
    "Predict the best-fit job category with a trained ML model.",
])

bullets_slide("What Is New In Version 3", [
    "Match score = skills 50% + text similarity 25% + experience 15% + education 10%.",
    "Reads the skills from the job description itself (required vs preferred).",
    "ATS readability check out of 100 with a tip for every failed check.",
    "Recruiter mode: rank up to 50 CVs and download a CSV.",
    "Years of experience and education level are extracted automatically.",
    "Bulk upload in the browser: PDF, DOCX, DOC, RTF, ODT, TXT, scanned images, ZIP.",
    "Background processing with live progress; filters, blind screening, CSV/ZIP export.",
])

bullets_slide("Tools & Technologies", [
    "Programming Language: Python",
    ("Libraries: Pandas, NumPy, Scikit-learn, NLTK", 1),
    ("File reading: pypdf, DOCX/ODT/RTF readers, antiword, tesseract OCR", 1),
    "Machine Learning: Logistic Regression, Naive Bayes (TF-IDF features)",
    "NLP: Tokenization, Stopword removal, Lemmatization, TF-IDF, Cosine similarity",
    "Optional: sentence-transformers (MiniLM) for meaning-based similarity",
    "Web: Streamlit (upload, live progress and results in the browser). Runs on CPU.",
])

bullets_slide("Dataset", [
    "Source: Kaggle - 'Updated Resume Dataset'.",
    "962 rows across 25 job categories (Category + Resume text).",
    "Contains many exact duplicates - removed before train/test split.",
    "Used to train the job-category classifier.",
    "The match score itself needs no training data: it is rule + similarity based.",
])

architecture_slide()

bullets_slide("How The Match Score Works", [
    "Skills (50%): skills in the JD found in the CV. Required = 1.0, preferred = 0.5.",
    "Text similarity (25%): TF-IDF cosine, plus embeddings when installed.",
    "Experience (15%): years found in the CV vs years the JD asks for.",
    "Education (10%): degree level in the CV vs the level the JD asks for.",
    "If the JD does not mention a part, it is skipped and weights are re-scaled.",
    "Every number is shown to the user - nothing is a black box.",
])

bullets_slide("Machine Learning Methodology", [
    "Step 1: Clean text (lowercase, remove symbols, stopwords, lemmatize).",
    "Step 2: Remove duplicate resumes, then split 80% train / 20% test.",
    "Step 3: TF-IDF features (1,500 terms, unigrams + bigrams).",
    "Step 4: Compare Logistic Regression and Naive Bayes with 5-fold cross-validation.",
    "Step 5: Pick the winner by CV score, evaluate once on the test set.",
    "Step 6: Save the model; use it to suggest best-fit job categories.",
])

chart_slide()

results_placeholder_slide()

bullets_slide("Recruiter Mode & ATS Check", [
    "Upload up to 500 CVs (or one ZIP) + one job description.",
    "Ranked table: match %, skills matched, years, education, ATS score, best-fit role.",
    "Labels: Shortlist / Review / Low match - a human makes the final call.",
    "Download the ranking as a CSV file.",
    "ATS check: contact info, sections, length, measurable results, action verbs.",
])

bullets_slide("Evaluation Metrics", [
    "Accuracy, Precision, Recall, F1-score for the job-category model.",
    "Cross-validation score used to choose between models.",
    "Cosine similarity and the 4-part match score for CV vs job description.",
    "Duplicates removed first, so results reflect unseen resumes.",
    "Expect a lower number than the old ~99% - it is the honest one.",
])

bullets_slide("Responsible AI", [
    "Name, photo, age, gender and address are never read or scored.",
    "Output is a shortlist to review, not an automatic rejection.",
    "Every score is explained: which skills matched, which are missing.",
    "Files are processed in memory and are not stored.",
    "Known bias risk: the skills list and dataset reflect what the data contains.",
])

bullets_slide("Advantages & Limitations", [
    "Advantages:",
    ("Fast, explainable and works for both job seekers and recruiters.", 1),
    ("Gives actionable advice, not just a number.", 1),
    ("Runs on a laptop; no GPU or paid API.", 1),
    "Limitations:",
    ("Skill vocabulary is hand-curated and misses unlisted skills.", 1),
    ("Scanned (image) PDFs are not readable without OCR.", 1),
    ("Dataset has only 25 job categories; years/education use pattern matching.", 1),
])

bullets_slide("Future Enhancements", [
    "OCR for scanned resumes.",
    "Learn the skill vocabulary automatically from many job postings.",
    "Database + recruiter dashboard with saved jobs and candidates.",
    "LLM-based rewriting suggestions and interview-question generation.",
    "Deploy online (Docker / cloud) and add multi-language support.",
])

bullets_slide("Conclusion", [
    "The system compares a CV with a job and explains the match.",
    "It tells job seekers exactly what to improve, and recruiters whom to review first.",
    "It uses classical ML + NLP only and runs on CPU.",
    "Evaluation is honest: duplicates removed, cross-validated model choice.",
    "The project is practical and easy to extend.",
])

closing_slide()

# ---------------- save ----------------
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presentation")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "AI_Resume_Analyzer_Presentation.pptx")
prs.save(OUT)
print(f"Saved presentation with {len(prs.slides._sldIdLst)} slides to:\n{OUT}")
