"""When does a strategy work or fail? Slice tests with multiple-testing control (so a lucky slice is not reported as a rule).

For each (key, value) slice of ONE strategy's trades, Welch's t-test compares the slice with the strategy's remaining trades.
All slices tested together are corrected with Benjamini-Hochberg. Only slices that survive are called works_when / fails_when;
the rest are listed as 'no evidence'. Numeric keys are bucketed into terciles (edges from the strategy's own trades).
"""
import math

import numpy as np
from scipy.stats import ttest_ind

from bt2.stats import liquidity_bucket

from . import evidence


def _tercile_label(values):
    v = np.array([x for x in values if isinstance(x, (int, float)) and math.isfinite(x)], dtype=float)
    if len(v) < 30:
        return lambda x: None
    lo, hi = np.percentile(v, [33.3, 66.7])
    return lambda x: None if not isinstance(x, (int, float)) or not math.isfinite(x) else ("low" if x <= lo else "high" if x >= hi else "mid")


def find_conditions(trades, strategy, keys=("regime", "symbol", "side"), numeric_keys=(), liquidity=True, min_n=20, q=0.05):
    rows, _ = evidence.normalize(trades)
    mine = [r for r in rows if r["strategy"] == strategy]
    if len(mine) < 2 * min_n:
        return {"strategy": strategy, "n": len(mine), "works_when": [], "fails_when": [], "no_evidence": [], "n_slices_tested": 0,
                "note": "too few trades for slice analysis"}
    feats = []
    for r in mine:
        f = {"regime": r["regime"], "symbol": r["symbol"], **r["tags"]}
        if liquidity and "entry_participation" in r["tags"]:
            f["liquidity"] = liquidity_bucket({"entry_participation": r["tags"]["entry_participation"]})
        feats.append(f)
    names = [k for k in keys if any(k in f for f in feats)] + (["liquidity"] if liquidity and any("liquidity" in f for f in feats) else [])
    for k in numeric_keys:
        lab = _tercile_label([f.get(k) for f in feats])
        for f in feats:
            f[k + "_bucket"] = lab(f.get(k))
        names.append(k + "_bucket")
    R = np.array([r["R"] for r in mine])
    tested = []
    for k in names:
        for val in sorted({str(f[k]) for f in feats if f.get(k) is not None}):
            mask = np.array([str(f.get(k)) == val for f in feats])
            a, b = R[mask], R[~mask]
            if len(a) < min_n or len(b) < min_n:
                continue
            _, p = ttest_ind(a, b, equal_var=False)
            tested.append({"key": k, "value": val, "n": int(len(a)), "mean_R": float(a.mean()), "rest_mean_R": float(b.mean()),
                           "p": None if p != p else float(p)})
    rej = evidence.bh_reject([t["p"] for t in tested], q)
    out = {"strategy": strategy, "n": len(mine), "works_when": [], "fails_when": [], "no_evidence": [], "n_slices_tested": len(tested)}
    for t, r in zip(tested, rej):
        if r and t["mean_R"] > t["rest_mean_R"] and t["mean_R"] > 0:
            out["works_when"].append(t)
        elif r and t["mean_R"] < t["rest_mean_R"] and t["mean_R"] < 0:
            out["fails_when"].append(t)
        else:
            out["no_evidence"].append(t)
    for k in ("works_when", "fails_when"):
        out[k].sort(key=lambda t: -abs(t["mean_R"] - t["rest_mean_R"]))
    return out
