# silver-signal

Does the news tell you anything about **HDFC Silver ETF** (NSE: HDFCSILVER) that last night's silver and rupee moves don't already?

The ETF holds physical silver, so its price is mostly the international silver price converted into rupees. By the time NSE opens at 09:15 IST, silver has traded all night in New York and London. A news model that ignores this will look clever and still lose to a one-line rule. So this project starts from that rule and asks whether headlines add anything on top of it.

## The question, precisely

At 09:15 IST each trading day, using only information published before then:

1. Can we predict today's **close-to-close** return? (Includes the opening gap. Easy to predict, impossible to trade from a 09:15 forecast.)
2. Can we predict today's **open-to-close** return? (What you can actually capture by buying at the open and selling at the close.)
3. Does adding news beat the baselines below on question 2, after trading costs?

## Timeline (IST)

```
 day t-1                                         day t
 15:30 ETF closes ... ~03:30 COMEX daily bar ... 09:15 ETF opens ........ 15:30 ETF closes
                      (Yahoo dates it t-1)       ^ forecast made here
```

The newest silver or USD/INR bar a forecast for day *t* may use is the last one dated strictly **before** *t*. A headline may only inform the first session whose 09:15 open comes **after** it was published. Both rules are enforced in code and tested.

## Baselines

| Model | Idea |
|---|---|
| `zero` | Predict no change (the bar for error metrics) |
| `historical_mean` | Predict the average return so far |
| `yesterday` | Today repeats yesterday |
| `overnight_rule` | Today's move ≈ overnight silver move × rupee move, with a fitted slope |
| `gap_rule` | Open-to-close only: does the day continue or reverse its opening gap? |

Every model is scored **walk-forward**: fit on everything before a 20-day block, predict the block, move on. Nothing is ever tested on data it trained on.

## Results

Main results use **Nippon India Silver ETF (SILVERBEES)** as a proxy, because Yahoo Finance only has HDFC Silver ETF prices from March 2025. Both ETFs hold physical silver and track the same domestic silver price. SILVERBEES gives 1,016 trading days (Sept 2022 to Oct 2026), of which 896 are scored out of sample. Raw tables, including the HDFC-only run, are in [docs/raw_results.md](docs/raw_results.md).

### 1. Overnight silver and rupee moves explain most of the ETF's day

| Target | Model | Hit rate (95% interval) | Rank corr. |
|---|---|---|---|
| Close-to-close | overnight rule | **67.1%** (64.0–70.2%) | 0.455 |
| Close-to-close | historical mean | 53.2% (49.9–56.5%) | −0.013 |
| Open-to-close | overnight rule | **55.9%** (52.6–59.1%) | 0.154 |
| Open-to-close | historical mean | 50.8% (47.5–54.1%) | 0.010 |
| Open-to-close | gap rule | 45.3% (42.0–48.5%) | −0.149 |

The rule calls close-to-close direction two days in three. On the tradable open-to-close return it keeps a small edge whose interval sits above 50%. The gap rule is worse than chance: whether a day continues or reverses its opening gap is unstable, and the fitted direction keeps flipping out of sample.

### 2. That edge does not make money as "buy at the open"

Buying at the open and selling at the close whenever the forecast beats a 10 bp round-trip cost: 134 trades, −2.5% in total, Sharpe about 0. The skill is mostly in spotting down days, which a long-only strategy can only sit out.

### 3. News, as measured by GDELT tone, adds nothing

About 234,000 English market headlines (2022–2026), each assigned only to the first session that opens after it was published, averaged into three daily moods: metals, US macro and India.

| Model (open-to-close) | Hit rate (95% interval) | Rank corr. |
|---|---|---|
| overnight rule | 55.9% (52.6–59.1%) | 0.154 |
| news only | 50.3% (47.0–53.6%) | −0.002 |
| overnight rule + news | 55.4% (52.1–58.7%) | 0.140 |

The news moods' correlation with the overnight rule's errors is −0.02 to −0.03, inside the ±0.07 noise band for 896 days. GDELT's general-purpose tone is a blunt measure; a finance-specific scorer (FinBERT, or an LLM that knows "rate cuts" are good for silver) is the next test.

### 4. The ETF's gains came overnight; Indian trading hours lost money

| Period | Overnight (close → next open) | Daytime (open → close) | Up days, daytime |
|---|---|---|---|
| All days | +1,297% | **−73%** | 48% |
| Excluding 59 suspect Yahoo bars | +1,349% | −71% | 49% |
| 2023 | +97% | −41% | 42% |
| 2024 | +87% | −33% | 50% |
| 2025 | +185% | −13% | 54% |
| 2026 to 16 Oct | +5% | −15% | 51% |

Before costs. Yahoo's opens were checked against an official NSE download with `scripts/check_prices.py`: at least 95% match within 0.2%. Dropping every suspect bar (open equal to close, or to the previous close) barely changes the result, and daytime returns are negative in every full year.

### 5. Why: the ETF opens at a premium to its silver and gives it back

