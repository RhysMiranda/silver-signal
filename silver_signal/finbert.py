"""FinBERT headline scoring.

FinBERT (ProsusAI/finbert on Hugging Face) is BERT fine-tuned on financial news.
For each headline it gives probabilities for positive, negative and neutral.
We keep all three plus one summary number:

    fb_score = P(positive) - P(negative)      between -1 and +1

Labels are read from the model's own config, so a model with a different label
order can't silently swap positive and negative.

Needs:  pip install -r requirements-nlp.txt   (torch, transformers)
The model (~440 MB) downloads once to your Hugging Face cache on first use.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

# Override with the FINBERT_MODEL environment variable (a Hugging Face name or a local folder).
MODEL = os.environ.get("FINBERT_MODEL", "ProsusAI/finbert")
LABELS = ("positive", "negative", "neutral")


class FinBert:
    def __init__(self, model: str = MODEL, batch_size: int = 64, max_length: int = 64,
                 threads: int | None = None):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if threads:
            torch.set_num_threads(threads)
        self._torch = torch
        self.tok = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForSequenceClassification.from_pretrained(model).eval()
        id2label = {int(i): str(l).lower() for i, l in self.model.config.id2label.items()}
        missing = set(LABELS) - set(id2label.values())
        if missing:
            raise ValueError(f"{model} has labels {id2label}; expected {LABELS}")
        self.order = [next(i for i, l in id2label.items() if l == lab) for lab in LABELS]
        self.batch_size, self.max_length = batch_size, max_length

    def probs(self, texts: list[str]) -> np.ndarray:
        """Array of shape (n, 3): P(positive), P(negative), P(neutral)."""
        out = []
        with self._torch.inference_mode():
            for i in range(0, len(texts), self.batch_size):
                batch = [str(t) for t in texts[i:i + self.batch_size]]
                enc = self.tok(batch, padding=True, truncation=True,
                               max_length=self.max_length, return_tensors="pt")
                p = self._torch.softmax(self.model(**enc).logits, dim=-1).numpy()
                out.append(p[:, self.order])
        return np.vstack(out) if out else np.zeros((0, 3))


_CACHE: dict = {}


def get_model(model: str | None = None, threads: int | None = 1) -> FinBert:
    """One FinBert per process. Spark reuses Python workers across tasks, so this
    loads the model once per worker rather than once per partition."""
    model = model or os.environ.get("FINBERT_MODEL", MODEL)
    if model not in _CACHE:
        _CACHE[model] = FinBert(model, threads=threads)
    return _CACHE[model]


def to_frame(probs: np.ndarray, index=None) -> pd.DataFrame:
    df = pd.DataFrame(probs, columns=["p_pos", "p_neg", "p_neu"], index=index)
    df["fb_score"] = df["p_pos"] - df["p_neg"]
    return df


def keyword_probs(texts: list[str]) -> np.ndarray:
    """Stand-in scorer with FinBERT's output shape, for tests and quick dry runs."""
    from .news import keyword_score

    s = np.array([keyword_score(t) for t in texts], dtype=float)
    pos = np.clip(s, 0, None) / (1 + np.abs(s))
    neg = np.clip(-s, 0, None) / (1 + np.abs(s))
    return np.column_stack([pos, neg, 1 - pos - neg])
