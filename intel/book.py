"""StrategyBook: statistical verdict per (strategy, regime) + regime-aware selection. Fail-closed persistence.

ENABLE needs ALL of: enough trades; mean R > 0; bootstrap 5th percentile of mean R > 0; Benjamini-Hochberg rejection over EVERY
cell examined (so 'best of many cells' luck is controlled); Deflated Sharpe >= dsr_min against the number of cells tried;
time stability (positive in most chronological chunks). DISABLE: enough trades and the bootstrap 95th percentile of mean R < 0.
Everything else is UNPROVEN. Win rate is reported but never used to decide anything.
"""
import json
import math
import os
import time
from dataclasses import asdict, dataclass

import numpy as np

from bt2 import stats as btstats

from . import evidence

SEP = "|"


@dataclass(frozen=True)
class IntelCfg:
    min_trades_enable: int = 30
    min_trades_disable: int = 20
    fdr_q: float = 0.05
    dsr_min: float = 0.80
    min_chunks_positive: int = 2           # of 3 chronological chunks
    shrink_k: float = 20.0                 # empirical-Bayes prior strength (pseudo-trades)
    n_boot: int = 2000
    mode: str = "strict"                   # strict: only ENABLE may trade | probation: UNPROVEN trades at unproven_risk_mult
    unproven_risk_mult: float = 0.5
    seed: int = 0


def cell_key(strategy, regime):
    return "%s%s%s" % (strategy, SEP, regime)


def build_cells(trades, cfg=IntelCfg()):
    rows, dropped = evidence.normalize(trades)
    groups = {}
    for r in evidence.ordered(rows):
        groups.setdefault((r["strategy"], r["regime"]), []).append(r["R"])
    stats = {cell_key(*k): evidence.cell_stats(v, n_boot=cfg.n_boot, seed=cfg.seed) for k, v in groups.items()}
    keys = sorted(stats)
    testable = [k for k in keys if stats[k]["p_pos"] is not None]
    rej_pos = dict(zip(testable, evidence.bh_reject([stats[k]["p_pos"] for k in testable], cfg.fdr_q)))
    n_trials = len(testable)
    for k in keys:
        s = stats[k]
        s["strategy"], s["regime"] = k.split(SEP, 1)
        s["fdr_significant"] = bool(rej_pos.get(k, False))
        s["dsr"] = s["dsr_benchmark_sr0"] = None
        if k in rej_pos and n_trials >= 2 and s["n"] >= 3 and s["sharpe_per_trade"] is not None:
            # Benchmark = expected best Sharpe of n_trials UNSKILLED cells, each measured on as many trades as this one
            # (null variance of a sample Sharpe ~ 1/n). The empirical dispersion of Sharpes ACROSS cells is deliberately not
            # used: it is inflated by real differences between strategies and by tiny noisy cells, which would reject genuine edges.
            R = groups[tuple(k.split(SEP, 1))]
            sk, ku = btstats.skew_kurt(R)
            sr0 = btstats.expected_max_sr(n_trials, 1.0 / s["n"])
            d = btstats.psr(s["sharpe_per_trade"], sr0, s["n"], sk, ku)
            s["dsr_benchmark_sr0"], s["dsr"] = float(sr0), (None if d != d else float(d))
        s["verdict"], s["reasons"] = _verdict(s, cfg)
    return stats, dropped, len(rows)


def _verdict(s, cfg):
    n, mean = s["n"], s["mean_R"]
    if n >= cfg.min_trades_disable and s["ci_high"] is not None and s["ci_high"] < 0:
        return "DISABLE", ["mean R %.3f with 95%% bootstrap upper bound %.3f < 0" % (mean, s["ci_high"])]
    why = []
    if n < cfg.min_trades_enable:
        why.append("only %d trades (< %d)" % (n, cfg.min_trades_enable))
    if mean is None or mean <= 0:
        why.append("mean R is not positive")
    if s["ci_low"] is None or s["ci_low"] <= 0:
        why.append("bootstrap lower bound of mean R is not above 0")
    if not s["fdr_significant"]:
        why.append("not significant after multiple-testing control (FDR q=%.2f)" % cfg.fdr_q)
    if s["dsr"] is None or s["dsr"] < cfg.dsr_min:
        why.append("deflated Sharpe %s < %.2f" % ("n/a" if s["dsr"] is None else "%.2f" % s["dsr"], cfg.dsr_min))
    if s["chunks_positive"] < cfg.min_chunks_positive:
        why.append("positive in only %d of %d time chunks" % (s["chunks_positive"], s["chunks_used"]))
    return ("UNPROVEN", why) if why else ("ENABLE", ["passed all statistical gates"])


