"""Stop management shared by the live paper trader and the backtester."""
import config

def next_stop(side, entry, initial_stop, stop, price, trailing=None):
    if trailing is None:
        trailing = config.TRAILING_ENABLED
    if not trailing:
        return stop
        
    initial = initial_stop or stop
    r = abs(entry - initial)
    if r <= 0:
        return stop
        
    sign = 1 if side == "LONG" else -1
    gain_r = (price - entry) * sign / r
    new = stop
    
    # 1. Break-even
    if gain_r >= config.BREAKEVEN_AT_R:
        be = entry * (1 + sign * (2 * config.FEE_RATE + config.SLIPPAGE_BPS / 10000))
        new = max(new, be) if sign == 1 else min(new, be)
        
    # 2. Chandelier Exit (الوقف المتدلي)
    if gain_r >= config.TRAIL_START_R:
        dynamic_multiplier = 3.0
        trail = price - sign * r * dynamic_multiplier
        new = max(new, trail) if sign == 1 else min(new, trail)
        
    return new
