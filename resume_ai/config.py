"""All settings in one place."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path("outputs")                                   # every run is saved in outputs/<timestamp>/
MODELS_DIR = ROOT / "models"

MAX_DOCS = int(os.environ.get("CV_MAX_DOCS", 500))      # most CVs per run (raise it if you have the RAM)
MAX_FILE_MB = 50                                        # biggest single file
MAX_ZIP_TOTAL_MB = 800                                  # biggest total size when unpacking a ZIP
READ_WORKERS = 6                                        # files read in parallel

# default weights of the four parts of the match score (re-scaled when a part does not apply)
WEIGHTS = {"skills": 0.50, "text": 0.25, "experience": 0.15, "education": 0.10}
SHORTLIST_AT = 65                                       # match % labelled "Shortlist"
REVIEW_AT = 40                                          # match % labelled "Review"

# what the upload box accepts
UPLOAD_TYPES = ["pdf", "docx", "doc", "rtf", "odt", "txt", "md", "html", "htm",
                "png", "jpg", "jpeg", "tif", "tiff", "bmp", "zip"]
PALETTE = ["#4f46e5", "#e11d48", "#059669", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#65a30d"]
