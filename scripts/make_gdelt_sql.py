"""Print a BigQuery query that pulls relevant English headlines from GDELT.

    python scripts/make_gdelt_sql.py --start 2024-01-01 --end 2024-01-08
    python scripts/make_gdelt_sql.py --start 2024-01-01 --end 2024-02-01 > month.sql

Paste the output into https://console.cloud.google.com/bigquery and check the
"This query will process ... GB" note (top right) BEFORE pressing Run.
The end date is exclusive. Headline titles exist in GDELT from September 2019.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import news_filter as nf  # noqa: E402


def category_case() -> str:
    lines = []
    for name, topic, ctx in nf.CATEGORIES:
        cond = f"REGEXP_CONTAINS(t, r'{topic}')"
        if ctx:
            cond += f"\n           AND REGEXP_CONTAINS(t, r'{ctx}')"
        lines.append(f"      WHEN {cond}\n        THEN '{name}'")
    return "\n".join(lines)


def build(start: date, end: date) -> str:
    trusted = ", ".join(f"'{d}'" for d in nf.TRUSTED_SOURCES)
    return f"""-- silver-signal: GDELT headlines {start} to {end} (end exclusive)
-- Check the bytes estimate before running. Re-run month by month for longer ranges.
WITH raw AS (
  SELECT
    PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)) AS published_utc,
    REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title,
    LOWER(SourceCommonName) AS source,
    DocumentIdentifier AS url,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS gdelt_tone
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('{start}')
    AND _PARTITIONTIME <  TIMESTAMP('{end}')
    -- English originals only: translated articles keep foreign-language titles
    AND (TranslationInfo IS NULL OR TranslationInfo = '')
),
cleaned AS (
  SELECT *, LOWER(title) AS t
  FROM raw
  WHERE title IS NOT NULL
    AND LENGTH(title) BETWEEN 25 AND 220
    AND NOT REGEXP_CONTAINS(title, r'{nf.NON_ENGLISH_CHARS}')
    AND NOT REGEXP_CONTAINS(LOWER(title), r'{nf.JUNK}')
),
labelled AS (
  SELECT *,
    CASE
{category_case()}
    END AS category
  FROM cleaned
)
SELECT
  published_utc, title, source, url, category, gdelt_tone,
  source IN ({trusted}) AS trusted
FROM labelled
WHERE category IS NOT NULL
-- the same headline syndicated across many sites: keep the first appearance
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY REGEXP_REPLACE(t, r'[^a-z0-9]', '') ORDER BY published_utc) = 1
ORDER BY published_utc
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat, help="exclusive")
    a = ap.parse_args()
    if a.end <= a.start:
        sys.exit("--end must be after --start")
    if a.start < date(2019, 9, 1):
        print("-- note: GDELT has no headline titles before September 2019", file=sys.stderr)
    sys.stdout.write(build(a.start, a.end))


if __name__ == "__main__":
    main()
