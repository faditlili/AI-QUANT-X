"""Machine-learning filter.

The model predicts whether price will be higher HORIZON candles from now, using only
scale-free features (ratios, oscillators), so one model can be applied to any symbol.
It is trained on several symbols and validated on a held-out, later time window.
If the held-out accuracy does not beat the naive baseline, the model is marked invalid
and get_ml_probability() returns None, which means "no opinion": the filter stays out
of the way instead of blocking trades with noise.
"""
import logging
import os
import time

import config

log = logging.getLogger(__name__)

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import GradientBoostingClassifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

FEATURES = (
    "rsi", "adx", "di_diff", "volume_ratio", "zscore", "bb_width", "bb_width_pctile",
    "atr_pctile", "taker_buy_ratio", "ema_fast_gap", "ema_slow_gap", "price_ema50_gap",
    "price_vwap_gap", "atr_pct", "channel_pos",
)
_REQUIRED = ("close", "rsi", "adx", "plus_di", "minus_di", "volume_ratio", "zscore", "bb_width",
             "bb_width_pctile", "atr_pctile", "taker_buy_ratio", "ema9", "ema21", "ema50",
             "vwap24", "atr", "swing_high", "swing_low")
MIN_TRAIN_ROWS = 300
TEST_FRACTION = 0.2
_cache = {"mtime": None, "bundle": None}
_path_cache = {"path": None}


def _model_path():
    if _path_cache["path"]:
        return _path_cache["path"]
    path = config.ML_MODEL_PATH
    try:
        folder = os.path.dirname(path) or "."
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".ml_write_test")
        with open(probe, "w") as handle:
            handle.write("ok")
        os.remove(probe)
    except OSError:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl")
    _path_cache["path"] = path
    return path


def feature_frame(df):
    """Scale-free features from an indicator frame (output of indicators.compute_frame)."""
    close = df["close"]
    rng = (df["swing_high"] - df["swing_low"]).where(lambda s: s > 0)
    out = pd.DataFrame(index=df.index)
    out["rsi"] = df["rsi"]
    out["adx"] = df["adx"]
    out["di_diff"] = df["plus_di"] - df["minus_di"]
    out["volume_ratio"] = df["volume_ratio"].clip(0, 10)
    out["zscore"] = df["zscore"].clip(-5, 5)
    out["bb_width"] = df["bb_width"]
    out["bb_width_pctile"] = df["bb_width_pctile"]
    out["atr_pctile"] = df["atr_pctile"]
    out["taker_buy_ratio"] = df["taker_buy_ratio"]
    out["ema_fast_gap"] = df["ema9"] / df["ema21"] - 1.0
    out["ema_slow_gap"] = df["ema21"] / df["ema50"] - 1.0
    out["price_ema50_gap"] = close / df["ema50"] - 1.0
    out["price_vwap_gap"] = close / df["vwap24"] - 1.0
    out["atr_pct"] = df["atr"] / close
    out["channel_pos"] = ((close - df["swing_low"]) / rng).clip(-1, 2).fillna(0.5)
    return out.replace([np.inf, -np.inf], np.nan)


def _frame_from_snapshot(snap):
    row = {}
    for key in _REQUIRED:
        if key == "close":
            row[key] = snap.get("price", snap.get("close"))
        else:
            row[key] = snap.get(key)
    return pd.DataFrame([row]).astype(float)


def _build_model():
    return GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.05,
                                      subsample=0.8, random_state=42)


