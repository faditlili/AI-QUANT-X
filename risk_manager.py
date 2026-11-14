"""Risk controls for a virtual portfolio."""
import time
from datetime import datetime
import config
from brain import Brain

class RiskManager:
    def __init__(self, database):
        self.db = database
        self.brain = Brain(database)

    def calculate_open_risk(self):
        return sum(float(p["risk_amount"]) for p in self.db.get_open_positions())

    def get_risk_status(self):
        portfolio = self.db.get_portfolio()
        cap = portfolio["equity"] * config.MAX_PORTFOLIO_RISK_PCT / 100
        used = self.calculate_open_risk()
        baseline = self.db.refresh_daily_baseline()
        daily_change = portfolio["equity"] - baseline
        daily_limit = baseline * config.DAILY_LOSS_LIMIT_PCT / 100
        return {"equity": portfolio["equity"], "open_risk": used, "risk_cap": cap,
                "risk_remaining": max(0, cap - used), "daily_change": daily_change,
                "daily_loss_limit": daily_limit, "daily_limit_hit": daily_change <= -daily_limit}

    def protection_status(self):
        closed = sorted([t for t in self.db.get_recent_trades(config.MAX_CONSECUTIVE_LOSSES*6) if t["status"]=="CLOSED"],
                      key=lambda t:t["closed_at"] or "", reverse=True)
        last = closed[:config.MAX_CONSECUTIVE_LOSSES]
        if len(last) == config.MAX_CONSECUTIVE_LOSSES and all((t["net_pnl"] or 0)<0 for t in last):
            try: age = time.time() - datetime.fromisoformat(last[0]["closed_at"]).timestamp()
            except Exception: age = config.LOSS_STREAK_PAUSE_SECONDS
            if age < config.LOSS_STREAK_PAUSE_SECONDS:
                return True, "Paused after consecutive losses"
        equity = self.db.get_portfolio()["equity"]
        until = float(self.db.get_state("dd_block_until","0"))
        now = time.time()
        if until:
            if now < until: return True, "Maximum drawdown pause"
            self.db.reset_peak(equity); self.db.set_state("dd_block_until","0")
            return False, ""
        peak = self.db.get_peak_equity()
        if peak > 0 and (peak-equity)/peak*100 >= config.MAX_DRAWDOWN_PCT:
            self.db.set_state("dd_block_until", now+config.DRAWDOWN_PAUSE_SECONDS)
            return True, "Maximum drawdown reached"
        return False, ""

    def calculate_position_size(self, symbol, source, side, price, atr, stop_mult=None, rr=None, strategy="trend"):
        if source not in ("spot","futures") or side not in ("LONG","SHORT"):
            return None, "Invalid market or side"
        if source=="spot" and side=="SHORT": return None, "Spot simulation is long-only"
        if price<=0 or atr<=0: return None, "Invalid price or ATR"
            
        p = self.db.get_portfolio()
        status = self.get_risk_status()
        
        if status["daily_limit_hit"]: return None, "Daily loss limit reached"
        if p["open_count"] >= config.MAX_OPEN_POSITIONS: return None, "Maximum open positions reached"
        if any(x["symbol"]==symbol and x["source"]==source for x in self.db.get_open_positions()):
            return None, "Duplicate open position"
        
        blocked, why = self.protection_status()
        if blocked: return None, why
            
        # 1. استخدام العقل الديناميكي
        if not self.brain.is_strategy_healthy(strategy, None):
            return None, f"Strategy {strategy} paused due to consecutive losses"
            
        dynamic_risk_pct = self.brain.get_dynamic_risk()

        stop_mult = stop_mult or config.ATR_STOP_MULTIPLIER
        rr = rr or config.REWARD_RISK_RATIO
        stop_dist = atr * stop_mult
        
        if stop_dist * rr / price * 100 < config.MIN_TARGET_PCT:
            return None, "Target too small vs. costs"
            
        stop = price - stop_dist if side=="LONG" else price + stop_dist
        
        # 2. حساب الميزانية
        risk_budget = min(p["equity"] * dynamic_risk_pct / 100, status["risk_remaining"])
        cash_cap = p["cash_balance"] / (1 + config.fee_rate(source) + config.SLIPPAGE_BPS/10000 + 0.002)
        allocation = min(p["equity"] * config.MAX_ALLOCATION_PCT / 100, cash_cap)
        
        qty = min(risk_budget / stop_dist, allocation / price)
        notional = qty * price
        fee = notional * config.fee_rate(source)
        
        if qty <= 0 or notional < config.MIN_NOTIONAL_USDT: return None, "Insufficient virtual cash"
        if notional + fee > p["cash_balance"]: return None, "Insufficient cash"
            
        actual_risk = qty * stop_dist
        
        # 3. إدارة الحرارة
        open_positions = self.db.get_open_positions()
        directional_risk = sum(float(pos["risk_amount"]) for pos in open_positions if pos["side"] == side)
        max_directional_risk = p["equity"] * config.MAX_DIRECTIONAL_HEAT_PCT / 100
        
        total_risk = sum(float(pos["risk_amount"]) for pos in open_positions)
        max_total_risk = p["equity"] * config.MAX_TOTAL_HEAT_PCT / 100
        
        if directional_risk + actual_risk > max_directional_risk:
            return None, f"Heat Blocked: Max {side} risk reached"
        if total_risk + actual_risk > max_total_risk:
            return None, f"Heat Blocked: Max Total risk reached"

        return {"quantity": qty, "stop_price": stop,
                "target_price": price+stop_dist*rr if side=="LONG" else price-stop_dist*rr,
                "margin_used": notional, "risk_amount": actual_risk, "opening_fee": fee}, ""

    def assess(self):
        s = self.get_risk_status()
        return {"allowed": not s["daily_limit_hit"] and s["risk_remaining"]>0, **s}
