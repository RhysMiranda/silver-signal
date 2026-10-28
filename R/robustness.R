# Robustness checks for the first-hour result, in R.
#
#   Rscript R/robustness.R
#
# Reads results/intraday_1015_silverbees/daily.csv (written by
# scripts/intraday_1015.py) and asks whether the first-hour giveback survives:
#   1. autocorrelation-robust (Newey-West) standard errors
#   2. a block bootstrap of the "wait until 10:15" advantage
#   3. dropping extreme days, and using medians instead of means
#   4. each half-year on its own
# Needs: install.packages(c("sandwich", "lmtest"))

suppressPackageStartupMessages({ library(sandwich); library(lmtest) })

args <- commandArgs(trailingOnly = TRUE)
path <- if (length(args)) args[1] else "results/intraday_1015_silverbees/daily.csv"
d <- read.csv(path)
d$date <- as.Date(d$date)
n <- nrow(d)
bps <- function(x) sprintf("%+.1f bps", 1e4 * x)
cat(sprintf("%d sessions, %s to %s\n\n", n, min(d$date), max(d$date)))

# 1. Means and slopes with Newey-West standard errors -----------------------
hac_mean <- function(y) {
  m <- lm(y ~ 1)
  ct <- coeftest(m, vcov = NeweyWest(m, prewhite = FALSE))
  c(est = ct[1, 1], t = ct[1, 3], p = ct[1, 4])
}
hac_slope <- function(y, x) {
  m <- lm(y ~ x)
  ct <- coeftest(m, vcov = NeweyWest(m, prewhite = FALSE))
  c(est = ct[2, 1], t = ct[2, 3], p = ct[2, 4])
}
rows <- list(
  "Gap 09:15-10:15 (mean)"   = hac_mean(d$gap_first_hour),
  "Gap 10:15-15:30 (mean)"   = hac_mean(d$gap_rest),
  "ETF 09:15-10:15 (mean)"   = hac_mean(d$etf_first_hour),
  "Slope 09:15-10:15"        = hac_slope(d$gap_first_hour, d$open_premium),
  "Slope 10:15-15:30"        = hac_slope(d$gap_rest, d$open_premium)
)
tab <- do.call(rbind, rows)
cat("1. Newey-West (autocorrelation-robust)\n")
for (r in rownames(tab)) {
  e <- tab[r, "est"]
  shown <- if (grepl("Slope", r)) sprintf("%+.2f", e) else bps(e)
  cat(sprintf("   %-24s %12s   t = %+5.1f   p = %.4f\n", r, shown, tab[r, "t"], tab[r, "p"]))
}

# 2. Block bootstrap of the 10:15 advantage ----------------------------------
# Buying at 10:15 instead of 09:15 just skips the first hour, so the advantage
# in log terms is -sum(log(1 + etf_first_hour)). Blocks of 10 days keep any
# short-run dependence intact.
set.seed(1)
adv <- -log1p(d$etf_first_hour)
block <- 10
B <- 5000
starts <- seq_len(n - block + 1)
boot <- replicate(B, {
  s <- sample(starts, ceiling(n / block), replace = TRUE)
  idx <- as.vector(outer(0:(block - 1), s, "+"))[seq_len(n)]
  sum(adv[idx])
})
ci <- quantile(boot, c(0.025, 0.975))
cat(sprintf("\n2. Block bootstrap (%d draws, %d-day blocks)\n", B, block))
cat(sprintf("   Extra return from waiting until 10:15, whole period: %+.1f%% (95%% CI %+.1f%% to %+.1f%%)\n",
            100 * expm1(sum(adv)), 100 * expm1(ci[1]), 100 * expm1(ci[2])))
cat(sprintf("   Share of draws where waiting did worse: %.2f%%\n", 100 * mean(boot <= 0)))

# 3. Outliers ----------------------------------------------------------------
q <- quantile(d$gap_first_hour, c(0.01, 0.99))
trim <- d$gap_first_hour[d$gap_first_hour > q[1] & d$gap_first_hour < q[2]]
cat("\n3. Outliers (first-hour gap)\n")
cat(sprintf("   Median %s; mean without top and bottom 1%% of days %s (t = %+.1f); share of days negative %.0f%%\n",
            bps(median(d$gap_first_hour)), bps(mean(trim)), hac_mean(trim)["t"],
            100 * mean(d$gap_first_hour < 0)))

# 4. Each half-year ------------------------------------------------------------
d$half <- paste0(format(d$date, "%Y"), ifelse(as.integer(format(d$date, "%m")) <= 6, " H1", " H2"))
cat("\n4. By half-year (first-hour gap)\n")
halves <- do.call(rbind, lapply(split(d, d$half), function(g) {
  h <- hac_mean(g$gap_first_hour)
  data.frame(period = g$half[1], days = nrow(g), mean_bps = 1e4 * h[["est"]], t = h[["t"]])
}))
for (i in seq_len(nrow(halves)))
  cat(sprintf("   %s  %3d days  %+6.1f bps  t = %+5.1f\n",
              halves$period[i], halves$days[i], halves$mean_bps[i], halves$t[i]))

out <- file.path(dirname(dirname(path)), "r_robustness")
dir.create(out, showWarnings = FALSE, recursive = TRUE)
write.csv(data.frame(test = rownames(tab), tab, row.names = NULL), file.path(out, "newey_west.csv"), row.names = FALSE)
write.csv(halves, file.path(out, "by_half_year.csv"), row.names = FALSE)
cat(sprintf("\nSaved to %s\n", out))
