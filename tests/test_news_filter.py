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
    # real headlines from the first GDELT export
    "Silver Price Analysis: XAG/USD tumbles below $23 as US labor market conditions improve": "silver",
    "Rupee rises four paise to close at 83.28 against U.S. dollar": "rupee",
    "Gold slips to near two-week low as dollar firms ahead of Fed minutes": "precious_metals",
    "Copper prices fall on stronger US dollar": "dollar",
    "Will the dollar index recover at the beginning of 2024?": "dollar",
    "TREASURIES-U.S. Treasury yields climb as investors rein in rate-cut bets": "us_macro",
    "Rupee slips to all-time low of 83.80 against US dollar in early trade": "rupee",
    "India hikes gold and silver import duty to 15% to protect rupee": "india_duty",
    "Gold surges over Rs 3,300 in this week, Silver crosses Rs 1.28 L mark": "silver",
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
    # real headlines from the first GDELT export
    "Rupee records back-to-back gain, settles at 281.67 against US dollar - Markets Pakistan",
    "Gold Rate in Pakistan Today – 01 Jan 2024",
    "Gold prices in Doha Today Sunday 7 January 2024",
    "IMPACT Silver (CVE:IPT) Stock Price Down 5.1%",
    "Silver Tiger Metals Inc. (OTCMKTS:SLVTF) Sees Significant Increase in Short Interest",
    "Japanese Yen remains depressed for the third straight day against US Dollar",
    "Naira extends gains against US Dollar at forex market",
    "AUD/USD declines into 0.6750 as Greenback lurches higher, China data beat bolsters Aussie",
    "Gold, Silver Prices On January 5; Check Prices In Mumbai, Delhi, Chennai, Kolkata",
    # real headlines from the full 2022-2026 export
    "Sri Lankan Rupee Records Modest Gains Against the US Dollar",
    "Sri Lankan rupee appreciates against USD for week",
    "Today Gold, Silver Rate January 11: Check 18, 22, 24 carat Gold prices in Chennai, Mumbai",
    "Invesco Ltd: Form 8.3 - Dundee Precious Metals Inc; Public",
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


def test_blocked_sources():
    assert nf.is_blocked_source("dnd.com.pk")
    assert nf.is_blocked_source("brecorder.com")
    assert not nf.is_blocked_source("thehindu.com")
