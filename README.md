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

Run it and paste your numbers here. On synthetic data (where silver drives the ETF by construction) the overnight rule calls close-to-close direction about 65% of the time, and has no edge on open-to-close. That gap is the whole point of the project.

| Target | Best baseline | Hit rate (95% interval) | Rank corr. | Backtest Sharpe after costs |
|---|---|---|---|---|
| close-to-close | | | | n/a |
| open-to-close | | | | |
| open-to-close + news | | | | |

## Setup (Windows)

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
python scripts\run_baselines.py --synthetic   # check everything runs, no network
python scripts\run_baselines.py               # real data, cached in data\raw\
```

Options: `--refresh` re-downloads prices, `--cost-bps 15` sets the round-trip cost (default 10 bps; use what your broker actually charges plus the spread), `--min-train` and `--step` control the walk-forward windows. Results are written to `results\real\`.

## Layout

```
silver_signal/
  config.py      tickers, market hours, cost assumption
  data.py        Yahoo Finance download and CSV cache
  features.py    one row per trading day, no look-ahead
  baselines.py   the models to beat
  evaluate.py    walk-forward, hit rate, backtest
  news.py        assigns headlines to sessions safely; scoring is yours
  synthetic.py   fake data with the real timing, for tests
scripts/run_baselines.py
tests/           look-ahead, news cut-off and walk-forward checks
PLAN.md          what to build next, week by week
```

## Known limitations

- `SI=F` is a continuous futures series, so it jumps when contracts roll. Those days produce fake "overnight moves". Detect them or switch to a spot series.
- Daily bars only approximate the overnight window (they run roughly 03:30 to 03:30 IST, not 15:30 to 09:15). `PLAN.md` week 2 replaces this with hourly data.
- The ETF has traded since September 2022, so there are only around 1,000 trading days. Hit rates near 52% are indistinguishable from chance at this sample size; check the interval.
- The ETF can trade at a premium or discount to the value of its silver, which no price model here captures yet.

Not financial advice. Paper trade any signal for a few months before risking money on it.
