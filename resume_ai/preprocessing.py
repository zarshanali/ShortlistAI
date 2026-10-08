"""Text cleaning and preprocessing shared by training and prediction.

IMPORTANT: the same clean_text() must be used when training the model AND when
predicting, otherwise the features won't line up.

v2 change: if NLTK (or its data files) is unavailable - e.g. no internet on first
run - we fall back to scikit-learn's built-in stop-word list and skip lemmatization
instead of crashing. Normal runs (NLTK available) behave exactly as before.
"""
import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
except ImportError:  # NLTK not installed
    nltk = None


def _ensure_nltk():
    """Download the small NLTK data files once (quietly) if missing."""
    if nltk is None:
        return
    for pkg, path in [
        ("stopwords", "corpora/stopwords"),
        ("wordnet", "corpora/wordnet"),
        ("omw-1.4", "corpora/omw-1.4"),
    ]:
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                pass


def _setup():
    """Return (stopword_set, lemmatize_function) with graceful fallbacks."""
    _ensure_nltk()
    try:
        stop = set(stopwords.words("english"))
    except Exception:
        stop = set(ENGLISH_STOP_WORDS)
    try:
        lem = WordNetLemmatizer()
        lem.lemmatize("tests")  # raises LookupError if wordnet is missing
        return stop, lem.lemmatize
    except Exception:
        return stop, (lambda w: w)


STOPWORDS, _lemmatize = _setup()


def clean_text(text):
    """Lowercase, strip noise, remove stopwords and lemmatize.

    Returns a single space-joined string ready for TF-IDF.
    """
    if not isinstance(text, str):
        text = str(text)

    text = text.lower()
    text = re.sub(r"http\S+|www\.\S+", " ", text)        # URLs
    text = re.sub(r"\S+@\S+", " ", text)                  # emails
    text = re.sub(r"[^a-z\s]", " ", text)                 # keep letters only
    text = re.sub(r"\s+", " ", text).strip()              # collapse spaces

    tokens = [
        _lemmatize(tok)
        for tok in text.split()
        if tok not in STOPWORDS and len(tok) > 1
    ]
    return " ".join(tokens)
