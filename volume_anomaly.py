# volume_anomaly.py
#
# No new line is needed in requirements.txt (numpy is already installed with pandas).

import numpy as np

LOOKBACK_CANDLES = 50
MIN_CANDLES = 20
ANOMALY_Z_THRESHOLD = 3.0
HIGH_Z_THRESHOLD = 4.0
EXTREME_Z_THRESHOLD = 5.0


def _no_anomaly():
    return {"anomaly": False, "z_score": 0.0}


def detect_volume_anomaly(df):
    """Detect abnormal volume (whale activity) on the latest candle.

    df: DataFrame with "volume", "close" and "open" columns in chronological order.
    The baseline (mean and standard deviation) uses the 50 candles BEFORE the latest
    candle, so the spike itself does not distort its own Z-Score.

    Returns:
        {"anomaly": True, "z_score": 3.5, "direction": "SELLING_WHALE", "intensity": "EXTREME"}
    or {"anomaly": False, "z_score": 0.0} when there is no unusual activity or the data is bad.
    """
    try:
        if df is None or len(df) < MIN_CANDLES + 1:
            return _no_anomaly()

        recent = df.tail(LOOKBACK_CANDLES + 1)

        volumes = np.asarray(recent["volume"], dtype=float)
        current_volume = volumes[-1]
        history = volumes[:-1]
        history = history[np.isfinite(history)]

        if len(history) < MIN_CANDLES or not np.isfinite(current_volume):
            return _no_anomaly()

        mean = float(np.mean(history))
        std = float(np.std(history))
        if std <= 0.0:
            return _no_anomaly()

        z_score = (float(current_volume) - mean) / std
        if z_score <= ANOMALY_Z_THRESHOLD:
            return _no_anomaly()

        current_open = float(recent["open"].iloc[-1])
        current_close = float(recent["close"].iloc[-1])

        if current_close > current_open:
            direction = "BUYING_WHALE"
        elif current_close < current_open:
            direction = "SELLING_WHALE"
        else:
            direction = "NEUTRAL"

        if z_score >= EXTREME_Z_THRESHOLD:
            intensity = "EXTREME"
        elif z_score >= HIGH_Z_THRESHOLD:
            intensity = "HIGH"
        else:
            intensity = "MODERATE"

        return {
            "anomaly": True,
            "z_score": round(z_score, 2),
            "direction": direction,
            "intensity": intensity,
        }
    except Exception:
        return _no_anomaly()
