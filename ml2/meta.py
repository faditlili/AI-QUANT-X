"""Meta-labeling model: given a primary signal (side), predict P(trade is profitable after costs).

Engines are comparable through the same interface: "hgb" (scikit-learn, always available), "lightgbm", "xgboost"
(optional, imported lazily). Probabilities are Platt-calibrated on a chronologically LATER slice than the fit slice.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression


class EngineUnavailable(ImportError):
    pass


def available_engines():
    out = ["hgb"]
    for name, mod in (("lightgbm", "lightgbm"), ("xgboost", "xgboost")):
        try:
            __import__(mod)
            out.append(name)
        except Exception:
            pass
    return out


def make_engine(name, seed=0):
    if name == "hgb":
        from sklearn.ensemble import HistGradientBoostingClassifier
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=120, l2_regularization=1.0,
                                              min_samples_leaf=40, random_state=seed)
    try:
        if name == "lightgbm":
            from lightgbm import LGBMClassifier
            return LGBMClassifier(n_estimators=120, learning_rate=0.05, max_depth=3, num_leaves=7, min_child_samples=40,
                                  reg_lambda=1.0, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                  random_state=seed, verbose=-1)
        if name == "xgboost":
            from xgboost import XGBClassifier
            return XGBClassifier(n_estimators=120, learning_rate=0.05, max_depth=3, min_child_weight=5, reg_lambda=1.0,
                                 subsample=0.8, colsample_bytree=0.8, random_state=seed, eval_metric="logloss")
    except ImportError as exc:
        raise EngineUnavailable("engine %r needs its package installed: %s" % (name, exc))
    raise ValueError("unknown engine %r" % (name,))


class Platt:
    """Logistic recalibration of raw probabilities."""
    def fit(self, p, y):
        y = np.asarray(y)
        if len(set(y.tolist())) < 2:
            raise ValueError("calibration slice needs both classes")
        self._lr = LogisticRegression(C=1.0).fit(self._z(p), y)
        return self

    @staticmethod
    def _z(p):
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def transform(self, p):
        return self._lr.predict_proba(self._z(p))[:, 1]


def brier(p, y):
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2))
