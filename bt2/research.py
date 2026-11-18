"""Generic research harnesses. `evaluate(start, end, params) -> {"score": float, "n_trades": int, ...}` is supplied by the
caller (typically a closure running bt2.engine.simulate on bars [start, end))."""
import itertools


def grid(param_grid):
    names = list(param_grid)
    return [dict(zip(names, vals)) for vals in itertools.product(*(param_grid[n] for n in names))]


def walk_forward(evaluate, param_grid, n_bars, n_splits=4, gap=0, min_trades=10):
    """Anchored walk-forward: fold k trains on [0, (k+1)L) and is tested on [(k+1)L + gap, (k+2)L), L = n_bars // (n_splits+1).
    Parameters are chosen on TRAIN only; the test block is never used for selection. `gap` (>= max holding bars) keeps
    positions opened in training from overlapping the test block."""
    L = n_bars // (n_splits + 1)
    if L < 10 or gap >= L:
        raise ValueError("windows too small for %d splits (gap=%d)" % (n_splits, gap))
    combos, folds = grid(param_grid), []
    for k in range(n_splits):
        tr_end, te_start, te_end = (k + 1) * L, (k + 1) * L + gap, (k + 2) * L
        scored = [(evaluate(0, tr_end, p), p) for p in combos]
        scored = [(r, p) for r, p in scored if r.get("n_trades", 0) >= min_trades] or scored
        best_r, best_p = max(scored, key=lambda rp: rp[0]["score"])
        oos = evaluate(te_start, te_end, best_p)
        folds.append({"fold": k, "params": best_p, "is_score": best_r["score"], "oos_score": oos["score"],
                      "oos_trades": oos.get("n_trades", 0)})
    is_mean = sum(f["is_score"] for f in folds) / len(folds)
    oos_mean = sum(f["oos_score"] for f in folds) / len(folds)
    return {"folds": folds, "is_mean": is_mean, "oos_mean": oos_mean,
            "efficiency": (oos_mean / is_mean) if is_mean > 0 else None,
            "oos_positive_folds": sum(1 for f in folds if f["oos_score"] > 0), "n_folds": len(folds)}


def parameter_sensitivity(evaluate, base_params, sweeps, start, end, tolerance=0.5):
    """One-at-a-time sweeps around base_params. A parameter is FRAGILE if a neighbouring value (adjacent in its list)
    loses more than `tolerance` of the base score, or flips its sign. Robust results sit on a plateau, not a spike."""
    base = evaluate(start, end, base_params)["score"]
    report, fragile = {}, []
    for name, values in sweeps.items():
        scores = [evaluate(start, end, {**base_params, name: v})["score"] for v in values]
        report[name] = dict(zip(map(str, values), scores))
        if base_params[name] in values:
            i = values.index(base_params[name])
            for j in (i - 1, i + 1):
                if 0 <= j < len(values):
                    s = scores[j]
                    if base > 0 and (s < 0 or (base - s) / base > tolerance):
                        fragile.append(name)
                        break
    return {"base_score": base, "sweeps": report, "fragile": sorted(set(fragile)), "robust": not fragile}
