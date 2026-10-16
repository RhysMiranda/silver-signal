-- silver-signal: GDELT headlines 2024-01-01 to 2024-01-08 (end exclusive)
-- Check the bytes estimate before running. Re-run month by month for longer ranges.
WITH raw AS (
  SELECT
    PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)) AS published_utc,
    REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title,
    LOWER(SourceCommonName) AS source,
    DocumentIdentifier AS url,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS gdelt_tone
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('2024-01-01')
    AND _PARTITIONTIME <  TIMESTAMP('2024-01-08')
    -- English originals only: translated articles keep foreign-language titles
    AND (TranslationInfo IS NULL OR TranslationInfo = '')
),
cleaned AS (
  SELECT *, LOWER(title) AS t
  FROM raw
  WHERE title IS NOT NULL
    AND LENGTH(title) BETWEEN 25 AND 220
    AND NOT REGEXP_CONTAINS(title, r'[^\x00-\x7F–—‘’“”…₹ ]')
    AND NOT REGEXP_CONTAINS(LOWER(title), r'\b(medal|medals|medallist|medalist|olympic|olympics|world cup|championship|tournament|silver screen|silver lining|silver jubilee|silver anniversary|silverware|silver spoon|silverback|silverstone|silver lake|silverado|silver alert|silver fox|adam silver|nate silver|silver city|quicksilver|silver surfer|silver age|silver star|silver bells?|wedding|recipe|horoscope|crossword)\b')
),
labelled AS (
  SELECT *,
    CASE
      WHEN REGEXP_CONTAINS(t, r'\b(import duty|customs duty|import tariff)\b')
           AND REGEXP_CONTAINS(t, r'\b(gold|silver|bullion|precious)\b')
        THEN 'india_duty'
      WHEN REGEXP_CONTAINS(t, r'\bsilver\b')
           AND REGEXP_CONTAINS(t, r'\b(price|prices|rate|rates|ounce|ounces|oz|futures|comex|mcx|bullion|etf|etfs|rally|rallies|surge|surges|soar|soars|jump|jumps|slump|slumps|tumble|tumbles|fall|falls|drop|drops|rise|rises|gain|gains|record|demand|supply|deficit|import|imports|precious|metal|metals|outlook|forecast|trading|traders|investors)\b')
        THEN 'silver'
      WHEN REGEXP_CONTAINS(t, r'\b(precious metals?|bullion|gold prices?|gold rate|gold futures|spot gold|comex gold|mcx gold|gold etfs?|gold hits|gold rises|gold falls|gold slips|gold gains)\b')
        THEN 'precious_metals'
      WHEN REGEXP_CONTAINS(t, r'\brupee\b')
           AND REGEXP_CONTAINS(t, r'\b(dollar|usd|forex|rbi|record low|record high|weakens|strengthens|falls|rises|slips|gains|ends|opens|settles|depreciates?|appreciates?|depreciation)\b')
        THEN 'rupee'
      WHEN REGEXP_CONTAINS(t, r'\b(fed|federal reserve|fomc|powell)\b')
           AND REGEXP_CONTAINS(t, r'\b(rate|rates|hike|hikes|cut|cuts|hold|holds|policy|minutes|inflation|meeting|decision|tightening|easing|dovish|hawkish)\b')
        THEN 'fed'
      WHEN REGEXP_CONTAINS(t, r'\b(dollar index|dxy|greenback|us dollar|u\.s\. dollar)\b')
        THEN 'dollar'
      WHEN REGEXP_CONTAINS(t, r'\b(rbi|reserve bank of india)\b')
           AND REGEXP_CONTAINS(t, r'\b(repo|rate|rates|policy|mpc|inflation|liquidity)\b')
        THEN 'rbi'
      WHEN REGEXP_CONTAINS(t, r'\b(us|u\.s|american)\b')
           AND REGEXP_CONTAINS(t, r'\b(cpi|inflation|jobs report|nonfarm|payrolls|pce|gdp|recession|treasury yields?)\b')
        THEN 'us_macro'
    END AS category
  FROM cleaned
)
SELECT
  published_utc, title, source, url, category, gdelt_tone,
  source IN ('reuters.com', 'bloomberg.com', 'cnbc.com', 'marketwatch.com', 'wsj.com', 'ft.com', 'barrons.com', 'apnews.com', 'kitco.com', 'fxstreet.com', 'investing.com', 'economictimes.indiatimes.com', 'livemint.com', 'business-standard.com', 'moneycontrol.com', 'financialexpress.com', 'thehindubusinessline.com', 'businesstoday.in', 'ndtvprofit.com', 'zeebiz.com', 'thehindu.com', 'hindustantimes.com', 'timesofindia.indiatimes.com') AS trusted
FROM labelled
WHERE category IS NOT NULL
-- the same headline syndicated across many sites: keep the first appearance
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY REGEXP_REPLACE(t, r'[^a-z0-9]', '') ORDER BY published_utc) = 1
ORDER BY published_utc
