"""Trade normalisation and per-cell statistics. Pure functions, no I/O."""
import json
import math

import numpy as np
from scipy.stats import t as student_t

_SCALAR = (str, int, float, bool, type(None))
_TIME_KEYS = ("entry_bar", "entry_idx", "entry_time", "opened_at", "t")


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _meta(t):
    m = t.get("metadata")
    try:
        return json.loads(m or "{}") if isinstance(m, str) else (m or {})
    except ValueError:
        return {}


def normalize(trades):
    """Accepts legacy-backtest trades (r/net), bt2 trades (R/net_pnl) or paper-trading DB rows (net_pnl/risk_amount + metadata).
    Returns (rows, dropped). Each row: strategy, regime, symbol, R, net, seq, tags(dict of scalar extras).
    A trade whose R cannot be determined as a finite number is DROPPED and counted - never defaulted to 0."""
    rows, dropped = [], 0
    for i, t in enumerate(trades):
        meta = _meta(t)
        R = _num(t.get("R", t.get("r")))
        net = _num(t.get("net_pnl", t.get("net")))
        if R is None and net is not None:
            risk = _num(t.get("initial_risk", t.get("risk_amount")))
            R = net / risk if risk and risk > 0 else None
        if R is None:
            dropped += 1
            continue
        key = next((k for k in _TIME_KEYS if t.get(k) is not None), None)
        seq = t[key] if key else i
        tags = {k: v for k, v in t.items() if isinstance(v, _SCALAR) and k not in ("R", "r", "net", "net_pnl", "metadata")}
        for k, v in meta.items():
            if isinstance(v, _SCALAR):
                tags.setdefault(k, v)
        rows.append({"strategy": str(t.get("strategy") or meta.get("strategy") or "unknown"),
                     "regime": str(t.get("regime") or meta.get("regime") or "unknown"),
                     "symbol": str(t.get("symbol") or "unknown"), "R": R, "net": net, "seq": seq, "tags": tags, "_i": i})
    return rows, dropped


def ordered(rows):
    """Chronological order when every row has a comparable sequence key, else input order."""
    try:
        return sorted(rows, key=lambda r: (r["seq"], r["_i"]))
    except TypeError:
        return sorted(rows, key=lambda r: r["_i"])


def bh_reject(pvals, q):
    """Benjamini-Hochberg step-up: boolean list, True = rejected at false-discovery rate q. NaN p-values never reject."""
    p = np.array([1.0 if (x is None or x != x) else x for x in pvals], dtype=float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    passed = p[order] <= q * (np.arange(1, m + 1) / m)
    k = int(np.max(np.flatnonzero(passed)) + 1) if passed.any() else 0
    out = np.zeros(m, dtype=bool)
    out[order[:k]] = True
    return out.tolist()


def boot_ci(R, n_boot=2000, seed=0, lo=5, hi=95):
    R = np.asarray(R, dtype=float)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(int(np.ceil(n_boot / 250))):
        means.append(R[rng.integers(0, len(R), size=(250, len(R)))].mean(axis=1))
    m = np.concatenate(means)[:n_boot]
    return float(np.percentile(m, lo)), float(np.percentile(m, hi))


def cell_stats(R, chunks=3, min_chunk=5, n_boot=2000, seed=0):
    """R: chronological per-trade R multiples. One-sided p-values from a t-test on the mean; bootstrap CI;
    time stability = number of chronological chunks (with >= min_chunk trades) whose mean is positive."""
    R = np.asarray(R, dtype=float)
    n = len(R)
    out = {"n": n, "mean_R": None, "sd_R": None, "t_stat": None, "p_pos": None, "p_neg": None, "ci_low": None, "ci_high": None,
           "win_rate": None, "profit_factor": None, "sharpe_per_trade": None, "chunks_positive": 0, "chunks_used": 0}
    if n == 0:
        return out
    out["mean_R"], out["win_rate"] = float(R.mean()), float((R > 0).mean())
    gains, losses = R[R > 0].sum(), -R[R < 0].sum()
    out["profit_factor"] = float(gains / losses) if losses > 0 else None
    if n >= 3:
        sd = float(R.std(ddof=1))
        out["sd_R"] = sd
        if sd > 0:
            t = out["mean_R"] / (sd / math.sqrt(n))
            out.update(t_stat=float(t), p_pos=float(student_t.sf(t, n - 1)), p_neg=float(student_t.cdf(t, n - 1)),
                       sharpe_per_trade=out["mean_R"] / sd)
        else:                                                      # zero variance: decided by sign only
            out.update(p_pos=0.0 if out["mean_R"] > 0 else 1.0, p_neg=0.0 if out["mean_R"] < 0 else 1.0, sharpe_per_trade=0.0)
        out["ci_low"], out["ci_high"] = boot_ci(R, n_boot, seed)
    parts = [p for p in np.array_split(R, chunks) if len(p) >= min_chunk]
    out["chunks_used"], out["chunks_positive"] = len(parts), sum(1 for p in parts if p.mean() > 0)
    return out
