# Plan

Each stage has a question it answers and a check that tells you it's done. Don't move on until the check passes; the honest version of this project is the impressive one.

## Week 0: foundation (done)

Data download and cache, one row per trading day with no look-ahead, five baselines, walk-forward evaluation, a cost-aware backtest, and tests for look-ahead, the news cut-off and the walk-forward split.

**Done when:** `python -m pytest` passes and `run_baselines.py --synthetic` prints two tables.

## Week 1: baselines on real data (you)

1. Run `python scripts\run_baselines.py` and paste the numbers into the README table.
2. Look at the worst 20 days for `overnight_rule` on `ret_cc` in `results\real\predictions.csv`. Are they futures roll dates, Indian holidays after big US moves, or days the ETF's premium jumped?
3. Plot ETF close against silver × USD/INR. How tight is the tracking, and how big is the premium or discount?

**Answers:** how much of the ETF's daily move the overnight rule explains, and what the cost-adjusted bar is for open-to-close.
**Done when:** you can say both numbers from memory and explain the worst days.

## Week 2: a sharper overnight window (you)

Daily bars run roughly 03:30 to 03:30 IST. The true window is 15:30 (yesterday's ETF close) to 09:15 (today's open). Use `yf.download(..., interval="60m")`, which goes back about two years, to measure silver and USD/INR between exactly those times, and add it as `driver_exact` in `features.py`.

**Done when:** a new test proves `driver_exact` only uses bars before 09:15, and you've compared it with the daily version.

## Week 3: collect historical news (you)

The hard, unglamorous part. The tools for it are ready:

1. **Make the query.** `python scripts\make_gdelt_sql.py --start 2024-01-01 --end 2024-01-08` prints a BigQuery query (a copy is in `sql\gdelt_one_week_example.sql`). It keeps English originals only, drops sports and other junk, labels each headline (silver, precious metals, rupee, Fed, dollar, RBI, US macro, India import duty) and removes syndicated duplicates.
2. **Run one week first** at https://console.cloud.google.com/bigquery. Before pressing Run, read "This query will process ... GB" and multiply by the number of weeks you want. Stay under the free 1 TB a month by doing a few months per calendar month if needed.
3. **Export** each result as CSV into `data\news\raw\`.
4. **Clean and review:** `python scripts\clean_news.py` combines the files, re-checks every headline, and prints counts by category, source and month, plus random samples. Read the samples. If junk gets through, add words to `JUNK` or tighten a category in `silver_signal\news_filter.py`, add the headline to `tests\test_news_filter.py`, and regenerate the query. Both the SQL and the cleaner use the same definitions.

Output: `data\news\headlines.csv` with `published_utc, title, source, url, category, gdelt_tone, trusted`.

Alternatives if BigQuery gets expensive: the GDELT DOC API (free, last three months only) or a Kaggle news dataset with publication times.

**Done when:** you have at least two years of headlines, the samples look relevant, and you've opened 10 URLs to check the timestamps against the articles.

## Week 4: turn headlines into features (you)

1. Start with `news.keyword_score` and `news.daily_features` so the whole path works end to end.
2. Replace the scorer with FinBERT (`ProsusAI/finbert` on Hugging Face) sentiment.
3. Try an LLM that tags each headline with an event type (Fed decision, dollar move, industrial demand, India import duty, and so on) and a direction for silver in rupees. Cache every LLM response so reruns are free and reproducible.

**Done when:** each session has news features, and a test proves a headline published at 09:16 IST never reaches that day's row.

## Week 5: does news add anything? (you)

Model the **residual**: what the overnight rule got wrong. If news only re-describes the overnight silver move, it will add nothing here. Try logistic regression first, then gradient boosting, always walk-forward.

Compare against `overnight_rule` and `gap_rule` on `ret_oc`, after costs. Use a binomial test on hit rates and report the 95% interval. A 52% hit rate on 900 days is not evidence of anything.

**Done when:** you can answer question 3 in the README with a number and an interval, whichever way it falls.

## Week 6: live, public track record (you)

A GitHub Actions workflow on a schedule (cron times are UTC):

- `30 3 * * 1-5` (09:00 IST): fetch overnight data and news, write today's forecast to `live/predictions.csv`, commit.
- `0 11 * * 1-5` (16:30 IST): record what actually happened, commit.

Then add a small page on your portfolio that reads the CSV and shows the running record. Paper trade it for at least two months before trusting it with money.

**Done when:** a forecast has been published before the open, with a commit timestamp to prove it, for 20 trading days in a row.

## Week 7: write it up (you)

A short post with three sections: what the overnight rule explains, what news adds (or doesn't), and what you'd change. Include the result that disappointed you. Then add the project to your portfolio, linking the repo, the live tracker and the write-up.
