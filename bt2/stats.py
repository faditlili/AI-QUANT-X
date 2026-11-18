"""Statistical validation. Formulas follow Bailey & Lopez de Prado (PSR / Deflated Sharpe / PBO via CSCV).
Sharpe ratios here are PER-PERIOD (not annualised) - they must be consistent with the number of observations used."""
import itertools
import math

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def sharpe(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 3:
        raise ValueError("need at least 3 observations")
    sd = x.std(ddof=1)
    return 0.0 if sd == 0 else float(x.mean() / sd)


def skew_kurt(x):
    """Population skewness and RAW (non-excess) kurtosis."""
    x = np.asarray(x, dtype=float)
    sd = x.std(ddof=0)
    if sd == 0:
        return 0.0, 3.0
    z = (x - x.mean()) / sd
    return float(np.mean(z ** 3)), float(np.mean(z ** 4))


def psr(sr, sr_benchmark, n, skew, kurt):
    """Probabilistic Sharpe Ratio: P(true SR > benchmark) given sample length and non-normality."""
    denom2 = 1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2
    if denom2 <= 0 or n < 2:
        return float("nan")
    return float(norm.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom2)))


def expected_max_sr(n_trials, sr_variance):
    """Expected maximum Sharpe among n_trials unskilled strategies (the selection-bias benchmark SR0)."""
    if n_trials < 2:
        return 0.0
    return math.sqrt(max(sr_variance, 0.0)) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
                                              + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(returns, trial_sharpes):
    """DSR: probability that the chosen strategy's SR beats what the best of N tried strategies would show by luck.
    `trial_sharpes`: per-period Sharpe of EVERY variant tried (including the chosen one). Needs N >= 2."""
    trial_sharpes = np.asarray(trial_sharpes, dtype=float)
    if len(trial_sharpes) < 2:
        raise ValueError("deflated Sharpe needs the Sharpe of every variant tried (N >= 2); use psr() for a single test")
    r = np.asarray(returns, dtype=float)
    sr = sharpe(r)
    sk, ku = skew_kurt(r)
    sr0 = expected_max_sr(len(trial_sharpes), float(np.var(trial_sharpes, ddof=1)))
    return {"dsr": psr(sr, sr0, len(r), sk, ku), "sharpe": sr, "benchmark_sr0": sr0, "n_trials": int(len(trial_sharpes)),
            "n_obs": int(len(r)), "skew": sk, "kurtosis": ku}


def pbo_from_logits(logits):
    """PBO = P(lambda <= 0): share of splits where the in-sample winner ranks at or below the out-of-sample median."""
    return float(np.mean(np.asarray(logits, dtype=float) <= 0))


