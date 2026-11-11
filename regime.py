"""Market regime classification used to choose which strategy may trade."""
import config
from indicators import direction

def detect_regime(ind):
    """Return one of HIGH_VOL, TREND, SQUEEZE, RANGE, TRANSITION."""
    if ind["atr_pctile"] >= config.HIGH_VOL_PERCENTILE:
        return "HIGH_VOL"
    if direction(ind) != "NEUTRAL" and ind["adx"] >= config.TREND_ADX_MIN:
        return "TREND"
    if ind["squeeze"] and ind["adx"] < config.TREND_ADX_MIN:
        return "SQUEEZE"
    if ind["adx"] < config.RANGE_ADX_MAX:
        return "RANGE"
    return "TRANSITION"
