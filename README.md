# silver-signal

Can the morning's news predict Indian silver ETFs, once you account for what silver and the rupee did overnight?

Silver ETFs on NSE hold physical silver, so their price is mostly the international silver price in rupees. By the 09:15 IST open, silver has already traded all night in London and New York. This project starts from that one-line rule, tests whether 234,000 news headlines add anything on top of it, and then follows up on what the data showed instead.

**Live dashboard:** [rhysmiranda.github.io/silver-signal](https://rhysmiranda.github.io/silver-signal/), daily paper trading since May 2026.

## Findings

1. **Last night's silver and rupee moves predict the ETF's day.** The overnight rule calls close-to-close direction 67% of the time, and the tradable open-to-close direction 56% (95% interval 53–59%).
2. **News adds nothing.** Headlines scored by GDELT's tone and by FinBERT both perform at chance on their own (50–51%) and make the overnight rule slightly worse when added.
3. **The ETF's gains all came overnight.** Over four years, Indian trading hours lost money in every full year, while silver itself rose during those hours.
4. **The cause is the opening price.** The ETF opened 18 bps a day rich compared with silver (t = −4.0) and gave it back within the first hour. After 10:15 it tracked silver. Buying at 10:15 rather than 09:15 turned −50% into +15% over two years.
5. **That edge has faded.** It was −36 bps a day in late 2024 and is gone in 2026. The daily pipeline tracks whether it returns.

## Method

At 09:15 IST each day, using only information published before then:

| Target | What it means |
|---|---|
| close-to-close return | includes the opening gap; easy to predict, impossible to trade from a 09:15 forecast |
| open-to-close return | what buying at the open and selling at the close actually captures |

The newest silver or USD/INR bar a forecast may use is the last one dated strictly before the session. A headline may only inform the first session whose open comes after it was published. Both rules are enforced in code and tested.

| Baseline | Idea |
|---|---|
| `zero` | no change |
| `historical_mean` | the average return so far |
| `yesterday` | today repeats yesterday |
| `overnight_rule` | overnight silver × rupee move, with a fitted slope |
| `gap_rule` | does the day continue or reverse its opening gap? |

Every model is scored walk-forward: fit on everything before a 20-day block, predict the block, move on. Trading results are long-or-flat with a 10 bp round-trip cost.

The main results use Nippon India Silver ETF (SILVERBEES), because Yahoo Finance only has HDFC Silver ETF prices from March 2025. Both hold physical silver. SILVERBEES gives 1,016 trading days (September 2022 to October 2026), 896 of them scored out of sample.

## Results

### Overnight moves explain most of the day

| Target | Model | Hit rate (95% interval) | Rank corr. |
|---|---|---|---|
| close-to-close | overnight rule | **67.1%** (64.0–70.2%) | 0.455 |
| close-to-close | historical mean | 53.2% (49.9–56.5%) | −0.013 |
| open-to-close | overnight rule | **55.9%** (52.6–59.1%) | 0.154 |
| open-to-close | historical mean | 50.8% (47.5–54.1%) | 0.010 |
| open-to-close | gap rule | 45.3% (42.0–48.5%) | −0.149 |

The open-to-close edge doesn't make money as "buy at the open": 134 trades, −2.5% in total. The skill is mostly in spotting down days, which a long-only strategy can only sit out.

### News adds nothing

About 234,000 English market headlines from GDELT (2022–2026), filtered for silver, precious metals, the Fed, the dollar, US data, the rupee and Indian import duty. They're averaged into five daily moods (metals, fed, dollar, us_data, india), kept apart because good news for the dollar is usually bad for silver. Each headline is scored two ways: GDELT's general tone, and [FinBERT](https://huggingface.co/ProsusAI/finbert) (P(positive) − P(negative)), run in parallel with Spark.

| Model (open-to-close, 896 days) | Hit rate (95% interval) | Rank corr. |
|---|---|---|
| overnight rule | 55.9% (52.6–59.1%) | 0.154 |
| GDELT tone only | 50.1% (46.8–53.4%) | 0.001 |
| overnight rule + GDELT tone | 55.8% (52.5–59.0%) | 0.133 |
| FinBERT only | 51.2% (48.0–54.5%) | 0.001 |
| overnight rule + FinBERT | 55.8% (52.5–59.0%) | 0.130 |

By 09:15, whatever the morning's headlines say is already in the overnight silver and rupee prices.

### The gains came overnight

| Period | Overnight (close → open) | Daytime (open → close) |
|---|---|---|
| All days | +1,297% | **−73%** |
| 2023 | +97% | −41% |
| 2024 | +87% | −33% |
| 2025 | +185% | −13% |
| 2026 to 16 Oct | +5% | −15% |

Yahoo's opening prices were checked against an official NSE download: at least 95% match within 0.2%, and dropping every suspect bar barely changes the result.

### Why: the ETF opens rich

Against hourly COMEX silver converted to rupees (511 sessions, May 2024 to October 2026):

| ETF minus silver | Average per day | t | Slope on opening premium |
|---|---|---|---|
| 09:15–10:15 | **−17.9 bps** | −4.0 | −0.57 |
| 10:15–15:30 | −1.9 bps | −0.7 | −0.05 |

| Total return | |
|---|---|
| buy 09:15, sell 15:30 | −50.1% |
| buy 10:15, sell 15:30 | +14.8% (silver, same hours: +27.6%) |

The richer the open, the bigger the first-hour giveback. After 10:15, the opening premium predicts nothing. The first-hour slope is partly mechanical, since the opening price sits on both sides of it. The after-10:15 numbers use a separate price, and the −17.9 bps average can't come from random noise in the opening price, which would average out.

### Robustness (R)

`R/robustness.R` re-tests the first-hour result:

- **Newey-West errors**, which allow for runs of similar days: t = −4.0, unchanged.
- **10-day block bootstrap:** waiting until 10:15 added +130% over the period (95% interval +43% to +297%), and none of 5,000 draws was negative.
- **Outliers:** median −12.4 bps; trimming the extreme 1% of days gives −14.6 bps; 61% of days negative.
- **By half-year:** −36 bps (2024 H2), −24, −17, −5 (2026 H1), +6 (2026 H2 so far). The effect has faded to nothing.

## Pipeline

```
GDELT (BigQuery) ─> clean_news ─> Spark + FinBERT ─> daily news moods ─┐
Yahoo daily + hourly prices ───────────────────────────────────────────┴─> walk-forward models
Airflow (daily, 16:15 IST) ─> paper trades ─> MongoDB Atlas ─> FastAPI (Vercel) ─> React dashboard
```

- **Spark:** FinBERT scores the headlines inside a pandas UDF; Spark SQL builds the daily moods. A test checks that the Spark output matches the pandas version exactly. The full 233,737 headlines take 84 minutes on a laptop (4 workers × 4 PyTorch threads).
- **Airflow:** every weekday at 16:15 IST it fetches prices and records three paper strategies (`overnight_rule`, `buy_0915`, `wait_1015`) plus the first-hour gap. Records are keyed by date, so reruns overwrite instead of duplicating.
- **API:** FastAPI, read-only: `/summary`, `/trades`, `/equity`, `/health`.
- **Dashboard:** React, Vite and Recharts, published to GitHub Pages by a GitHub Actions workflow.

## Running it

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
python scripts\run_baselines.py --etf SILVERBEES.NS
python scripts\intraday_1015.py --etf SILVERBEES.NS
```

**News.** `python scripts\make_gdelt_sql.py --start 2024-01-01 --end 2025-01-01` prints the BigQuery query (a ready copy is in `sql\`). Save the results as CSV in `data\news\raw\`, then run `python scripts\clean_news.py` and `python scripts\news_test.py --etf SILVERBEES.NS`.

**FinBERT with Spark.** Needs Java 17 or 21. Install the packages, then run the scoring job and the comparison:
```
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-nlp.txt
python scripts\spark_score_news.py --etf SILVERBEES.NS
python scripts\news_test.py --etf SILVERBEES.NS --scorer both
```
On Windows, PySpark's Python workers keep a 15-second socket timeout from connection setup, so any batch slower than that silently kills the worker. `spark_news.py` raises it.

**Pipeline, API and dashboard.**
```
docker compose up -d --build
```
This starts Airflow on http://localhost:8080 (the password is in `/opt/airflow/standalone_admin_password.txt`), the API on http://localhost:8000/docs and the dashboard on http://localhost:3000. To use Atlas instead of the local MongoDB, put `MONGODB_URI=...` in a `.env` file. To backfill the paper trades:
```
docker compose exec airflow python /opt/silver-signal/scripts/paper_trade.py --etf SILVERBEES.NS --days 120
```

**R checks.** Run `Rscript R/robustness.R`. It needs the `sandwich` and `lmtest` packages.

## Layout

```
silver_signal/   data, features, baselines, walk-forward evaluation, news filters and
                 features, FinBERT, the Spark job, intraday analysis, paper trading
scripts/         command-line entry points
R/               robustness checks
api/             FastAPI service
dashboard/       React dashboard
airflow/dags/    the daily pipeline
sql/             BigQuery query for GDELT headlines
tests/           look-ahead, news cut-off, filters, Spark vs pandas, API
```

## Limitations

- `SI=F` is a continuous futures series, so it jumps when contracts roll.
- Daily silver bars only approximate the overnight window; the intraday results use hourly bars.
- Around 1,000 trading days: hit rates near 52% are indistinguishable from chance, so read the intervals.
- NSE's official close is a volume-weighted average of the last 30 minutes, not a single tradable price.
- GDELT has no headlines for 17 days in June 2025; those sessions are flagged rather than treated as quiet.

Not financial advice.