def pbo_cscv(matrix, n_blocks=10):
    """Probability of Backtest Overfitting via combinatorially symmetric cross-validation.
    matrix: T x N array of per-period returns for N variants. For every split of the blocks into halves, pick the best
    in-sample variant and see where it ranks out-of-sample. PBO = share of splits where it ranks at/below the median."""
    M = np.asarray(matrix, dtype=float)
    if M.ndim != 2 or M.shape[1] < 2:
        raise ValueError("matrix must be T x N with N >= 2 variants")
    if n_blocks % 2 or n_blocks < 4:
        raise ValueError("n_blocks must be even and >= 4")
    T = (M.shape[0] // n_blocks) * n_blocks
    if T < n_blocks * 5:
        raise ValueError("not enough observations for %d blocks" % n_blocks)
    M = M[:T]
    size, N = T // n_blocks, M.shape[1]
    blocks = M.reshape(n_blocks, size, N)
    s1, s2 = blocks.sum(axis=1), (blocks ** 2).sum(axis=1)             # per-block sum / sum of squares, (B, N)

    def sr_of(idx):
        cnt = len(idx) * size
        mean = s1[idx].sum(axis=0) / cnt
        var = np.maximum(s2[idx].sum(axis=0) / cnt - mean ** 2, 0.0) * cnt / (cnt - 1)
        sd = np.sqrt(var)
        return np.where(sd > 0, mean / np.where(sd > 0, sd, 1), 0.0)

    logits = []
    for ins in itertools.combinations(range(n_blocks), n_blocks // 2):
        ins = list(ins)
        oos = [b for b in range(n_blocks) if b not in ins]
        best = int(np.argmax(sr_of(ins)))
        sr_oos = sr_of(oos)
        rank = 1 + int(np.sum(sr_oos < sr_oos[best])) + 0.5 * int(np.sum(sr_oos == sr_oos[best]) - 1)
        w = rank / (N + 1)
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return {"pbo": pbo_from_logits(logits), "n_splits": int(len(logits)), "n_variants": int(N), "median_logit": float(np.median(logits))}


def max_drawdown(curve):
    c = np.asarray(curve, dtype=float)
    if len(c) == 0:
        return 0.0
    peak = np.maximum.accumulate(c)
    return float(np.max((peak - c) / np.where(peak > 0, peak, np.nan)))


def trade_returns(result):
    """Per-trade fractional return = net_pnl / equity at the entry bar (in exit order)."""
    curve = result["curve"]
    return [t["net_pnl"] / curve[t["entry_bar"]] for t in sorted(result["trades"], key=lambda t: (t["exit_bar"], t["entry_bar"]))]


def monte_carlo(returns, mode="shuffle", n=2000, seed=7, ruin_drawdown=0.5):
    """Trade-sequence simulation on fractional per-trade returns (compounded).
    shuffle  : same trades, random ORDER  -> final equity is fixed, only path / drawdown risk varies;
    bootstrap: resample WITH replacement  -> also varies the final outcome."""
    r = np.asarray(returns, dtype=float)
    if len(r) < 10:
        raise ValueError("need at least 10 trades")
    if mode not in ("shuffle", "bootstrap"):
        raise ValueError("mode must be shuffle or bootstrap")
    rng = np.random.default_rng(seed)
    finals, dds = np.empty(n), np.empty(n)
    for k in range(n):
        seq = rng.permutation(r) if mode == "shuffle" else rng.choice(r, size=len(r), replace=True)
        eq = np.concatenate([[1.0], np.cumprod(1 + seq)])
        finals[k], dds[k] = eq[-1] - 1, max_drawdown(eq)
    q = lambda a, p: float(np.percentile(a, p))
    return {"mode": mode, "n_sims": n, "final_p5": q(finals, 5), "final_p50": q(finals, 50), "final_p95": q(finals, 95),
            "max_dd_p50": q(dds, 50), "max_dd_p95": q(dds, 95), "max_dd_p99": q(dds, 99),
            "prob_loss": float(np.mean(finals < 0)), "prob_ruin": float(np.mean(dds >= ruin_drawdown)), "ruin_drawdown": ruin_drawdown}


def trade_metrics(trades, seed=0, n_boot=1000):
    R = np.array([t["R"] for t in trades], dtype=float)
    pnl = np.array([t["net_pnl"] for t in trades], dtype=float)
    n = len(R)
    out = {"n": n, "win_rate": None, "expectancy_R": None, "expectancy_ci_low": None, "avg_win_R": None, "avg_loss_R": None,
           "profit_factor": None, "total_pnl": float(pnl.sum()) if n else 0.0, "t_stat": None, "sharpe_per_trade": None}
    if n == 0:
        return out
    wins, losses = R > 0, R < 0
    out.update(win_rate=float(wins.mean()), expectancy_R=float(R.mean()),
               avg_win_R=float(R[wins].mean()) if wins.any() else None, avg_loss_R=float(R[losses].mean()) if losses.any() else None,
               profit_factor=(float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else None))
    if n >= 3:
        sd = R.std(ddof=1)
        out["sharpe_per_trade"] = float(R.mean() / sd) if sd > 0 else 0.0
        out["t_stat"] = float(R.mean() / (sd / math.sqrt(n))) if sd > 0 else None
        rng = np.random.default_rng(seed)
        boots = R[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
        out["expectancy_ci_low"] = float(np.percentile(boots, 5))
    return out


def breakdown(trades, key, min_trades=30):
    """Metrics per group. key: field name or callable. Groups with fewer than min_trades are marked unreliable
    (do not draw conclusions from them; with many groups some will look good by chance alone)."""
    kf = key if callable(key) else (lambda t: t.get(key, "unknown"))
    groups = {}
    for t in trades:
        groups.setdefault(kf(t), []).append(t)
    out = {}
    for g, ts in sorted(groups.items(), key=lambda kv: str(kv[0])):
        m = trade_metrics(ts)
        m["reliable"] = m["n"] >= min_trades
        out[g] = m
    return out


def liquidity_bucket(trade, low=0.01, high=0.05):
    """Tag by the share of the entry bar's volume the order took (thresholds are explicit parameters, not tuned)."""
    p = trade.get("entry_participation")
    if p is None or p != p:
        return "unknown"
    return "thin" if p >= high else ("normal" if p >= low else "deep")