class StrategyBook:
    def __init__(self, cells, cfg=IntelCfg(), meta=None):
        self.cells, self.cfg, self.meta = cells, cfg, meta or {}

    @classmethod
    def build(cls, trades, cfg=IntelCfg(), now=None):
        cells, dropped, n = build_cells(trades, cfg)
        meta = {"created_at": int(now if now is not None else time.time()), "n_trades": n, "dropped": dropped, "n_cells": len(cells)}
        return cls(cells, cfg, meta)

    # ---- queries -------------------------------------------------------------------------------------------------
    def verdict(self, strategy, regime):
        return self.cells.get(cell_key(strategy, regime), {}).get("verdict", "UNPROVEN")      # never seen = unproven

    def risk_multiplier(self, strategy, regime):
        """Always in [0, 1]: this layer can only restrict risk, never raise it."""
        v = self.verdict(strategy, regime)
        if v == "ENABLE":
            return 1.0
        if v == "UNPROVEN" and self.cfg.mode == "probation":
            return float(min(max(self.cfg.unproven_risk_mult, 0.0), 1.0))
        return 0.0

    def allowed(self, strategy, regime):
        return self.risk_multiplier(strategy, regime) > 0

    def shrunk_expectancy(self, strategy, regime):
        """Empirical-Bayes estimate: the cell mean pulled toward the strategy's pooled mean (more strongly when n is small)."""
        c = self.cells.get(cell_key(strategy, regime))
        if not c or c["mean_R"] is None:
            return None
        pool = [x for x in self.cells.values() if x["strategy"] == strategy and x["mean_R"] is not None]
        tot = sum(x["n"] for x in pool)
        prior = sum(x["mean_R"] * x["n"] for x in pool) / tot if tot else 0.0
        return (c["n"] * c["mean_R"] + self.cfg.shrink_k * prior) / (c["n"] + self.cfg.shrink_k)

    def rank(self, regime):
        out = [(self.shrunk_expectancy(c["strategy"], regime), c["strategy"]) for c in self.cells.values()
               if c["regime"] == regime and self.allowed(c["strategy"], regime)]
        return [s for _, s in sorted(out, key=lambda x: (-x[0], x[1]))]

    def decide(self, regime, candidates):
        """candidates: [{"strategy", "score", ...}] already produced by the Legacy signal logic. Returns
        {"trade": bool, "chosen": cand|None, "risk_multiplier": float, "reason": str}. No allowed candidate => do not trade."""
        ok = [c for c in candidates if c.get("strategy") and self.allowed(c["strategy"], regime)]
        if not ok:
            names = ", ".join(sorted({"%s=%s" % (c.get("strategy"), self.verdict(c.get("strategy"), regime)) for c in candidates})) or "no candidates"
            return {"trade": False, "chosen": None, "risk_multiplier": 0.0, "reason": "NO_TRADE in %s: nothing proven (%s)" % (regime, names)}
        best = max(ok, key=lambda c: (self.shrunk_expectancy(c["strategy"], regime) or 0.0, c.get("score", 0)))
        m = self.risk_multiplier(best["strategy"], regime)
        return {"trade": True, "chosen": best, "risk_multiplier": m,
                "reason": "%s/%s %s (shrunk expectancy %.3f R)" % (regime, best["strategy"], self.verdict(best["strategy"], regime),
                                                                    self.shrunk_expectancy(best["strategy"], regime) or 0.0)}

    def summary(self):
        by = {}
        for c in self.cells.values():
            by.setdefault(c["verdict"], []).append(cell_key(c["strategy"], c["regime"]))
        return {k: sorted(v) for k, v in by.items()}

    # ---- persistence (fail-closed) ----------------------------------------------------------------------------------
    def to_dict(self):
        return {"meta": self.meta, "cfg": asdict(self.cfg), "cells": self.cells}

    @classmethod
    def from_dict(cls, d):
        return cls(d["cells"], IntelCfg(**d["cfg"]), d.get("meta"))


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return float(o) if math.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def save_book(path, book):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_clean(book.to_dict()), fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_book(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return StrategyBook.from_dict(json.load(fh))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def decide_active(book, flag_on, max_age_days=14, min_trades=100, now=None):
    """(active, reason). Fail-closed: any doubt -> the book is NOT used and the Legacy behaviour stays exactly as it is."""
    now = now if now is not None else time.time()
    if not flag_on:
        return False, "feature flag off"
    if book is None:
        return False, "no book on file"
    if book.meta.get("n_trades", 0) < min_trades:
        return False, "evidence too thin (%d trades < %d)" % (book.meta.get("n_trades", 0), min_trades)
    if now - book.meta.get("created_at", 0) > max_age_days * 86400:
        return False, "book older than %d days" % max_age_days
    return True, "book valid"