`scripts/intraday_check.py` compares SILVERBEES with hourly COMEX silver converted to rupees, over the same Indian trading hours (512 sessions, May 2024 to Oct 2026; silver's morning price is taken at 09:30 IST, the first hourly bar after the open).

| | Daytime total |
|---|---|
| SILVERBEES | **−50.8%** |
| Silver in rupees, same hours | **+37.5%** |
| Gap, ETF minus silver | −64.2% (average −19.3 bps a day, t = −3.6) |

Silver did not fall during Indian hours; it rose. The ETF fell anyway. Grouping days by how far the ETF's open ran ahead of silver's overnight move:

| Opening premium (quintile) | Avg premium | ETF daytime | Silver daytime | Gap |
|---|---|---|---|---|
| 1 (lowest) | −115 bps | +58 bps | +8 bps | +51 bps |
| 2 | −26 bps | +30 bps | +12 bps | +18 bps |
| 3 | +23 bps | −26 bps | −12 bps | −14 bps |
| 4 | +55 bps | −19 bps | +32 bps | −50 bps |
| 5 (highest) | +166 bps | −105 bps | −4 bps | −101 bps |

The richer the open, the bigger the same-day giveback (slope −0.62, correlation −0.57). Opening cheap is followed by gains.

Caveat: the slope is partly mechanical, because the opening price appears in both the premium and the giveback, so noise in it (an odd opening-auction print, or silver measured at 09:30 rather than 09:15) pushes the slope negative by itself. The average daily gap does not share that problem and is the stronger evidence. Next check: measure the giveback from 10:15 using hourly ETF prices, so the opening price is used only once.

### 6. What this does not mean

It is not a free trade. NSE's official close is a volume-weighted average of the last 30 minutes, not a single price you can trade at, and costs on a daily round trip add up quickly.

## Setup (Windows)

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
python scripts\run_baselines.py --synthetic                 # check everything runs, no network
python scripts\run_baselines.py --etf SILVERBEES.NS         # baselines on real prices
python scripts\news_test.py --etf SILVERBEES.NS             # does news help? (needs data\news\headlines.csv)
python scripts\check_prices.py nse_file.csv --etf SILVERBEES.NS   # Yahoo vs official NSE prices
python scripts\intraday_check.py --etf SILVERBEES.NS        # is the daytime drop the ETF or silver itself?
```

Options: `--refresh` re-downloads prices, `--cost-bps 15` sets the round-trip cost (default 10 bps; use what your broker actually charges plus the spread), `--min-train` and `--step` control the walk-forward windows. Results are written to `results\`.

News: `python scripts\make_gdelt_sql.py --start 2024-01-01 --end 2025-01-01` prints a BigQuery query (a ready copy is in `sql\gdelt_headlines.sql`). Save the results as CSV in `data\news\raw\`, then `python scripts\clean_news.py` builds `data\news\headlines.csv` and prints a quality report.

## FinBERT news scores with Spark

Scores every headline with [FinBERT](https://huggingface.co/ProsusAI/finbert), a BERT model trained on financial news, in parallel across your CPU cores with Spark, then builds daily news moods with Spark SQL. The Spark job is tested to give exactly the same daily numbers as the pandas code used everywhere else.

1. Install Java 17 or 21 (Spark needs it): [Eclipse Temurin](https://adoptium.net), and tick "Set JAVA_HOME" in the installer. Check with `java -version` in a new terminal.
2. Install the extra packages. On Windows, install the smaller CPU-only PyTorch first:
   ```
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install -r requirements-nlp.txt
   ```
3. A quick timing run on 2,000 headlines (downloads FinBERT, about 440 MB, once):
   ```
   python scripts\spark_score_news.py --etf SILVERBEES.NS --limit 2000
   ```
4. All headlines (writes `data\news\headlines_scored.parquet` and `data\news\daily_news.parquet`):
   ```
   python scripts\spark_score_news.py --etf SILVERBEES.NS
   ```
5. Compare FinBERT with GDELT tone:
   ```
   python scripts\news_test.py --etf SILVERBEES.NS --scorer both
   ```

News moods use five themes, because good news for the dollar is usually bad for silver while a Fed rate cut is usually good: metals, fed, dollar, us_data, india. `--scorer keyword` runs the whole pipeline with a crude stand-in scorer, for checking setup without the model. A "Did not find winutils.exe" warning on Windows is harmless here: output is written through pandas, not Hadoop.

## Layout

```
silver_signal/
  config.py         tickers, market hours, cost assumption
  data.py           Yahoo Finance download and CSV cache
  features.py       one row per trading day, no look-ahead
  baselines.py      the models to beat
  evaluate.py       walk-forward, hit rate, backtest
  news.py           assigns headlines to sessions safely
  news_filter.py    what counts as a relevant headline (shared by SQL and Python)
  news_features.py  daily news moods per theme
  finbert.py        FinBERT headline scoring
  spark_news.py     the Spark job: parallel scoring and Spark SQL aggregation
  intraday.py       hourly silver vs the ETF during Indian trading hours
  synthetic.py      fake data with the real timing, for tests
scripts/            run_baselines, news_test, check_prices, intraday_check,
                    make_gdelt_sql, clean_news, spark_score_news
sql/                ready-to-paste BigQuery query
tests/              look-ahead, news cut-off, filters, walk-forward
docs/               raw output tables
PLAN.md             what to build next, week by week
```

## Known limitations

- `SI=F` is a continuous futures series, so it jumps when contracts roll. Those days produce fake "overnight moves". Detect them or switch to a spot series.
- Daily bars only approximate the overnight window (they run roughly 03:30 to 03:30 IST, not 15:30 to 09:15). `PLAN.md` week 2 replaces this with hourly data.
- Yahoo only has HDFC Silver ETF prices from March 2025, so the main results use SILVERBEES (`--etf SILVERBEES.NS`). Around 1,000 trading days in total: hit rates near 52% are indistinguishable from chance, so always read the interval.
- NSE's official closing price is a volume-weighted average of the last 30 minutes, not a single tradable price.
- GDELT has no headlines for 17 days in June 2025. Those sessions are flagged as `news_missing` rather than treated as quiet.
- The ETF can trade at a premium or discount to the value of its silver, which no price model here captures yet.

Not financial advice. Paper trade any signal for a few months before risking money on it.
