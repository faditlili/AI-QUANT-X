"""Out-of-sample evidence gate. A model may only be used if it beats the accept-every-signal baseline.

Procedure (per purged walk-forward fold, no test data ever used for fitting / calibration / threshold choice):
  train -> [fit slice | later calibration slice (purged from fit)];  fit engine, Platt-calibrate on calibration slice,
  pick the probability threshold on the calibration slice only, then apply to the untouched test block.
Pooled out-of-sample results are compared with the BASELINE (take every primary signal) in net R after costs.
PASS needs ALL of:
  1. enough selected trades (min_selected);
  2. mean R of selected trades > 0 (profitable after costs);
  3. improvement over baseline: 5th percentile of a block-bootstrap of (mean R selected - mean R all) > 0;
  4. selected beats baseline in at least `min_fold_win` of the folds that selected >= 10 trades;
  5. calibrated Brier score better than the constant base-rate predictor.
Block bootstrap is used because consecutive trades overlap in time (positive serial dependence).
"""
import json
import os
import time

import numpy as np

from . import meta
from .features import EVENT_FEATURES
from .validation import purge, purged_walk_forward

# Must span the break-even win probability (~ (1+cost)/(1+tp/sl) = 0.34 for 2:1 barriers), not just high-confidence levels.
THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)


