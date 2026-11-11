"""Pluggable strategies. Each one returns a candidate dict or None.

A candidate carries: strategy, side, score (0-100), reasons, confirmed (gate that must
pass), stop_mult (ATR multiples for the stop) and rr (reward/risk target).
select_signal() picks the regime, runs the strategies allowed in it, applies the shared
gates (spot-long-only, news risk, minimum score) and returns one decision.
"""
import config
from indicators import direction
from decision_engine import calculate_technical_score, evaluate_setup
from regime import detect_regime

def _htf_dir(ctx):
    dirs = ctx.get("dirs") or []
    return dirs[-1] if dirs else "NEUTRAL"

class TrendStrategy:
    name = "trend"
    regimes = {"TREND", "TRANSITION"}

    def evaluate(self, ctx):
        tech = calculate_technical_score(ctx["primary"])
        side = tech["side"]
        if side == "NONE":
            return None
        dirs = ctx.get("dirs") or []
        want = "BULLISH" if side == "LONG" else "BEARISH"
        confirmed = bool(dirs) and len(set(dirs)) == 1 and dirs[0] == want
        reasons = list(tech["reasons"])
        if not confirmed:
            reasons.append("Timeframes do not agree")
        return {"strategy": self.name, "side": side, "score": tech["score"], "reasons": reasons,
                "confirmed": confirmed, "stop_mult": config.ATR_STOP_MULTIPLIER,
                "rr": config.REWARD_RISK_RATIO}

class MeanReversionStrategy:
    name = "mean_reversion"
    regimes = {"RANGE"}

    def evaluate(self, ctx):
        p = ctx["primary"]
        z, rsi = p["zscore"], p["rsi"]
        if z <= -2 and rsi <= 38:
            side = "LONG"
        elif z >= 2 and rsi >= 62:
            side = "SHORT"
        else:
            return None
        score, reasons = 40, [f"Price stretched {abs(z):.1f} sigma from its mean"]
        if (side == "LONG" and rsi <= 32) or (side == "SHORT" and rsi >= 68):
            score += 20; reasons.append("RSI at an extreme")
        else:
            score += 10; reasons.append("RSI leaning extreme")
        if p["adx"] < config.RANGE_ADX_MAX:
            score += 15; reasons.append("Market is ranging (low ADX)")
        if p["volume_ratio"] < 2.0:
            score += 15; reasons.append("No panic-volume spike")
        htf = _htf_dir(ctx)
        confirmed = htf != ("BEARISH" if side == "LONG" else "BULLISH")
        if not confirmed:
            reasons.append("Higher timeframe trend opposes the trade")
        return {"strategy": self.name, "side": side, "score": score, "reasons": reasons,
                "confirmed": confirmed, "stop_mult": 1.5, "rr": 1.5}

class BreakoutStrategy:
    name = "breakout"
    regimes = {"SQUEEZE", "RANGE", "TRANSITION", "TREND"}

    def evaluate(self, ctx):
        p = ctx["primary"]
        if not p["squeeze"]:
            return None
        if p["close"] > p["donchian_high"]:
            side = "LONG"
        elif p["close"] < p["donchian_low"]:
            side = "SHORT"
        else:
            return None
        score, reasons = 35, ["Close broke the 20-candle channel"]
        score += 20; reasons.append("Breakout follows a volatility squeeze")
        vr = p["volume_ratio"]
        if vr >= 1.5:
            score += 20; reasons.append("Strong breakout volume")
        elif vr >= 1.2:
            score += 10; reasons.append("Above-average volume")
        rsi = p["rsi"]
        if (side == "LONG" and 30 < rsi < 75) or (side == "SHORT" and 25 < rsi < 70):
            score += 15; reasons.append("RSI not exhausted")
        htf = _htf_dir(ctx)
        confirmed = htf != ("BEARISH" if side == "LONG" else "BULLISH")
        if htf == ("BULLISH" if side == "LONG" else "BEARISH"):
            score += 10; reasons.append("Higher timeframe agrees")
        if not confirmed:
            reasons.append("Higher timeframe trend opposes the trade")
        return {"strategy": self.name, "side": side, "score": score, "reasons": reasons,
                "confirmed": confirmed, "stop_mult": 1.5, "rr": 2.5}

REGISTRY = {s.name: s for s in (TrendStrategy(), MeanReversionStrategy(), BreakoutStrategy())}

def _decision(regime, cand, res):
    base = {"regime": regime, "strategy": cand["strategy"], "score": cand["score"],
            "stop_mult": cand["stop_mult"], "rr": cand["rr"]}
    base["reason"] = f"[{regime}/{cand['strategy']}] {res['reason']}"
    base["action"] = res["action"]
    if res["action"] != "HOLD":
        base["side"] = res["side"]
    return base

def select_signal(ctx, enabled=None):
    # --- Session Filter (تجنب التداول في أوقات السيولة الميتة) ---
    if getattr(config, 'USE_SESSION_FILTER', False):
        import datetime
        current_hour = datetime.datetime.now(datetime.timezone.utc).hour
        if not (config.LONDON_OPEN <= current_hour < config.SESSION_END):
            return {"regime": "OUT_OF_SESSION", "strategy": None, "score": 0, "action": "HOLD",
                    "reason": "Outside high-liquidity trading sessions", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}

    regime = detect_regime(ctx["primary"])
    if regime == "HIGH_VOL":
        return {"regime": regime, "strategy": None, "score": 0, "action": "HOLD",
                "reason": f"[{regime}] Volatility too high, standing aside",
                "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}
    
    results = []
    for name in (enabled or config.STRATEGIES):
        strat = REGISTRY.get(name)
        if not strat or regime not in strat.regimes:
            continue
        cand = strat.evaluate(ctx)
        if not cand:
            continue
            
        # --- Advanced Filters (VWAP & Funding Rate) ---
        if cand["side"] == "LONG":
            # 1. VWAP Filter (لا تشتري إذا كان السعر تحت المؤسسات)
            if "vwap" in ctx["primary"] and ctx["primary"]["price"] < ctx["primary"]["vwap"]:
                cand["reasons"].append("Price below VWAP (Institutional resistance)")
                cand["confirmed"] = False
                
            # 2. Funding Rate Filter (لا تشتري في قمة الزحام)
            if getattr(config, 'USE_FUNDING_RATE_FILTER', False):
                funding = ctx.get("funding_rate", 0.0)
                if funding > config.MAX_LONG_FUNDING_RATE:
                    cand["reasons"].append(f"Funding rate too high ({funding:.4f})")
                    cand["confirmed"] = False
                    
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
    return {"regime": regime, "strategy": None, "score": 0, "action": "HOLD",
            "reason": f"[{regime}] No setup from the enabled strategies",
            "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}
