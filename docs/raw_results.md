# Raw output

Printed tables kept for reference. The write-up is in the README.

## Synthetic data (pipeline check)

```
1031 trading days, 2022-09-05 to 2026-10-15  [SYNTHETIC]

Forecast accuracy (walk-forward, out of sample)
target           model  days  direction_calls  hit_rate  hit_low  hit_high  mae_bps  rank_corr
ret_cc            zero   911                0       NaN      NaN       NaN  186.676        NaN
ret_cc historical_mean   911              911     0.508    0.476     0.541  186.670     -0.112
ret_cc       yesterday   911              911     0.483    0.451     0.515  265.751      0.027
ret_cc  overnight_rule   911              911     0.648    0.617     0.679  167.342      0.436
ret_oc            zero   911                0       NaN      NaN       NaN   89.035        NaN
ret_oc historical_mean   911              911     0.468    0.435     0.500   89.262     -0.087
ret_oc       yesterday   911              911     0.479    0.446     0.511  207.603      0.006
ret_oc  overnight_rule   911              911     0.468    0.435     0.500   89.304     -0.091
ret_oc        gap_rule   911              911     0.460    0.428     0.492   89.371     -0.078

Trading ret_oc: buy at open, sell at close, 10 bps round trip
       strategy  trades  total_return  annual_return  annual_vol  sharpe  max_drawdown
historical_mean       0         0.000          0.000       0.000     NaN         0.000
      yesterday     468        -0.405         -0.134       0.127  -1.070        -0.434
 overnight_rule       4         0.019          0.005       0.010   0.549        -0.006
       gap_rule      14        -0.082         -0.023       0.026  -0.878        -0.085
 buy_every_open     911        -0.619         -0.235       0.176  -1.429        -0.656
   buy_and_hold       1         0.971          0.206       0.381   0.683        -0.378
```

## HDFC Silver ETF, real data (only 397 days on Yahoo, March 2025 onwards)

```
397 trading days, 2025-03-05 to 2026-10-16 [Real]

Forecast accuracy (walk-forward, out of sample)
target           model  days  direction_calls  hit_rate  hit_low  hit_high  mae_bps  rank_corr
ret_cc            zero   277                0       NaN      NaN       NaN  252.601        NaN
ret_cc historical_mean   277              276     0.540    0.481     0.599  251.997     -0.001
ret_cc       yesterday   277              275     0.502    0.443     0.561  362.460     -0.005
ret_cc  overnight_rule   277              276     0.623    0.566     0.680  235.430      0.356
ret_oc            zero   277                0       NaN      NaN       NaN  168.066        NaN
ret_oc historical_mean   277              276     0.511    0.452     0.570  171.148     -0.093
ret_oc       yesterday   277              275     0.513    0.454     0.572  306.697     -0.029
ret_oc  overnight_rule   277              276     0.518    0.459     0.577  170.786      0.144
ret_oc        gap_rule   277              276     0.467    0.409     0.526  176.261      0.002

Trading ret_oc: buy at open, sell at close, 10 bps round trip
       strategy  trades  total_return  annual_return  annual_vol  sharpe  max_drawdown
historical_mean       0         0.000          0.000       0.000     NaN         0.000
      yesterday     146        -0.445         -0.415       0.309  -1.573        -0.450
 overnight_rule      64         0.277          0.249       0.165   1.433        -0.106
       gap_rule      51        -0.454         -0.423       0.250  -2.068        -0.461
 buy_every_open     277        -0.498         -0.466       0.416  -1.298        -0.553
   buy_and_hold       1         0.754          0.667       0.618   1.151        -0.460
```

## SILVERBEES (Nippon India Silver ETF), real data

```
1016 trading days, 2022-09-05 to 2026-10-16

Forecast accuracy (walk-forward, out of sample)
target           model  days  direction_calls  hit_rate  hit_low  hit_high  mae_bps  rank_corr
ret_cc            zero   896                0       NaN      NaN       NaN  145.464        NaN
ret_cc historical_mean   896              885     0.532    0.499     0.565  145.285     -0.013
ret_cc       yesterday   896              874     0.517    0.484     0.550  205.488      0.022
ret_cc  overnight_rule   896              885     0.671    0.640     0.702  125.428      0.455
ret_oc            zero   896                0       NaN      NaN       NaN   85.716        NaN
ret_oc historical_mean   896              886     0.508    0.475     0.541   86.919      0.010
ret_oc       yesterday   896              875     0.521    0.488     0.554  171.931      0.023
ret_oc  overnight_rule   896              886     0.559    0.526     0.591   86.471      0.154
ret_oc        gap_rule   896              886     0.453    0.420     0.485   92.100     -0.149

Trading ret_oc: buy at open, sell at close, 10 bps round trip
       strategy  trades  total_return  annual_return  annual_vol  sharpe  max_drawdown
historical_mean       0         0.000          0.000       0.000     NaN         0.000
      yesterday     451        -0.694         -0.283       0.178  -1.772        -0.701
 overnight_rule     134        -0.025         -0.007       0.103  -0.017        -0.140
       gap_rule     101        -0.485         -0.170       0.121  -1.474        -0.503
 buy_every_open     896        -0.872         -0.439       0.236  -2.324        -0.873
   buy_and_hold       1         2.098          0.374       0.370   1.051        -0.450
```

## SILVERBEES news test

```
Correlation of each news mood with the overnight rule's mistakes (open-to-close):
  tone_metals  -0.024
  tone_us      -0.027
  tone_india   -0.034

Forecast accuracy on open-to-close (walk-forward, out of sample)
         model  days  direction_calls  hit_rate  hit_low  hit_high  mae_bps  rank_corr
overnight_rule   896              886     0.559    0.526     0.591   86.471      0.154
     news_only   896              886     0.503    0.470     0.536   87.888     -0.002
overnight+news   896              886     0.554    0.521     0.587   87.762      0.140

Trading: buy at open, sell at close when the forecast beats 10 bps
      strategy  trades  total_return  annual_return  annual_vol  sharpe  max_drawdown
overnight_rule     134        -0.025         -0.007       0.103  -0.017        -0.140
     news_only       3        -0.008         -0.002       0.006  -0.401        -0.013
overnight+news     127        -0.015         -0.004       0.105   0.014        -0.142
buy_every_open     896        -0.872         -0.439       0.236  -2.324        -0.873
  buy_and_hold       1         2.098          0.374       0.370   1.051        -0.450
```

## SILVERBEES intraday check (hourly silver)

```
SILVERBEES.NS: 512 sessions with hourly silver, 2024-05-29 to 2026-10-14
Total daytime return, ETF:            -50.8%
Total daytime return, silver in INR:  +37.5%
Total daytime gap, ETF minus silver:  -64.2%
Average daily gap: -19.3 bps  (t = -3.6)
Daytime correlation, ETF vs silver:   0.67
Opening premium vs giveback: slope -0.62, correlation -0.57

              days  open_premium_bps  etf_daytime_bps  silver_daytime_bps  gap_bps
1 lowest       103            -115.3             58.1                 7.8     51.1
2              102             -26.2             30.2                12.2     18.1
3              102              23.4            -26.4               -12.4    -14.3
4              102              54.7            -19.1                31.5    -50.3
5 highest      103             166.1           -105.1                -4.0   -101.0
```
