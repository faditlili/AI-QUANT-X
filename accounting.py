"""Pure financial math shared by the live paper trader, risk manager, database and backtester.

Nothing here touches the network or the database, so every formula can be unit-tested and the
live engine and the backtester are guaranteed to use the SAME arithmetic.

Conventions
-----------
* side sign: LONG = +1, SHORT = -1.
* "R unit" (initial_risk) = quantity * |entry - initial_stop|  (price risk only, immutable).
* "open risk" (risk_amount) = worst-case loss still ahead if the CURRENT stop is hit, including the
  exit fee and exit slippage. The entry fee of an already open position is sunk (already paid).
  A brand-new candidate additionally carries its entry fee.
* Portfolio cap: sum(open risk) + candidate risk <= 10% of CURRENT equity (hard ceiling, see below).
"""
import math
from decimal import Decimal, ROUND_DOWN

import config

HARD_MAX_PORTFOLIO_RISK_PCT = 10.0
EPS = 1e-9
CASH_BUFFER = 0.999


def is_valid_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def is_valid_price(x):
    return is_valid_number(x) and x > 0


def side_sign(side):
    if side == "LONG":
        return 1
    if side == "SHORT":
        return -1
    raise ValueError("side must be LONG or SHORT")


def slip_rate(slippage_bps=None):
    return (config.SLIPPAGE_BPS if slippage_bps is None else slippage_bps) / 10000.0


def fee_rate(source, fee=None):
    return config.fee_rate(source) if fee is None else fee


def entry_fill(price, side, slippage_bps=None):
    return price * (1 + side_sign(side) * slip_rate(slippage_bps))


def exit_fill(price, side, slippage_bps=None):
    return price * (1 - side_sign(side) * slip_rate(slippage_bps))


def gross_pnl(side, entry, exit_price, qty):
    return (exit_price - entry) * qty * side_sign(side)


def stop_risk(side, entry, stop, qty, source, fee=None, slippage_bps=None, entry_fee=0.0):
    f = fee_rate(source, fee)
    s = slip_rate(slippage_bps)
    move = side_sign(side) * (entry - stop) * qty
    return max(0.0, move + qty * stop * (f + s) + entry_fee)


def position_open_risk(pos, fee=None, slippage_bps=None):
    return stop_risk(
        pos["side"], float(pos["entry_price"]), float(pos["stop_price"]),
        float(pos["quantity"]), pos["source"], fee, slippage_bps
    )


def total_open_risk(positions, fee=None, slippage_bps=None):
    return sum(position_open_risk(p, fee, slippage_bps) for p in positions)


def portfolio_risk_cap(equity):
    pct = min(config.MAX_PORTFOLIO_RISK_PCT, HARD_MAX_PORTFOLIO_RISK_PCT)
    return max(0.0, equity) * pct / 100.0


def liquidation_price(side, entry, leverage, maintenance_rate=None):
    mmr = config.MAINTENANCE_MARGIN_RATE if maintenance_rate is None else maintenance_rate
    lev = max(1.0, float(leverage))
    if side == "LONG":
        return max(0.0, entry * (1 - 1 / lev + mmr))
    return entry * (1 + 1 / lev - mmr)


def funding_payment(side, notional, rate):
    return side_sign(side) * notional * rate


def floor_to_step(value, step):
    if not step or step <= 0:
        return value
    d = Decimal(str(value)) / Decimal(str(step))
    return float(d.to_integral_value(rounding=ROUND_DOWN) * Decimal(str(step)))


def round_to_tick(value, tick):
    if not tick or tick <= 0:
        return value
    return float((Decimal(str(value)) / Decimal(str(tick))).to_integral_value() * Decimal(str(tick)))


def size_position(*, equity, cash, entry, stop, side, source, risk_budget, leverage=1.0,
                  alloc_pct=None, fee=None, slippage_bps=None, rules=None):
    if not (is_valid_price(entry) and is_valid_price(stop)):
        return None, "Invalid entry or stop price"
    if side_sign(side) * (entry - stop) <= 0:
        return None, "Stop is on the wrong side of entry"
    if risk_budget <= 0:
        return None, "No risk budget left"

    f = fee_rate(source, fee)
    s = slip_rate(slippage_bps)
    lev = max(1.0, float(leverage)) if source == "futures" else 1.0
    alloc = config.MAX_ALLOCATION_PCT if alloc_pct is None else alloc_pct

    per_unit_risk = side_sign(side) * (entry - stop) + stop * (f + s) + entry * f
    qty = risk_budget / per_unit_risk
    qty = min(qty, max(0.0, equity) * alloc / 100.0 * lev / entry)
    qty = min(qty, cash * CASH_BUFFER / (entry / lev + entry * f))

    if rules:
        qty = floor_to_step(qty, rules.get("step"))
        if qty < (rules.get("min_qty") or 0):
            return None, "Below exchange minimum quantity"

    notional = qty * entry
    min_notional = max(config.MIN_NOTIONAL_USDT, (rules or {}).get("min_notional") or 0)
    if qty <= 0 or notional < min_notional:
        return None, "Insufficient virtual cash or below minimum notional"

    entry_fee = notional * f
    margin = notional / lev
    risk = stop_risk(
        side, entry, stop, qty, source, f, slippage_bps, entry_fee=entry_fee
    )

    return {
        "quantity": qty,
        "notional": notional,
        "margin_used": margin,
        "opening_fee": entry_fee,
        "risk_amount": risk,
        "initial_risk": qty * abs(entry - stop),
        "leverage": lev,
        "liquidation_price": liquidation_price(side, entry, lev)
            if source == "futures" else None
    }, ""


def check_portfolio_limits(*, equity, cash, positions, cand, daily_change=0.0, daily_limit=None):
    if cand["source"] not in ("spot", "futures") or cand["side"] not in ("LONG", "SHORT"):
        return False, "Invalid market or side"
    if cand["source"] == "spot" and cand["side"] == "SHORT":
        return False, "Spot simulation is long-only"
    if not (is_valid_number(equity) and equity > 0):
        return False, "Equity is not positive"
    if daily_limit is not None and daily_change <= -daily_limit + EPS:
        return False, "Daily loss limit reached"
    if len(positions) >= config.MAX_OPEN_POSITIONS:
        return False, "Maximum open positions reached"
    if any(p["symbol"] == cand["symbol"] for p in positions):
        return False, "Duplicate open position"
    if sum(1 for p in positions if p["side"] == cand["side"]) >= config.MAX_SAME_SIDE:
        return False, f"Maximum {cand['side']} positions reached"
    if cand["margin_used"] + cand["opening_fee"] > cash + EPS:
        return False, "Insufficient cash"

    cap = portfolio_risk_cap(equity)
    open_risk = total_open_risk(positions)
    if open_risk + cand["risk_amount"] > cap + EPS:
        return False, "Aggregate risk cap exceeded"

    dir_cap = min(equity * config.MAX_DIRECTIONAL_HEAT_PCT / 100.0, cap)
    dir_risk = total_open_risk([p for p in positions if p["side"] == cand["side"]])
    if dir_risk + cand["risk_amount"] > dir_cap + EPS:
        return False, f"Heat Blocked: Max {cand['side']} risk reached"

    return True, ""
