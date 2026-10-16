"""FinBERT wrapper: labels must be read from the model, never assumed by position."""
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import finbert  # noqa: E402


def _tiny_model(tmp_path, id2label, winner):
    """A tiny random BERT whose `winner` label always gets the highest logit."""
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "silver", "rises", "falls", "fed", "cuts"]
    (tmp_path / "vocab.txt").write_text("\n".join(vocab))
    tok = BertTokenizerFast(vocab_file=str(tmp_path / "vocab.txt"))
    cfg = BertConfig(vocab_size=len(vocab), hidden_size=8, num_hidden_layers=1, num_attention_heads=1,
                     intermediate_size=8, num_labels=3, id2label=id2label,
                     label2id={v: k for k, v in id2label.items()})
    model = BertForSequenceClassification(cfg)
    with torch.no_grad():
        model.classifier.weight.zero_()
        model.classifier.bias.zero_()
        model.classifier.bias[[k for k, v in id2label.items() if v.lower() == winner][0]] = 20.0
    tok.save_pretrained(tmp_path)
    model.save_pretrained(tmp_path)
    return str(tmp_path)


@pytest.mark.parametrize("id2label", [
    {0: "positive", 1: "negative", 2: "neutral"},   # ProsusAI/finbert's order
    {0: "neutral", 1: "positive", 2: "negative"},
    {0: "NEGATIVE", 1: "Neutral", 2: "Positive"},
])
def test_positive_is_positive_whatever_the_label_order(tmp_path, id2label):
    fb = finbert.FinBert(_tiny_model(tmp_path, id2label, "positive"), batch_size=2)
    p = fb.probs(["silver rises", "fed cuts", "silver falls"])
    assert p.shape == (3, 3)
    np.testing.assert_allclose(p.sum(axis=1), 1, atol=1e-5)
    assert (p[:, 0] > 0.99).all()                       # column 0 is always P(positive)
    df = finbert.to_frame(p)
    assert (df["fb_score"] > 0.98).all()


def test_negative_winner(tmp_path):
    fb = finbert.FinBert(_tiny_model(tmp_path, {0: "positive", 1: "negative", 2: "neutral"}, "negative"))
    assert (finbert.to_frame(fb.probs(["silver falls"]))["fb_score"] < -0.98).all()


def test_rejects_model_without_expected_labels(tmp_path):
    with pytest.raises(ValueError):
        finbert.FinBert(_tiny_model(tmp_path, {0: "a", 1: "b", 2: "c"}, "a"))


def test_spark_job_with_a_real_model(tmp_path, monkeypatch):
    pytest.importorskip("pyspark")
    import pandas as pd
    from silver_signal import spark_news
    path = _tiny_model(tmp_path, {0: "positive", 1: "negative", 2: "neutral"}, "negative")
    monkeypatch.setenv("FINBERT_MODEL", path)
    heads = pd.DataFrame({
        "published_utc": pd.to_datetime(["2024-03-11 01:00", "2024-03-11 02:00", "2024-03-12 01:00"], utc=True),
        "title": ["silver rises", "fed cuts", "silver falls"], "source": "x.com",
        "category": ["silver", "fed", "silver"], "gdelt_tone": [1.0, 2.0, 3.0], "trusted": True})
    per, daily = spark_news.run(heads, pd.to_datetime(["2024-03-11", "2024-03-12"]), "finbert",
                                cores=2, partitions=2)
    assert (per["fb_score"] < -0.98).all()
    assert daily.loc["2024-03-11", "fb_metals"] < -0.98 and daily.loc["2024-03-11", "n_fed"] == 1
