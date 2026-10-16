import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import news_filter as nf  # noqa: E402

KEEP = {
    "Silver prices surge to 12-year high as industrial demand climbs": "silver",
    "MCX silver futures fall Rs 1,200 per kg on weak global cues": "silver",
    "Silver ETFs see record inflows in India this Diwali": "silver",
    "Gold prices slip as dollar firms ahead of Fed minutes": "precious_metals",
    "Spot gold steadies near record; bullion traders eye US data": "precious_metals",
    "Fed holds rates steady, signals two cuts later this year": "fed",
    "Powell says Fed in no hurry to cut rates": "fed",
    "Dollar index climbs to two-month high after strong payrolls": "dollar",
    "Rupee falls 15 paise to 83.40 against US dollar in early trade": "rupee",
    "RBI keeps repo rate unchanged at 6.5% for seventh straight time": "rbi",
    "US CPI inflation cools more than expected in March": "us_macro",
    "Government cuts import duty on gold and silver to 6%": "india_duty",
    "Silver&#39;s rally: what&#39;s driving the metal higher": "silver",
}
DROP = [
    "India wins silver medal in men's 4x400m relay at Asian Games",
    "Silver jubilee celebrations held at district school",
    "Adam Silver says NBA expansion talks are on hold",
    "Silverstone confirms new contract with Formula 1",
    "Fed up with traffic, residents block highway",
    "Cricketer donates prize money worth one lakh rupee to charity",
    "Every cloud has a silver lining, says coach",
    "Ramesh celebrates silver wedding anniversary",
]


def test_keeps_market_headlines_with_right_category():
    for title, cat in KEEP.items():
        assert nf.categorize(nf.clean_title(title)) == cat, title


def test_drops_unrelated_headlines():
    for title in DROP:
        assert nf.categorize(title) is None, title


def test_language_filter():
    assert nf.is_english("Rupee ends at ₹83.2 — lowest since June")
    assert not nf.is_english("Precio de la plata sube un 3% ¡récord!")
    assert not nf.is_english("सोने की कीमत")
    assert not nf.is_english("白银价格上涨")


def test_trusted_sources():
    assert nf.is_trusted("reuters.com")
    assert nf.is_trusted("economictimes.indiatimes.com")
    assert not nf.is_trusted("notreuters.com")


def test_patterns_avoid_syntax_bigquery_rejects():
    # BigQuery's RE2 has no lookarounds or backreferences
    for _, topic, ctx in nf.CATEGORIES:
        for p in (topic, ctx or ""):
            assert not re.search(r"\(\?[=!<]|\\[1-9]", p), p
            assert "'" not in p   # would break the SQL string
