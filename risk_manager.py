"""Risk controls for the virtual portfolio.

All hard numeric limits live in accounting.check_portfolio_limits (also enforced atomically inside
Database.create_position). This class adds the state-based protections (loss streak, drawdown,
strategy kill-switch, data outage) and the position sizing.
"""
import time

import accounting
import config
from brain import Brain, _parse_time


class RiskManager:
    def __init__(self, database):
        self.db = database
        self.brain = Brain(database)
        self.data_ok = True
        self.data_reason = ""

    # --- data-outage protection -------------------------------------------------
    def set_data_status(self, ok, reason=""):
        self.data_ok, self.data_reason = bool(ok), reason

    # --- status -----------------------------------------------------------------
    def calculate_open_risk(self):
        return accounting.total_open_risk(self.db.get_open_positions())

    def get_risk_status(self):
        portfolio = self.db.get_portfolio()
        cap = accounting.portfolio_risk_cap(portfolio["equity"])
        used = portfolio["open_risk"]
        baseline = self.db.refresh_daily_baseline()
        daily_change = portfolio["equity"] - baseline
        daily_limit = baseline * config.DAILY_LOSS_LIMIT_PCT / 100
        return {"equity": portfolio["equity"], "open_risk": used, "risk_cap": cap,
                "risk_remaining": max(0.0, cap - used), "daily_change": daily_change,
                "daily_loss_limit": daily_limit, "daily_limit_hit": daily_change <= -daily_limit,
                "max_portfolio_risk_pct": min(config.MAX_PORTFOLIO_RISK_PCT, accounting.HARD_MAX_PORTFOLIO_RISK_PCT)}

    def protection_status(self):
        closed = self.db.get_closed_trades(config.MAX_CONSECUTIVE_LOSSES * 6)
        last = closed[:config.MAX_CONSECUTIVE_LOSSES]
        if len(last) == config.MAX_CONSECUTIVE_LOSSES and all((t["net_pnl"] or 0) < 0 for t in last):
            closed_ts = _parse_time(last[0]["closed_at"])
            age = (time.time() - closed_ts) if closed_ts is not None else config.LOSS_STREAK_PAUSE_SECONDS
            if age < config.LOSS_STREAK_PAUSE_SECONDS:
                return True, "Paused after consecutive losses"
        equity = self.db.get_portfolio()["equity"]
        until = float(self.db.get_state("dd_block_until", "0"))
        now = time.time()
        if until:
            if now < until:
                return True, "Maximum drawdown pause"
            self.db.reset_peak(equity)
            self.db.set_state("dd_block_until", "0")
            return False, ""
        peak = self.db.get_peak_equity()
        if peak > 0 and (peak - equity) / peak * 100 >= config.MAX_DRAWDOWN_PCT:
            self.db.set_state("dd_block_until", now + config.DRAWDOWN_PAUSE_SECONDS)
            return True, "Maximum drawdown reached"
        return False, ""

    # --- sizing -----------------------------------------------------------------
    def calculate_position_size(self, symbol, source, side, price, atr, stop_mult=None, rr=None,
                                strategy="trend", rules=None):
        """Size a trade. `price` is the signal/live price; slippage is applied here so the stop,
        target, quantity and risk are all computed from the EXPECTED FILL, exactly like the DB records them."""
        if source not in ("spot", "futures") or side not in ("LONG", "SHORT"):
            return None, "Invalid market or side"
        if source == "spot" and side == "SHORT":
            return None, "Spot simulation is long-only"
        if not (accounting.is_valid_price(price) and accounting.is_valid_price(atr)):
            return None, "Invalid price or ATR"
        if not self.data_ok:
            return None, f"Market data outage: {self.data_reason or 'stale prices'}"
        if rules is None and config.REQUIRE_SYMBOL_RULES:
            return None, "Exchange trading rules unavailable"

        p = self.db.get_portfolio()
        status = self.get_risk_status()
        if status["daily_limit_hit"]:
            return None, "Daily loss limit reached"
        positions = self.db.get_open_positions()
        if len(positions) >= config.MAX_OPEN_POSITIONS:
            return None, "Maximum open positions reached"
        if any(x["symbol"] == symbol for x in positions):
            return None, "Duplicate open position"
        blocked, why = self.protection_status()
        if blocked:
            return None, why
        if not self.brain.is_strategy_healthy(strategy, None):
            return None, f"Strategy {strategy} paused due to consecutive losses"

        stop_mult = stop_mult or config.ATR_STOP_MULTIPLIER
        rr = rr or config.REWARD_RISK_RATIO
        stop_dist = atr * stop_mult
        if stop_dist * rr / price * 100 < config.MIN_TARGET_PCT:
            return None, "Target too small vs. costs"

        sign = accounting.side_sign(side)
        entry = accounting.entry_fill(price, side)
        stop = entry - sign * stop_dist
        target = entry + sign * stop_dist * rr
        if stop <= 0:
            return None, "Stop would be non-positive"
        if rules:
            stop = accounting.round_to_tick(stop, rules.get("tick")) or stop
            target = accounting.round_to_tick(target, rules.get("tick")) or target

        risk_pct = self.brain.get_dynamic_risk()
        budget = min(p["equity"] * risk_pct / 100, status["risk_remaining"])
        lev = config.FUTURES_LEVERAGE if source == "futures" else 1.0
        sized, reason = accounting.size_position(
            equity=p["equity"], cash=p["cash_balance"], entry=entry, stop=stop, side=side, source=source,
            risk_budget=budget, leverage=lev, rules=rules)
        if not sized:
            return None, reason
        liq = sized["liquidation_price"]
        if liq is not None and sign * (stop - liq) <= 0:
            return None, "Stop lies beyond the liquidation price"

        ok, why = accounting.check_portfolio_limits(
            equity=p["equity"], cash=p["cash_balance"], positions=positions,
            cand={"symbol": symbol, "source": source, "side": side, "margin_used": sized["margin_used"],
                  "opening_fee": sized["opening_fee"], "risk_amount": sized["risk_amount"]},
            daily_change=status["daily_change"], daily_limit=status["daily_loss_limit"])
        if not ok:
            return None, why
        return {"quantity": sized["quantity"], "entry_price": entry, "stop_price": stop, "target_price": target,
                "margin_used": sized["margin_used"], "risk_amount": sized["risk_amount"],
                "initial_risk": sized["initial_risk"], "opening_fee": sized["opening_fee"],
                "leverage": sized["leverage"], "liquidation_price": liq}, ""

    def assess(self):
        s = self.get_risk_status()
        return {"allowed": not s["daily_limit_hit"] and s["risk_remaining"] > 0, **s}
