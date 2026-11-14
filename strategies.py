"""Pluggable strategies with Macro Filters (Symmetric for Long & Short)."""
import config, datetime
from indicators import direction
from decision_engine import calculate_technical_score, evaluate_setup
from regime import detect_regime

def _vwap(ctx):
    p = ctx["primary"]
    key = "vwap24" if getattr(config, "USE_ROLLING_VWAP", True) else "vwap"
    return p.get(key, p.get("vwap"))

def _htf_dir(ctx):
    dirs = ctx.get("dirs") or []
    return dirs[-1] if dirs else "NEUTRAL"

class TrendStrategy:
    name = "trend"
    regimes = {"TREND", "TRANSITION"}
    def evaluate(self, ctx):
        tech = calculate_technical_score(ctx["primary"])
        side = tech["side"]
        if side == "NONE": return None
        dirs = ctx.get("dirs") or []
        want = "BULLISH" if side == "LONG" else "BEARISH"
        
        # --- تعديل القناص: نكتفي بتأكيد إطار الساعة وإطار الـ 4 ساعات ---
        opposite = "BEARISH" if side == "LONG" else "BULLISH"
        htf_ok = (dirs[-1] == want) if getattr(config, "STRICT_HTF_CONFIRM", False) else (dirs[-1] != opposite)
        confirmed = len(dirs) >= 2 and dirs[1] == want and htf_ok
        
        reasons = list(tech["reasons"])
        if not confirmed: reasons.append("Timeframes do not agree")
        return {"strategy": self.name, "side": side, "score": tech["score"], "reasons": reasons, "confirmed": confirmed, "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}

class MeanReversionStrategy:
    name = "mean_reversion"
    regimes = {"RANGE"}
    def evaluate(self, ctx):
        p = ctx["primary"]
        z, rsi = p["zscore"], p["rsi"]
        
        # --- تعديل القناص: تخفيف شروط الارتداد قليلاً لالتقاط صفقات في السوق العرضي ---
        if z <= -1.5 and rsi <= 42: side = "LONG"
        elif z >= 1.5 and rsi >= 58: side = "SHORT"
        else: return None
        
        score, reasons = 40, [f"Price stretched {abs(z):.1f} sigma"]
        if (side == "LONG" and rsi <= 32) or (side == "SHORT" and rsi >= 68): score += 20; reasons.append("RSI extreme")
        else: score += 10; reasons.append("RSI leaning extreme")
        if p["adx"] < config.RANGE_ADX_MAX: score += 15; reasons.append("Ranging market")
        if p["volume_ratio"] < 2.0: score += 15; reasons.append("No panic volume")
        htf = _htf_dir(ctx)
        confirmed = htf != ("BEARISH" if side == "LONG" else "BULLISH")
        if not confirmed: reasons.append("HTF opposes")
        return {"strategy": self.name, "side": side, "score": score, "reasons": reasons, "confirmed": confirmed, "stop_mult": 1.5, "rr": 1.5}

class BreakoutStrategy:
    name = "breakout"
    regimes = {"SQUEEZE", "RANGE", "TRANSITION", "TREND"}
    def evaluate(self, ctx):
        p = ctx["primary"]
        if not p["squeeze"]: return None
        if p["close"] > p["donchian_high"]: side = "LONG"
        elif p["close"] < p["donchian_low"]: side = "SHORT"
        else: return None
        score, reasons = 35, ["Broke 20-candle channel"]
        score += 20; reasons.append("Follows a squeeze")
        vr = p["volume_ratio"]
        if vr >= 1.5: score += 20; reasons.append("Strong volume")
        elif vr >= 1.2: score += 10; reasons.append("Above avg volume")
        rsi = p["rsi"]
        if (side == "LONG" and 30 < rsi < 75) or (side == "SHORT" and 25 < rsi < 70): score += 15; reasons.append("RSI not exhausted")
        htf = _htf_dir(ctx)
        confirmed = htf != ("BEARISH" if side == "LONG" else "BULLISH")
        if htf == ("BULLISH" if side == "LONG" else "BEARISH"): score += 10; reasons.append("HTF agrees")
        if not confirmed: reasons.append("HTF opposes")
        return {"strategy": self.name, "side": side, "score": score, "reasons": reasons, "confirmed": confirmed, "stop_mult": 1.5, "rr": 2.5}

REGISTRY = {s.name: s for s in (TrendStrategy(), MeanReversionStrategy(), BreakoutStrategy())}

def _decision(regime, cand, res):
    base = {"regime": regime, "strategy": cand["strategy"], "score": cand["score"], "stop_mult": cand["stop_mult"], "rr": cand["rr"]}
    base["reason"] = f"[{regime}/{cand['strategy']}] {res['reason']}"
    base["action"] = res["action"]
    if res["action"] != "HOLD": base["side"] = res["side"]
    return base

def select_signal(ctx, enabled=None):
    # 1. Session Filter
    if getattr(config, 'USE_SESSION_FILTER', False):
        current_hour = ctx.get("hour_utc", datetime.datetime.now(datetime.timezone.utc).hour)
        if not (config.LONDON_OPEN <= current_hour < config.SESSION_END):
            return {"regime": "OUT_OF_SESSION", "strategy": None, "score": 0, "action": "HOLD", "reason": "Outside high-liquidity sessions", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}

    regime = detect_regime(ctx["primary"])
    if regime == "HIGH_VOL":
        return {"regime": regime, "strategy": None, "score": 0, "action": "HOLD", "reason": f"[{regime}] Volatility too high", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}
    
    results = []
    for name in (enabled or config.STRATEGIES):
        strat = REGISTRY.get(name)
        if not strat or regime not in strat.regimes: continue
        cand = strat.evaluate(ctx)
        if not cand: continue
            
        # --- الفلاتر المتقدمة (متوازنة للشراء والبيع) ---
        if cand["side"] == "LONG":
            if _vwap(ctx) is not None and ctx["primary"]["price"] < _vwap(ctx):
                cand["reasons"].append("Price below VWAP"); cand["confirmed"] = False
            if getattr(config, 'USE_FUNDING_RATE_FILTER', False):
                funding = ctx.get("funding_rate", 0.0)
                if funding > config.MAX_LONG_FUNDING_RATE:
                    cand["reasons"].append(f"Funding high ({funding:.4f})"); cand["confirmed"] = False
            taker_ratio = ctx["primary"].get("taker_buy_ratio", 0.5)
            if taker_ratio < 0.45:
                cand["reasons"].append(f"Weak Takers ({taker_ratio:.2f})"); cand["confirmed"] = False
            if ctx.get("fear_greed", 50) > 80:
                cand["reasons"].append("Extreme Greed"); cand["confirmed"] = False
            if ctx.get("breadth", 50.0) < 30.0:
                cand["reasons"].append("Weak Breadth"); cand["confirmed"] = False
                
        elif cand["side"] == "SHORT":
            # فلاتر البيع العكسية
            if _vwap(ctx) is not None and ctx["primary"]["price"] > _vwap(ctx):
                cand["reasons"].append("Price above VWAP"); cand["confirmed"] = False
            if getattr(config, 'USE_FUNDING_RATE_FILTER', False):
                funding = ctx.get("funding_rate", 0.0)
                if funding < config.MIN_SHORT_FUNDING_RATE:
                    cand["reasons"].append(f"Funding low ({funding:.4f})"); cand["confirmed"] = False
            taker_ratio = ctx["primary"].get("taker_buy_ratio", 0.5)
            if taker_ratio > 0.55: # مشترون أقوياء جداً، لا تبع
                cand["reasons"].append(f"Strong Takers ({taker_ratio:.2f})"); cand["confirmed"] = False
            if ctx.get("fear_greed", 50) < 20:
                cand["reasons"].append("Extreme Fear"); cand["confirmed"] = False
            if ctx.get("breadth", 50.0) > 70.0:
                cand["reasons"].append("Strong Breadth"); cand["confirmed"] = False
                    
        # بوصلة BTC/ETH: لا نعاكس اتجاه الثقيلتين معاً (لا تنطبق على BTC وETH نفسيهما)
        compass = ctx.get("compass")
        if compass and getattr(config, "USE_BTC_COMPASS", False) and ctx.get("symbol") not in config.DIRECTION_SYMBOLS:
            if cand["side"] == "LONG" and compass == "BEARISH":
                cand["reasons"].append("BTC/ETH trend is bearish"); cand["confirmed"] = False
            elif cand["side"] == "SHORT" and compass == "BULLISH":
                cand["reasons"].append("BTC/ETH trend is bullish"); cand["confirmed"] = False

        tech = {"score": cand["score"], "side": cand["side"], "reasons": cand["reasons"]}
        res = evaluate_setup(tech, ctx["source"], cand["confirmed"], ctx.get("news_risk", 0.0))
        results.append((cand, res))
        
    entries = [(c, r) for c, r in results if r["action"] != "HOLD"]
    if entries:
        cand, res = max(entries, key=lambda x: x[0]["score"])
        return _decision(regime, cand, res)
    if results:
        cand, res = max(results, key=lambda x: x[0]["score"])
        return _decision(regime, cand, res)
    return {"regime": regime, "strategy": None, "score": 0, "action": "HOLD", "reason": f"[{regime}] No setup", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}