def train_model(frames):
    """Train on one indicator frame or a list of them. Returns a summary dict, or None on failure."""
    if not ML_AVAILABLE:
        log.warning("[ML] scikit-learn / joblib not installed")
        return None
    try:
        if isinstance(frames, pd.DataFrame):
            frames = [frames]
        horizon = max(1, int(config.ML_HORIZON_CANDLES))
        train_parts, test_parts = [], []
        for frame in frames:
            if frame is None or any(col not in frame.columns for col in _REQUIRED):
                continue
            feats = feature_frame(frame)
            fwd = frame["close"].shift(-horizon) / frame["close"] - 1.0
            data = feats.copy()
            data["y"] = (fwd > 0).astype(int)
            data = data[fwd.notna()].dropna()
            if len(data) < MIN_TRAIN_ROWS:
                continue
            cut = int(len(data) * (1.0 - TEST_FRACTION))
            train_parts.append(data.iloc[:max(0, cut - horizon)])  # embargo: no label overlap
            test_parts.append(data.iloc[cut:])
        if not train_parts:
            log.warning("[ML] not enough data to train")
            return None
        train = pd.concat(train_parts)
        test = pd.concat(test_parts)
        if train["y"].nunique() < 2 or test.empty:
            log.warning("[ML] target has a single class")
            return None

        check = _build_model()
        check.fit(train[list(FEATURES)], train["y"])
        accuracy = float(check.score(test[list(FEATURES)], test["y"]))
        up_rate = float(test["y"].mean())
        baseline = max(up_rate, 1.0 - up_rate)
        n_test = int(len(test))
        # The edge over the naive baseline must be statistically meaningful (one-sided z >= 1.64, ~95%),
        # not just +1 percentage point that a few hundred noisy rows can produce by luck.
        sigma = (baseline * (1.0 - baseline) / n_test) ** 0.5 if n_test else 1.0
        z = (accuracy - baseline) / sigma if sigma > 0 else 0.0
        valid = accuracy >= config.ML_MIN_ACCURACY and accuracy >= baseline + 0.01 and z >= 1.64

        full = pd.concat([train, test])
        model = _build_model()
        model.fit(full[list(FEATURES)], full["y"])
        bundle = {"model": model, "features": list(FEATURES), "valid": bool(valid),
                  "accuracy": accuracy, "baseline": baseline, "rows": int(len(full)),
                  "test_rows": n_test, "z_score": float(z), "trained_at": time.time()}
        joblib.dump(bundle, _model_path())
        _cache["mtime"] = None
        _cache["bundle"] = None
        log.info("[ML] trained on %d rows | holdout accuracy %.3f | baseline %.3f | z %.2f | %s",
                 len(full), accuracy, baseline, z, "ACTIVE" if valid else "INACTIVE (no proven edge)")
        return {"valid": bool(valid), "accuracy": accuracy, "baseline": baseline, "rows": int(len(full)), "z_score": float(z)}
    except Exception as error:
        log.exception("[ML] training failed: %s", error)
        return None


def _load_bundle():
    path = _model_path()
    if not ML_AVAILABLE or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if _cache["bundle"] is not None and _cache["mtime"] == mtime:
            return _cache["bundle"]
        bundle = joblib.load(path)
        _cache["mtime"] = mtime
        _cache["bundle"] = bundle
        return bundle
    except Exception as exc:
        log.warning("[ML] could not load model: %s", exc)
        return None


def model_age_seconds():
    """Age of the saved model in seconds, or None if there is no model file."""
    path = _model_path()
    try:
        return max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        return None


def get_ml_probability(current_indicators):
    """Probability (0..1) that price is higher in HORIZON candles.

    Returns None (no opinion) when there is no model, the model has no proven edge,
    or anything goes wrong. Callers must treat None as "do not filter".
    """
    try:
        bundle = _load_bundle()
        if bundle is None or not bundle.get("valid") or not isinstance(current_indicators, dict):
            return None
        frame = _frame_from_snapshot(current_indicators)
        feats = feature_frame(frame)[bundle["features"]]
        if feats.isna().any(axis=None):
            return None
        model = bundle["model"]
        classes = list(model.classes_)
        if 1 not in classes:
            return None
        probability = float(model.predict_proba(feats)[0][classes.index(1)])
        return min(1.0, max(0.0, probability))
    except Exception as exc:
        log.debug("[ML] prediction unavailable: %s", exc)
        return None
