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

The hard, unglamorous part. Options:

- **GDELT DOC API:** easy, free, but only covers about the last three months. Good for building the live pipeline.
- **GDELT GKG on Google BigQuery** (`gdelt-bq.gdeltv2.gkg_partitioned`): years of global news with timestamps. Always filter on the date partition, or one query can eat the monthly free allowance.
- **Kaggle financial-news datasets:** quick, but check they have publication times, not just dates.

Store everything as `data\news\headlines.parquet` with columns `published_utc`, `title`, `source`, `url`. Keep queries broad: silver, gold, Fed, dollar, rupee, RBI, solar demand, inflation.

**Done when:** you have at least two years of timestamped headlines, and you've checked a sample of timestamps by hand against the original articles.

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
