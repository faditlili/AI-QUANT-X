"""Feature flags for the new engines. Everything defaults to OFF, so the Legacy Core behaves exactly
as before unless a flag is switched on in the environment (e.g. FF_ADVANCED_DATA=true).

Dependencies (a flag is only effective if the flags it needs are on too):
  ORDER_FLOW -> ADVANCED_DATA, ADVANCED_BACKTEST -> ADVANCED_DATA, META_LABELING -> LIGHTGBM
"""
import os

_ENV = {
    "ADVANCED_DATA": "FF_ADVANCED_DATA",
    "LIGHTGBM": "FF_LIGHTGBM",
    "META_LABELING": "FF_META_LABELING",
    "ORDER_FLOW": "FF_ORDER_FLOW",
    "MARKET_REGIME": "FF_MARKET_REGIME",
    "ADVANCED_BACKTEST": "FF_ADVANCED_BACKTEST",
}
_REQUIRES = {"ORDER_FLOW": ("ADVANCED_DATA",), "ADVANCED_BACKTEST": ("ADVANCED_DATA",),
             "META_LABELING": ("LIGHTGBM",)}


def _raw(name):
    return os.getenv(_ENV[name], "false").strip().lower() in ("1", "true", "yes", "on")


def enabled(name):
    """True only if the flag and everything it depends on are on. Unknown names raise (typo safety)."""
    if name not in _ENV:
        raise KeyError("unknown feature flag %r" % name)
    return _raw(name) and all(enabled(dep) for dep in _REQUIRES.get(name, ()))


def snapshot():
    return {name: enabled(name) for name in _ENV}
