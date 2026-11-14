"""Stop management shared by the live paper trader and the backtester."""
import config

def next_stop(side, entry, initial_stop, stop, price, trailing=None, fee=None):
    if trailing is None:
        trailing = config.TRAILING_ENABLED
    if fee is None:
        fee = config.FEE_RATE
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
        be = entry * (1 + sign * (2 * fee + config.SLIPPAGE_BPS / 10000))
        new = max(new, be) if sign == 1 else min(new, be)
        
    # 2. Chandelier Exit
    if gain_r >= config.TRAIL_START_R:
        trail = price - sign * r * config.TRAIL_DISTANCE_R
        new = max(new, trail) if sign == 1 else min(new, trail)
        
    return new
