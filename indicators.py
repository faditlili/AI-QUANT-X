"""Technical indicators (vectorised) with input validation."""
import threading
import numpy as np
import pandas as pd
import config

class IndicatorError(ValueError):
    pass

# Thread-local parameter override. Used by the Auto-Tune worker thread so the live
# engine (another thread / the event loop) never sees experimental values.
_override = threading.local()

class param_override:
    def __init__(self, rsi=None, ema_fast=None):
        self.rsi = rsi
        self.ema_fast = ema_fast
        self._prev = None

    def __enter__(self):
        self._prev = (getattr(_override, "rsi", None), getattr(_override, "ema_fast", None))
        _override.rsi = self.rsi
        _override.ema_fast = self.ema_fast
        return self

    def __exit__(self, exc_type, exc, tb):
        _override.rsi, _override.ema_fast = self._prev
        return False

def _rsi_period():
    v = getattr(_override, "rsi", None)
    return config.RSI_PERIOD if v is None else int(v)

def _ema_fast():
    v = getattr(_override, "ema_fast", None)
    return config.EMA_FAST if v is None else int(v)

def _clean(frame, strict=False):
    """Validate and normalise OHLCV. strict=True (live path) refuses frames with invalid rows or
    missing candles instead of silently repairing them: a gap would shift every indicator."""
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
    before = len(df)
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    df = df[(df[["open","high","low","close"]] > 0).all(axis=1) & (df["volume"] >= 0)
            & (df["high"] >= df["low"]) & (df["high"] >= df[["open","close"]].max(axis=1))
            & (df["low"] <= df[["open","close"]].min(axis=1))]
    if strict and len(df) != before:
        raise IndicatorError("Invalid candle(s) in the data")
    if "timestamp" in df.columns:
        df = df.drop_duplicates("timestamp").sort_values("timestamp")
        if strict and len(df) > 3:
            gaps = df["timestamp"].diff().tail(100).dropna()
            step = gaps.median()
            if step > 0 and (gaps > step * 1.5).any():
                raise IndicatorError("Missing candles in the data")
    if len(df) < max(config.MIN_CANDLES_REQUIRED, config.EMA_SLOW + 5):
        raise IndicatorError("Insufficient valid candles")
    return df.reset_index(drop=True)

def _pctile_of_last(window):
    return float((window <= window[-1]).mean() * 100)

def compute_frame(frame, strict=False):
    df = _clean(frame, strict)
    close, high, low = df.close, df.high, df.low
    
    rsi_period = _rsi_period()
    df["ema9"] = close.ewm(span=_ema_fast(), adjust=False).mean()
    df["ema21"] = close.ewm(span=config.EMA_MEDIUM, adjust=False).mean()
    df["ema50"] = close.ewm(span=config.EMA_SLOW, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/rsi_period, adjust=False, min_periods=rsi_period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/rsi_period, adjust=False, min_periods=rsi_period).mean()
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
    df["atr"] = atr
    df["adx"] = adx.fillna(0.0)
    df["plus_di"] = plus_di.fillna(0.0)
    df["minus_di"] = minus_di.fillna(0.0)

    vol_sma = df.volume.rolling(config.VOLUME_SMA_PERIOD).mean()
    df["volume_sma"] = vol_sma.fillna(0.0)
    df["volume_ratio"] = (df.volume / vol_sma.where(vol_sma > 0)).fillna(0.0)

    mid = close.rolling(20).mean()
    sd = close.rolling(20).std(ddof=0)
    df["bb_mid"] = mid
    df["bb_upper"] = mid + 2*sd
    df["bb_lower"] = mid - 2*sd
    df["zscore"] = ((close - mid) / sd.where(sd > 0)).fillna(0.0)
    width = (df.bb_upper - df.bb_lower) / mid
    df["bb_width"] = width
    df["bb_width_pctile"] = width.rolling(100, min_periods=30).apply(_pctile_of_last, raw=True).fillna(50.0)

    df["donchian_high"] = high.rolling(20).max().shift(1).fillna(high)
    df["donchian_low"] = low.rolling(20).min().shift(1).fillna(low)
    df["squeeze"] = (df.bb_width_pctile.rolling(10, min_periods=1).min() <= 25).astype(int)

    atr_pct = atr / close
    df["atr_pctile"] = atr_pct.rolling(100, min_periods=30).apply(_pctile_of_last, raw=True).fillna(50.0)

    # VWAP
    typical_price = (high + low + close) / 3
    df["vwap"] = (typical_price * df.volume).cumsum() / df.volume.cumsum()
    # VWAP متحرك لآخر 24 شمعة: يستجيب أسرع من VWAP الذي يمتد على كل النافذة
    vol24 = df.volume.rolling(24, min_periods=1).sum().replace(0, np.nan)
    df["vwap24"] = ((typical_price * df.volume).rolling(24, min_periods=1).sum() / vol24).fillna(close)

    # Order Flow (Taker Buy Ratio)
    df["taker_buy_ratio"] = (df.get("taker_buy_volume", df.volume * 0.5) / df.volume.replace(0, 1)).fillna(0.5)

    # Market Structure (Swing Highs / Lows)
    df["swing_high"] = high.rolling(10).max().shift(1).fillna(high)
    df["swing_low"] = low.rolling(10).min().shift(1).fillna(low)

    return df

_KEYS = ("ema9","ema21","ema50","rsi","atr","adx","plus_di","minus_di","volume_sma","volume_ratio",
         "bb_mid","bb_upper","bb_lower","zscore","bb_width","bb_width_pctile",
         "donchian_high","donchian_low","atr_pctile", "vwap", "vwap24", "taker_buy_ratio", "swing_high", "swing_low")

def snapshot(df, i=-1):
    r = df.iloc[i]
    out = {k: float(r[k]) for k in _KEYS if k in r}
    price = float(r["close"])
    out.update({
        "price": price, "close": price,
        "ema_fast": out["ema9"], "ema_medium": out["ema21"], "ema_slow": out["ema50"],
        "squeeze": bool(r["squeeze"]),
        "candles": int(len(df) if i == -1 else (i % len(df)) + 1),
        "vwap": out.get("vwap", price),
        "vwap24": out.get("vwap24", price)
    })
    return out

def calculate_indicators(frame):
    df = compute_frame(frame, strict=True)
    result = snapshot(df)
    if not all(np.isfinite(v) for v in result.values() if isinstance(v, (int, float))):
        raise IndicatorError("Non-finite indicator result")
    return result

def direction(ind):
    if not ind: return "NEUTRAL"
    if ind["ema9"] > ind["ema21"] > ind["ema50"] and ind["plus_di"] >= ind["minus_di"]:
        return "BULLISH"
    if ind["ema9"] < ind["ema21"] < ind["ema50"] and ind["minus_di"] > ind["plus_di"]:
        return "BEARISH"
    return "NEUTRAL"

def multi_timeframe_bullish(items):
    return all(items.get(tf) and direction(items[tf]) == "BULLISH" for tf in ("15m","1h","4h"))

def multi_timeframe_bearish(items):
    return all(items.get(tf) and direction(items[tf]) == "BEARISH" for tf in ("15m","1h","4h"))