def block_bootstrap_improvement(R, sel, n_boot=2000, block=10, seed=0):
    """Distribution of mean(R[sel]) - mean(R) over block-resampled trade sequences."""
    R, sel = np.asarray(R, dtype=float), np.asarray(sel, dtype=bool)
    n = len(R)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    out = []
    for _ in range(n_boot):
        starts = rng.integers(0, n, size=nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        idx = idx[:n]
        s = sel[idx]
        if s.sum() >= 5:
            out.append(R[idx][s].mean() - R[idx].mean())
    return np.array(out)


def _choose_threshold(p_cal, R_cal, min_n=20):
    best, best_val = None, -np.inf
    for thr in THRESHOLDS:
        m = p_cal >= thr
        if m.sum() >= min_n:
            val = R_cal[m].mean()
            if val >= best_val:
                best, best_val = thr, val
    return best


def judge(stats, min_selected=100, min_fold_win=0.6):
    """Pure verdict logic: returns the list of FAILED conditions (empty list = pass). Each condition is independent."""
    reasons = []
    if stats["n_selected"] < min_selected:
        reasons.append("only %d selected trades (< %d)" % (stats["n_selected"], min_selected))
    if stats["mean_R_selected"] is None or stats["mean_R_selected"] <= 0:
        reasons.append("selected trades are not profitable after costs")
    if stats["improvement_ci_low"] is None or stats["improvement_ci_low"] <= 0:
        reasons.append("improvement over accept-all baseline not statistically significant")
    if stats["fold_win_rate"] is None or stats["fold_win_rate"] < min_fold_win:
        reasons.append("does not beat baseline consistently across folds")
    if stats["brier_model"] >= stats["brier_baseline"]:
        reasons.append("probabilities are no better than the constant base rate")
    return reasons


def evaluate_meta(events, engine="hgb", n_splits=5, min_selected=100, min_fold_win=0.6, alpha=0.05,
                  n_boot=2000, seed=0, features=EVENT_FEATURES, engine_factory=None):
    """events: DataFrame from ml2.features.build_events (sorted by t0). Returns a JSON-serialisable verdict."""
    ev = events.sort_values("t0").reset_index(drop=True)
    X, y, R = ev[list(features)].to_numpy(float), ev["y"].to_numpy(int), ev["R"].to_numpy(float)
    t0, ex = ev["t0"].to_numpy(), ev["exit_idx"].to_numpy()
    factory = engine_factory or (lambda: meta.make_engine(engine, seed))
    folds_out, pool_R, pool_sel, pool_p, pool_y, pool_const = [], [], [], [], [], []
    for k, fold in enumerate(purged_walk_forward(t0, ex, n_splits)):
        tr, te = fold["train"], fold["test"]
        ncal = max(int(0.25 * len(tr)), 1)
        cal, fit = tr[-ncal:], purge(tr[:-ncal], ex, t0[tr[-ncal]])      # fit events must resolve before calibration starts
        info = {"fold": k, "n_fit": int(len(fit)), "n_cal": int(len(cal)), "n_test": int(len(te)), "skipped": None,
                # audit trail: every label used for fitting resolved before calibration began, and every label used
                # for calibration resolved before the test block began (must hold for the verdict to be trusted)
                "fit_max_exit": int(ex[fit].max()) if len(fit) else None, "cal_min_t0": int(t0[cal].min()),
                "cal_max_exit": int(ex[cal].max()), "test_min_t0": int(t0[te].min())}
        if len(fit) < 200 or len(cal) < 60 or len(set(y[fit])) < 2 or len(set(y[cal])) < 2:
            info["skipped"] = "not enough data in fit/calibration slice"
            folds_out.append(info)
            continue
        model = factory().fit(X[fit], y[fit])
        platt = meta.Platt().fit(model.predict_proba(X[cal])[:, 1], y[cal])
        thr = _choose_threshold(platt.transform(model.predict_proba(X[cal])[:, 1]), R[cal])
        p_te = platt.transform(model.predict_proba(X[te])[:, 1])
        sel = (p_te >= thr) if thr is not None else np.zeros(len(te), dtype=bool)
        info.update(threshold=thr, n_selected=int(sel.sum()), mean_R_all=float(R[te].mean()),
                    mean_R_selected=float(R[te][sel].mean()) if sel.any() else None)
        folds_out.append(info)
        pool_R.append(R[te]); pool_sel.append(sel); pool_p.append(p_te); pool_y.append(y[te])
        pool_const.append(np.full(len(te), y[fit].mean()))
    verdict = {"engine": engine, "n_splits": n_splits, "folds": folds_out, "created_at": int(time.time()), "passed": False}
    if not pool_R:
        verdict["reasons"] = ["no usable folds"]
        return verdict
    R_all, sel_all = np.concatenate(pool_R), np.concatenate(pool_sel)
    p_all, y_all, c_all = np.concatenate(pool_p), np.concatenate(pool_y), np.concatenate(pool_const)
    boot = block_bootstrap_improvement(R_all, sel_all, n_boot=n_boot, seed=seed)
    usable = [f for f in folds_out if f.get("n_selected", 0) >= 10]
    wins = sum(1 for f in usable if f["mean_R_selected"] > f["mean_R_all"])
    stats = {"n_oos": int(len(R_all)), "n_selected": int(sel_all.sum()), "mean_R_all": float(R_all.mean()),
             "mean_R_selected": float(R_all[sel_all].mean()) if sel_all.any() else None,
             "improvement_ci_low": float(np.quantile(boot, alpha)) if len(boot) else None,
             "fold_win_rate": (wins / len(usable)) if usable else None, "n_fold_usable": len(usable),
             "brier_model": meta.brier(p_all, y_all), "brier_baseline": meta.brier(c_all, y_all)}
    reasons = judge(stats, min_selected, min_fold_win)
    verdict.update(stats=stats, reasons=reasons, passed=not reasons)
    return verdict


def save_verdict(path, verdict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_verdict(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def decide_active(verdict, flag_on, max_age_days=30, drifted=(), now=None):
    """(active, reason). Fail-closed: any doubt -> not active."""
    now = now if now is not None else time.time()
    if not flag_on:
        return False, "feature flag off"
    if not verdict:
        return False, "no verdict on file"
    if not verdict.get("passed"):
        return False, "gate not passed"
    if now - verdict.get("created_at", 0) > max_age_days * 86400:
        return False, "verdict older than %d days" % max_age_days
    if drifted:
        return False, "feature drift: %s" % ", ".join(drifted)
    return True, "gate passed"
