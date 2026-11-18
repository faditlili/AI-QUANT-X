"""Triple-barrier labelling with conservative execution assumptions (numpy only, no look-ahead).

Event at signal bar t (decided at the CLOSE of bar t). Entry = OPEN of bar t+1.
Barriers in ATR(t) units: stop = sl_atr, target = tp_atr, vertical = `horizon` bars after t.
R unit = stop distance, so a stop-out is about -1R, a target is +tp_atr/sl_atr R, minus costs.
Conservative rules:
  * both barriers inside one bar        -> STOP is assumed to hit first;
  * bar opens beyond a barrier (gap)    -> filled at the OPEN (a gap through the stop loses MORE than 1R);
  * events whose full horizon is not available in the data are DROPPED (no partial/censored labels);
  * costs: round-trip `cost_pct` (fees+slippage, fraction of entry) is subtracted in R terms.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LabelCfg:
    tp_atr: float = 2.0
    sl_atr: float = 1.0
    horizon: int = 24
    cost_pct: float = 0.0012      # round trip, fraction of entry price (explicit assumption, not measured)


def label_events(open_, high, low, close, atr, sides, cfg=LabelCfg()):
    """Return dict of aligned arrays: t0, exit_idx, side, R, reason (0=stop,1=target,2=timeout)."""
    o, h, l, c = (np.asarray(x, dtype=float) for x in (open_, high, low, close))
    atr, sides = np.asarray(atr, dtype=float), np.asarray(sides)
    n = len(c)
    if not (len(h) == len(l) == len(o) == len(atr) == len(sides) == n):
        raise ValueError("all inputs must have the same length")
    t0s, exits, sd, rs, why = [], [], [], [], []
    for t in np.flatnonzero(sides != 0):
        a = atr[t]
        if t + cfg.horizon > n - 1 or not np.isfinite(a) or a <= 0:
            continue                                   # horizon not fully observable / no valid ATR
        s = int(np.sign(sides[t]))
        entry = o[t + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        sl_d, tp_d = cfg.sl_atr * a, cfg.tp_atr * a
        sl, tp = entry - s * sl_d, entry + s * tp_d
        exit_px, exit_idx, reason = c[t + cfg.horizon], t + cfg.horizon, 2
        for j in range(t + 1, t + cfg.horizon + 1):
            if j > t + 1:                              # gap handling (bar j-1 -> j)
                if (s == 1 and o[j] <= sl) or (s == -1 and o[j] >= sl):
                    exit_px, exit_idx, reason = o[j], j, 0
                    break
                if (s == 1 and o[j] >= tp) or (s == -1 and o[j] <= tp):
                    exit_px, exit_idx, reason = o[j], j, 1
                    break
            if (s == 1 and l[j] <= sl) or (s == -1 and h[j] >= sl):
                exit_px, exit_idx, reason = sl, j, 0   # stop first when both are inside the bar
                break
            if (s == 1 and h[j] >= tp) or (s == -1 and l[j] <= tp):
                exit_px, exit_idx, reason = tp, j, 1
                break
        r = s * (exit_px - entry) / sl_d - cfg.cost_pct * entry / sl_d
        t0s.append(t); exits.append(exit_idx); sd.append(s); rs.append(r); why.append(reason)
    return {"t0": np.array(t0s, dtype=int), "exit_idx": np.array(exits, dtype=int), "side": np.array(sd, dtype=int),
            "R": np.array(rs, dtype=float), "reason": np.array(why, dtype=int)}
