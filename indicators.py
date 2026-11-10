"""Dependency-light technical indicators with input validation."""
import numpy as np
import pandas as pd
import config

class IndicatorError(ValueError):
    pass

def _clean(frame):
    if isinstance(frame, pd.DataFrame):
        df = frame.copy()
    else:
        if not frame or len(frame[0]) < 5:
            raise IndicatorError("Expected OHLCV rows")
        df = pd.DataFrame(frame, columns=["open","high","low","close","volume"])
    required = ["open","high","low","close","volume"]
    if not set(required).issubset(df.columns):
        raise IndicatorError("Missing OHLCV columns")
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    df = df[(df[["open","high","low","close"]] > 0).all(axis=1) & (df["volume"] >= 0)]
    if "timestamp" in df.columns:
        df = df.drop_duplicates("timestamp").sort_values("timestamp")
    if len(df) < max(config.MIN_CANDLES_REQUIRED, config.EMA_SLOW + 5):
        raise IndicatorError("Insufficient valid candles")
    return df.reset_index(drop=True)

def calculate_indicators(frame):
    df = _clean(frame)
    close, high, low = df.close, df.high, df.low
    df["ema9"] = close.ewm(span=config.EMA_FAST, adjust=False).mean()
    df["ema21"] = close.ewm(span=config.EMA_MEDIUM, adjust=False).mean()
    df["ema50"] = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/config.RSI_PERIOD, adjust=False, min_periods=config.RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/config.RSI_PERIOD, adjust=False, min_periods=config.RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100/(1+rs)
    rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((gain == 0) & (loss > 0), 0).fillna(50)
    df["rsi"] = rsi
    prev = close.shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/config.ATR_PERIOD, adjust=False, min_periods=config.ATR_PERIOD).mean()
    up, down = high.diff(), -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1/config.ADX_PERIOD, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=1/config.ADX_PERIOD, adjust=False).mean() / atr_safe
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/config.ADX_PERIOD, adjust=False, min_periods=config.ADX_PERIOD).mean()
    vol_sma = df.volume.rolling(config.VOLUME_SMA_PERIOD).mean()
    last = len(df)-1
    result = {
        "price": float(close.iloc[last]), "close": float(close.iloc[last]),
        "ema_fast": float(df.ema9.iloc[last]), "ema_medium": float(df.ema21.iloc[last]),
        "ema_slow": float(df.ema50.iloc[last]), "ema9": float(df.ema9.iloc[last]),
        "ema21": float(df.ema21.iloc[last]), "ema50": float(df.ema50.iloc[last]),
        "rsi": float(df.rsi.iloc[last]), "atr": float(atr.iloc[last]),
        "adx": float(adx.iloc[last]) if pd.notna(adx.iloc[last]) else 0.0,
        "plus_di": float(plus_di.iloc[last]) if pd.notna(plus_di.iloc[last]) else 0.0,
        "minus_di": float(minus_di.iloc[last]) if pd.notna(minus_di.iloc[last]) else 0.0,
        "volume_sma": float(vol_sma.iloc[last]) if pd.notna(vol_sma.iloc[last]) else 0.0,
        "volume_ratio": float(df.volume.iloc[last]/vol_sma.iloc[last]) if pd.notna(vol_sma.iloc[last]) and vol_sma.iloc[last] > 0 else 0.0,
        "candles": int(len(df))
    }
    if not all(np.isfinite(v) for v in result.values()):
        raise IndicatorError("Non-finite indicator result")
    return result

def direction(ind):
    if not ind:
        return "NEUTRAL"
    if ind["ema9"] > ind["ema21"] > ind["ema50"] and ind["plus_di"] >= ind["minus_di"]:
        return "BULLISH"
    if ind["ema9"] < ind["ema21"] < ind["ema50"] and ind["minus_di"] > ind["plus_di"]:
        return "BEARISH"
    return "NEUTRAL"

def multi_timeframe_bullish(items):
    return all(items.get(tf) and direction(items[tf]) == "BULLISH" for tf in ("15m","1h","4h"))

def multi_timeframe_bearish(items):
    return all(items.get(tf) and direction(items[tf]) == "BEARISH" for tf in ("15m","1h","4h"))
