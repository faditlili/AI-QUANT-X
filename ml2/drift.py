"""Feature drift via Population Stability Index (bins fixed from the TRAINING distribution)."""
import numpy as np


def psi(train, live, bins=10, eps=1e-4):
    train, live = np.asarray(train, dtype=float), np.asarray(live, dtype=float)
    train, live = train[np.isfinite(train)], live[np.isfinite(live)]
    if len(train) < bins * 5 or len(live) < bins * 2:
        raise ValueError("not enough observations for PSI")
    edges = np.unique(np.quantile(train, np.linspace(0, 1, bins + 1)[1:-1]))
    a = np.bincount(np.searchsorted(edges, train, side="right"), minlength=len(edges) + 1) / len(train)
    b = np.bincount(np.searchsorted(edges, live, side="right"), minlength=len(edges) + 1) / len(live)
    a, b = np.clip(a, eps, None), np.clip(b, eps, None)
    return float(np.sum((b - a) * np.log(b / a)))


def drift_report(train_df, live_df, columns, threshold=0.25):
    """PSI per column; rule of thumb: <0.1 stable, 0.1-0.25 moderate, >0.25 significant shift."""
    scores = {c: psi(train_df[c], live_df[c]) for c in columns}
    return {"psi": scores, "drifted": sorted(c for c, v in scores.items() if v > threshold), "threshold": threshold}
