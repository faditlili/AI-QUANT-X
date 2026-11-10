"""Risk controls for a virtual portfolio. Aggregate open risk is capped at 10%."""
import config

class RiskManager:
    def __init__(self, database):
        self.db=database

    def calculate_open_risk(self):
        return sum(float(p["risk_amount"]) for p in self.db.get_open_positions())

    def get_risk_status(self):
        portfolio=self.db.get_portfolio()
        cap=portfolio["equity"]*config.MAX_PORTFOLIO_RISK_PCT/100
        used=self.calculate_open_risk()
        baseline=self.db.refresh_daily_baseline()
        daily_change=portfolio["equity"]-baseline
        daily_limit=baseline*config.DAILY_LOSS_LIMIT_PCT/100
        return {"equity":portfolio["equity"],"open_risk":used,"risk_cap":cap,
                "risk_remaining":max(0,cap-used),"daily_change":daily_change,
                "daily_loss_limit":daily_limit,"daily_limit_hit":daily_change <= -daily_limit}

    def calculate_position_size(self, symbol, source, side, price, atr):
        if source not in ("spot","futures") or side not in ("LONG","SHORT"):
            return None, "Invalid market or side"
        if source=="spot" and side=="SHORT":
            return None, "Spot simulation is long-only"
        if price<=0 or atr<=0:
            return None, "Invalid price or ATR"
        p=self.db.get_portfolio()
        status=self.get_risk_status()
        if status["daily_limit_hit"]:
            return None, "Daily loss limit reached"
        if p["open_count"]>=config.MAX_OPEN_POSITIONS:
            return None, "Maximum open positions reached"
        if any(x["symbol"]==symbol and x["source"]==source for x in self.db.get_open_positions()):
            return None, "Duplicate open position"
        stop_dist=atr*config.ATR_STOP_MULTIPLIER
        stop=price-stop_dist if side=="LONG" else price+stop_dist
        risk_budget=min(p["equity"]*config.RISK_PER_TRADE_PCT/100,status["risk_remaining"])
        allocation=p["equity"]*config.MAX_ALLOCATION_PCT/100
        qty=min(risk_budget/stop_dist,allocation/price)
        notional=qty*price
        fee=notional*config.FEE_RATE
        if qty<=0 or notional+fee>p["cash_balance"]:
            return None, "Insufficient virtual cash"
        return {"quantity":qty,"stop_price":stop,
                "target_price":price+stop_dist*config.REWARD_RISK_RATIO if side=="LONG" else price-stop_dist*config.REWARD_RISK_RATIO,
                "margin_used":notional,"risk_amount":qty*stop_dist,"opening_fee":fee}, ""

    def assess(self):
        s=self.get_risk_status()
        return {"allowed":not s["daily_limit_hit"] and s["risk_remaining"]>0,**s}
