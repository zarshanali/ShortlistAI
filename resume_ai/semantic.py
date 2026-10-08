"""OPTIONAL meaning-based similarity using a small sentence-embedding model (MiniLM).

TF-IDF only sees identical words, so "built ML models" vs "machine learning engineer"
scores low. Embeddings understand they are close. Needs `pip install sentence-transformers`
(first use downloads ~90 MB). All CVs are embedded in ONE batch, so it stays quick.
"""
from __future__ import annotations

import importlib.util
from typing import List, Optional

import numpy as np

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class Embedder:
    def __init__(self, name: str = MODEL):
        self.model, self.error, self.name = None, "", name.split("/")[-1]
        try:
            from sentence_transformers import SentenceTransformer
            try:
                import torch
                dev = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                dev = "cpu"
            self.model = SentenceTransformer(name, device=dev)
            self.model.max_seq_length = 256
        except Exception as e:
            self.error = str(e)

    def encode_docs(self, texts: List[str], chunk_words: int = 150, max_chunks: int = 12) -> Optional[np.ndarray]:
        """One normalised vector per document (mean of its chunks). None if the model is unavailable."""
        if self.model is None:
            return None
        chunks, owner = [], []
        for i, t in enumerate(texts):
            words = t.split() or [""]
            for j in list(range(0, len(words), chunk_words))[:max_chunks]:
                chunks.append(" ".join(words[j:j + chunk_words]))
                owner.append(i)
        vecs = self.model.encode(chunks, batch_size=128, normalize_embeddings=True, show_progress_bar=False)
        owner = np.array(owner)
        out = np.vstack([vecs[owner == i].mean(0) for i in range(len(texts))])
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return (out / np.maximum(norms, 1e-9)).astype(np.float32)
