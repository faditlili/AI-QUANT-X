# ml_filter.py
#
# Add these lines to requirements.txt (pandas and numpy are usually already there):
#     scikit-learn
#     joblib
#
# Note for Railway: the local file system is wiped on every redeploy, so model.pkl
# is lost after a redeploy. Call train_model(df) again after each deploy.

import os

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import GradientBoostingClassifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl")
NEUTRAL_PROBABILITY = 0.5
MIN_TRAIN_ROWS = 100
TEST_FRACTION = 0.2

# Raw price/time columns are not used as features (they are not stationary).
EXCLUDED_COLUMNS = {
    "open", "high", "low", "close", "volume",
    "timestamp", "time", "open_time", "close_time", "date", "datetime",
    "target",
}

_cache = {"mtime": None, "bundle": None}


def _build_model():
    return GradientBoostingClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )


def train_model(df):
    """Train a model to predict the next candle (1 = up, 0 = down) and save it to model.pkl.

    df: DataFrame with OHLCV columns ("close" is required) plus indicator columns
    (RSI, EMA, ATR, ...). Rows must be in chronological order.
    Returns True if the model was trained and saved, otherwise False.
    """
    if not ML_AVAILABLE:
        print("[ML] scikit-learn / joblib not installed")
        return False

    try:
        if df is None or "close" not in df.columns:
            print("[ML] DataFrame is missing the close column")
            return False

        data = df.copy()
        data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)
        data = data.iloc[:-1]  # the last row has no next candle

        feature_columns = [
            col for col in data.columns
            if col not in EXCLUDED_COLUMNS and pd.api.types.is_numeric_dtype(data[col])
        ]
        if not feature_columns:
            print("[ML] no indicator columns found to use as features")
            return False

        data = data[feature_columns + ["target"]]
        data = data.replace([np.inf, -np.inf], np.nan).dropna()

        if len(data) < MIN_TRAIN_ROWS:
            print("[ML] not enough rows to train: " + str(len(data)))
            return False
        if data["target"].nunique() < 2:
            print("[ML] target has only one class, cannot train")
            return False

        x = data[feature_columns]
        y = data["target"]

        # Time-ordered split (no shuffling) to get an honest accuracy estimate.
        split_index = int(len(data) * (1.0 - TEST_FRACTION))
        x_train, x_test = x.iloc[:split_index], x.iloc[split_index:]
        y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

        if y_train.nunique() >= 2 and len(x_test) > 0:
            check_model = _build_model()
            check_model.fit(x_train, y_train)
            accuracy = check_model.score(x_test, y_test)
            print("[ML] out-of-sample accuracy: " + str(round(accuracy, 4)))

        # Final model is trained on all available data.
        model = _build_model()
        model.fit(x, y)

        joblib.dump({"model": model, "features": feature_columns}, MODEL_PATH)
        _cache["mtime"] = None
        _cache["bundle"] = None
        print("[ML] model saved to " + MODEL_PATH)
        return True
    except Exception as error:
        print("[ML] training failed: " + str(error))
        return False


def _load_bundle():
    """Load the saved model (cached until the file changes). Returns None if unavailable."""
    if not ML_AVAILABLE or not os.path.exists(MODEL_PATH):
        return None
    try:
        mtime = os.path.getmtime(MODEL_PATH)
        if _cache["bundle"] is not None and _cache["mtime"] == mtime:
            return _cache["bundle"]
        bundle = joblib.load(MODEL_PATH)
        _cache["mtime"] = mtime
        _cache["bundle"] = bundle
        return bundle
    except Exception:
        return None


def get_ml_probability(current_indicators):
    """Return the probability (0 to 1) that the next candle is up.

    current_indicators: dict of the current indicator values.
    Returns 0.5 (neutral) if no trained model exists or anything goes wrong.
    """
    try:
        bundle = _load_bundle()
        if bundle is None or not isinstance(current_indicators, dict):
            return NEUTRAL_PROBABILITY

        model = bundle["model"]
        features = bundle["features"]

        row = {}
        for name in features:
            value = current_indicators.get(name, 0.0)
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = 0.0
            if value != value or value in (float("inf"), float("-inf")):
                value = 0.0
            row[name] = value

        frame = pd.DataFrame([row], columns=features)
        probabilities = model.predict_proba(frame)[0]

        classes = list(model.classes_)
        if 1 not in classes:
            return NEUTRAL_PROBABILITY
        probability_up = float(probabilities[classes.index(1)])

        return min(1.0, max(0.0, probability_up))
    except Exception:
        return NEUTRAL_PROBABILITY
