"""Stop management shared by the live paper trader and the backtester."""
import accounting
import config


def breakeven_stop(side, entry, fee, slippage_bps=None):
    """Stop level that covers both round-trip fees and the slippage."""
    sign = accounting.side_sign(side)
    return entry * (1 + sign * (2 * fee + accounting.slip_rate(slippage_bps)))


def next_stop(side, entry, initial_stop, stop, price, trailing=None, fee=None):
    """Ratchet only: the returned stop is never looser than the current one."""
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
    sign = accounting.side_sign(side)
    gain_r = (price - entry) * sign / r
    new = stop
    if gain_r >= config.BREAKEVEN_AT_R:
        be = breakeven_stop(side, entry, fee)
        new = max(new, be) if sign == 1 else min(new, be)
    if gain_r >= config.TRAIL_START_R:
        trail = price - sign * r * config.TRAIL_DISTANCE_R
        new = max(new, trail) if sign == 1 else min(new, trail)
    return new
