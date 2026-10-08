"""Train the resume -> job-category classifier.

Run once:  python train.py

Loads the Kaggle 'Updated Resume Dataset', cleans the text, REMOVES DUPLICATE
RESUMES, builds TF-IDF features, compares Logistic Regression and Naive Bayes with
cross-validation, evaluates the winner on a held-out test set, prints metrics, and
saves the vectorizer + best model + metrics.json to the models/ folder.

Everything runs on CPU in a few seconds.

v2 changes (honest evaluation)
  * The Kaggle file contains many exact duplicate resumes. If a duplicate lands in
    both train and test, accuracy looks like ~99% for the wrong reason. We drop
    duplicates BEFORE splitting, so the reported score reflects unseen resumes.
  * The model is chosen by 5-fold cross-validation on the training data, not by
    peeking at the test set.
"""
import json
import os
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.model_selection import (StratifiedKFold, cross_val_score,
                                     train_test_split)
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

# make the resume_ai package importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from resume_ai.preprocessing import clean_text  # noqa: E402

DATA_PATH = os.environ.get("RESUME_CSV") or os.path.join(BASE_DIR, "dataset", "UpdatedResumeDataSet.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")


def make_tfidf():
    return TfidfVectorizer(max_features=1500, stop_words="english", ngram_range=(1, 2))


def load_data():
    if not os.path.exists(DATA_PATH):
        sys.exit(
            f"Dataset not found at {DATA_PATH}\n"
            "Download 'UpdatedResumeDataSet.csv' from Kaggle:\n"
            "  https://www.kaggle.com/datasets/jillanisofttech/updated-resume-dataset\n"
            "and place it in the dataset/ folder."
        )
    df = pd.read_csv(DATA_PATH)

    # be flexible about column names across dataset versions
    text_col = next((c for c in df.columns if "resume" in c.lower()), None)
    cat_col = next((c for c in df.columns if "categor" in c.lower()), None)
    if text_col is None or cat_col is None:
        sys.exit(f"Expected resume/category columns, found: {list(df.columns)}")

    df = df[[cat_col, text_col]].dropna()
    df.columns = ["Category", "Resume"]
    return df


def main():
    print("Loading dataset...")
    df = load_data()
    n_raw = len(df)
    print(f"  {n_raw} resumes across {df['Category'].nunique()} categories")

    # ---- remove duplicates so train and test never share a resume
    df["Resume"] = df["Resume"].astype(str)
    df = df.drop_duplicates(subset="Resume").reset_index(drop=True)
    n_unique = len(df)
    print(f"  Removed {n_raw - n_unique} duplicate resumes -> {n_unique} unique resumes")

    counts = df["Category"].value_counts()
    rare = counts[counts < 4].index.tolist()
    if rare:
        print(f"  Dropping categories with fewer than 4 unique resumes: {rare}")
        df = df[~df["Category"].isin(rare)].reset_index(drop=True)

    print("Cleaning text...")
    df["clean"] = df["Resume"].apply(clean_text)

    X_train, X_test, y_train, y_test = train_test_split(
        df["clean"], df["Category"],
        test_size=0.2, random_state=42, stratify=df["Category"],
    )

    n_splits = max(2, min(5, int(y_train.value_counts().min())))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=1000, C=10),
        "Naive Bayes": MultinomialNB(),
    }

    print(f"\nComparing models ({n_splits}-fold cross-validation on the training set):")
    results, best_name, best_cv = {}, None, -1.0
    for name, clf in candidates.items():
        pipe = Pipeline([("tfidf", make_tfidf()), ("clf", clf)])
        scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_weighted")
        results[name] = {"cv_f1_mean": float(scores.mean()), "cv_f1_std": float(scores.std())}
        print(f"  {name:22s}  cv f1 = {scores.mean():.3f} (+/- {scores.std():.3f})")
        if scores.mean() > best_cv:
            best_name, best_cv = name, scores.mean()

    print("\nBuilding final TF-IDF features and fitting all models...")
    tfidf = make_tfidf()
    Xtr = tfidf.fit_transform(X_train)
    Xte = tfidf.transform(X_test)
    fitted = {}
    for name, clf in candidates.items():
        clf.fit(Xtr, y_train)
        preds = clf.predict(Xte)
        results[name]["test_accuracy"] = float(accuracy_score(y_test, preds))
        results[name]["test_f1"] = float(f1_score(y_test, preds, average="weighted"))
        print(f"  {name:22s}  test accuracy={results[name]['test_accuracy']:.3f}  "
              f"f1={results[name]['test_f1']:.3f}")
        fitted[name] = clf

    best_model = fitted[best_name]
    preds = best_model.predict(Xte)
    print(f"\nBest model (by cross-validation): {best_name}")
    print("\nClassification report (held-out test set):")
    print(classification_report(y_test, preds, zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(y_test, preds))

    metrics = {
        "resumes_raw": n_raw, "resumes_unique": n_unique,
        "categories": int(df["Category"].nunique()),
        "best_model": best_name,
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, preds, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_test, preds, average="weighted")),
        "models": results,
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(tfidf, os.path.join(MODELS_DIR, "tfidf.pkl"))
    joblib.dump(best_model, os.path.join(MODELS_DIR, "model.pkl"))
    with open(os.path.join(MODELS_DIR, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\nSaved tfidf.pkl, model.pkl and metrics.json to {MODELS_DIR}")


if __name__ == "__main__":
    main()
