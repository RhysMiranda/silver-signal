"""What counts as a relevant headline. One definition, used twice:

* `scripts/make_gdelt_sql.py` turns these patterns into the BigQuery filter, so
  you only download (and pay for) plausible headlines.
* `scripts/clean_news.py` applies them again in Python after cleaning, which is
  the version that decides what goes into the model.

Patterns use only syntax that both Python `re` and BigQuery's RE2 understand:
word boundaries, groups, alternation and simple classes. They run on lower-case text.

Each category needs a topic word AND a market word, which is what keeps out
"silver medal", "Fed up with..." and "rupee" stories about cricket prize money.
"""
from __future__ import annotations

import html
import re

# (category, topic pattern, market-context pattern or None). First match wins.
CATEGORIES: list[tuple[str, str, str | None]] = [
    ("india_duty",
     r"\b(import duty|customs duty|import tariff)\b",
     r"\b(gold|silver|bullion|precious)\b"),
    ("silver",
     r"\bsilver\b",
     r"\b(price|prices|rate|rates|ounce|ounces|oz|futures|comex|mcx|bullion|etf|etfs|"
     r"rally|rallies|surge|surges|soar|soars|jump|jumps|slump|slumps|tumble|tumbles|"
     r"fall|falls|drop|drops|rise|rises|gain|gains|record|demand|supply|deficit|"
     r"import|imports|precious|metal|metals|outlook|forecast|trading|traders|investors)\b"),
    ("precious_metals",
     r"\b(precious metals?|bullion|gold prices?|gold rate|gold futures|spot gold|comex gold|"
     r"mcx gold|gold etfs?|gold hits|gold rises|gold falls|gold slips|gold gains)\b",
     None),
    ("rupee",
     r"\brupee\b",
     r"\b(dollar|usd|forex|rbi|record low|record high|weakens|strengthens|falls|rises|"
     r"slips|gains|ends|opens|settles|depreciates?|appreciates?|depreciation)\b"),
    ("fed",
     r"\b(fed|federal reserve|fomc|powell)\b",
     r"\b(rate|rates|hike|hikes|cut|cuts|hold|holds|policy|minutes|inflation|meeting|"
     r"decision|tightening|easing|dovish|hawkish)\b"),
    ("dollar",
     r"\b(dollar index|dxy|greenback|us dollar|u\.s\. dollar)\b",
     r"\b(index|dxy|greenback|strengthens|weakens|firms|slips|rallies|rally|falls|rises|gains|"
     r"jumps|slides|steadies|surges|tumbles|softens|rebounds|strength|weakness|outlook|"
     r"stronger|weaker|strong|weak|commodities|commodity|gold|silver|metals?)\b"),
    ("rbi",
     r"\b(rbi|reserve bank of india)\b",
     r"\b(repo|rate|rates|policy|mpc|inflation|liquidity)\b"),
    ("us_macro",
     r"\b(us|u\.s|american)\b",
     r"\b(cpi|inflation|jobs report|nonfarm|payrolls|pce|gdp|recession|treasury yields?)\b"),
]

# Headlines that match a topic word but are about something else entirely.
JUNK = (r"\b(medal|medals|medallist|medalist|olympic|olympics|world cup|championship|"
        r"tournament|silver screen|silver lining|silver jubilee|silver anniversary|"
        r"silverware|silver spoon|silverback|silverstone|silver lake|silverado|silver alert|"
        r"silver fox|adam silver|nate silver|silver city|quicksilver|silver surfer|"
        r"silver age|silver star|silver bells?|wedding|recipe|horoscope|crossword|"
        # other countries' prices and currencies (this project is about India and the US)
        r"pakistan|pakistani|karachi|lahore|pkr|nepal|nepali|nepalese|sri lanka|sri lankan|lankan|"
        r"bangladesh|bangladeshi|taka|mauritian|seychelles|"
        r"doha|qatar|dubai|uae|saudi|riyadh|jeddah|muscat|bitcoin gold|kuwait|oman|bahrain|armenia|azerbaijan|nigeria|naira|"
        r"kenya|ghana|malaysia|ringgit|philippine|peso|yen|sterling|ringgit|rand|lira|baht|"
        r"aud/usd|nzd/usd|usd/cad|usd/jpy|gbp/usd|usd/mxn|loonie|aussie|kiwi|"
        # small-company stock chatter: tickers like (CVE:IPT) or (OTCMKTS:SLVTF)
        r"cve|tsxv|otcmkts|short interest|stock price (up|down)|shares (up|down)|"
        # daily price listing pages carry no news
        r"check (latest )?(prices|rates)|rate today|rates today|carat|karat|"
        # regulatory filings
        r"form 8\.3|form 4|13f|sec filing)\b")

# Outlets with reliable timestamps and real market coverage. Kept as a flag, not a filter.
TRUSTED_SOURCES = (
    "reuters.com", "bloomberg.com", "cnbc.com", "marketwatch.com", "wsj.com", "ft.com",
    "barrons.com", "apnews.com", "kitco.com", "fxstreet.com", "investing.com",
    "economictimes.indiatimes.com", "livemint.com", "business-standard.com",
    "moneycontrol.com", "financialexpress.com", "thehindubusinessline.com",
    "businesstoday.in", "ndtvprofit.com", "zeebiz.com", "thehindu.com",
    "hindustantimes.com", "timesofindia.indiatimes.com", "indiatimes.com",
    "marketscreener.com", "forexlive.com", "seekingalpha.com", "yahoo.com", "mining.com",
)

# Domains from countries whose local price pages swamp the feed. Dropped outright.
BLOCKED_TLDS = (".pk", ".np", ".ng", ".az", ".am", ".lk", ".bd", ".qa", ".ae")
# Pakistani outlets on .com/.tv domains: their "rupee" is the Pakistani rupee.
BLOCKED_SOURCES = ("brecorder.com", "dawn.com", "thenews.com", "geo.tv", "arynews.tv",
                   "samaa.tv", "dunyanews.tv", "express.com", "bolnews.com", "propakistani.com",
                   "nagariknetwork.com", "albawaba.com")

# Characters allowed besides plain ASCII: curly quotes, dashes, ellipsis, rupee sign, nbsp.
_EXTRA_OK = "–—‘’“”…₹ "
NON_ENGLISH_CHARS = r"[^\x00-\x7F" + _EXTRA_OK + "]"

_compiled = [(name, re.compile(topic), re.compile(ctx) if ctx else None)
             for name, topic, ctx in CATEGORIES]
_junk = re.compile(JUNK)
_non_en = re.compile(NON_ENGLISH_CHARS)


def clean_title(title: str) -> str:
    """Decode HTML entities (&amp;, &#39;) and squeeze whitespace."""
    return re.sub(r"\s+", " ", html.unescape(str(title))).strip()


def is_english(title: str) -> bool:
    return not _non_en.search(title)


def is_junk(title: str) -> bool:
    return bool(_junk.search(title.lower()))


def categorize(title: str) -> str | None:
    t = title.lower()
    if _junk.search(t):
        return None
    for name, topic, ctx in _compiled:
        if topic.search(t) and (ctx is None or ctx.search(t)):
            return name
    return None


def is_blocked_source(source: str) -> bool:
    s = str(source).lower()
    return s.endswith(BLOCKED_TLDS) or s in BLOCKED_SOURCES


def is_trusted(source: str) -> bool:
    s = str(source).lower()
    return any(s == d or s.endswith("." + d) for d in TRUSTED_SOURCES)
