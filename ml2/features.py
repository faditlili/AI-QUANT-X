"""Causal price/volume features + event table builder. Row t uses ONLY bars <= t (tested by truncation)."""
import numpy as np
import pandas as pd

from .labeling import LabelCfg, label_events

BASE_FEATURES = ["ret_1", "ret_5", "ret_20", "atr_pct", "vol_ratio", "rsi14", "ema_dist", "vol_z", "range_pos"]
EVENT_FEATURES = BASE_FEATURES + ["side", "side_x_ret_20", "side_x_ema_dist", "side_x_rsi"]


def price_features(df):
    c, h, l, v = (df[k].astype(float) for k in ("close", "high", "low", "volume"))
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    atr_pct = atr / c
    lc = np.log(c)
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    rsi = rsi.where(dn != 0, 100.0).where(up.notna() & dn.notna())
    ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    lo20, hi20 = l.rolling(20).min(), h.rolling(20).max()
    f = pd.DataFrame({
        "ret_1": lc.diff(), "ret_5": lc.diff(5), "ret_20": lc.diff(20), "atr_pct": atr_pct,
        "vol_ratio": atr_pct / atr_pct.rolling(100, min_periods=50).mean(),
        "rsi14": rsi, "ema_dist": (c / ema50 - 1) / atr_pct,
        "vol_z": (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan),
        "range_pos": (c - lo20) / (hi20 - lo20).replace(0, np.nan)}, index=df.index)
    return f, atr


def build_events(df, sides, cfg=LabelCfg()):
    """df: columns open/high/low/close/volume. sides: array of +1/-1/0 aligned with df (primary strategy decision
    at each bar's close). Returns an event DataFrame sorted by t0 with features, R (net, after costs) and y=(R>0)."""
    feats, atr = price_features(df)
    lab = label_events(df["open"], df["high"], df["low"], df["close"], atr.to_numpy(), sides, cfg)
    ev = feats.iloc[lab["t0"]].reset_index(drop=True)
    ev["side"] = lab["side"].astype(float)
    ev["side_x_ret_20"] = ev["side"] * ev["ret_20"] / ev["atr_pct"]
    ev["side_x_ema_dist"] = ev["side"] * ev["ema_dist"]
    ev["side_x_rsi"] = ev["side"] * (ev["rsi14"] - 50) / 50
    ev["t0"], ev["exit_idx"], ev["R"], ev["reason"] = lab["t0"], lab["exit_idx"], lab["R"], lab["reason"]
    ev["y"] = (ev["R"] > 0).astype(int)
    ev = ev.replace([np.inf, -np.inf], np.nan).dropna(subset=EVENT_FEATURES).reset_index(drop=True)
    return ev
