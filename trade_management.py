"""Stop management shared by the live paper trader and the backtester (identical logic)."""
import config

def next_stop(side, entry, initial_stop, stop, price, trailing=None):
    """Chandelier Exit: Trails the stop based on ATR, maximizing trend profits."""
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
    
    # 1. Break-even (نقل الوقف لنقطة الدخول عند ربح 1R لحماية رأس المال)
    if gain_r >= config.BREAKEVEN_AT_R:
        be = entry * (1 + sign * (2 * config.FEE_RATE + config.SLIPPAGE_BPS / 10000))
        new = max(new, be) if sign == 1 else min(new, be)
        
    # 2. Chandelier Exit (الوقف المتدلي الذكي)
    if gain_r >= config.TRAIL_START_R:
        # 3.0 هو مضاعف الصبر. كلما زاد الرقم، ترك البوت الصفقة تجري أطول.
        dynamic_multiplier = 3.0 
        trail = price - sign * r * dynamic_multiplier
        new = max(new, trail) if sign == 1 else min(new, trail)
        
    return new
