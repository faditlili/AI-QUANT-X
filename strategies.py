"""Pluggable strategies with Macro Filters (Symmetric for Long & Short)."""
import config, datetime
from indicators import direction
from decision_engine import calculate_technical_score, evaluate_setup
from regime import detect_regime

TREND_FOLLOWERS = ("trend", "breakout")

def _vwap(ctx):
    p = ctx["primary"]
    key = "vwap24" if getattr(config, "USE_ROLLING_VWAP", True) else "vwap"
    return p.get(key, p.get("vwap"))

def _htf_dir(ctx):
    dirs = ctx.get("dirs") or []
    return dirs[-1] if dirs else "NEUTRAL"

class TrendStrategy:
    name = "trend"
    regimes = {"TREND", "TRANSITION", "HIGH_VOL"}
    def evaluate(self, ctx):
        tech = calculate_technical_score(ctx["primary"])
        side = tech["side"]
        if side == "NONE": return None
        dirs = ctx.get("dirs") or []
        want = "BULLISH" if side == "LONG" else "BEARISH"
        opposite = "BEARISH" if side == "LONG" else "BULLISH"
        htf = _htf_dir(ctx)
        htf_ok = (htf == want) if getattr(config, "STRICT_HTF_CONFIRM", False) else (htf != opposite)
        confirmed = len(dirs) >= 2 and htf_ok
        reasons = list(tech["reasons"])
        if not confirmed: reasons.append("4h trend opposes")
        return {"strategy": self.name, "side": side, "score": tech["score"], "reasons": reasons, "confirmed": confirmed, "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}

class MeanReversionStrategy:
    name = "mean_reversion"
    regimes = {"RANGE"}
    def evaluate(self, ctx):
        p = ctx["primary"]
        z, rsi = p["zscore"], p["rsi"]
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
    regimes = {"SQUEEZE", "RANGE", "TRANSITION", "TREND", "HIGH_VOL"}
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

class DipBuyerStrategy:
    name = "dip_buyer"
    regimes = {"RANGE", "TREND", "TRANSITION", "HIGH_VOL"}
    def evaluate(self, ctx):
        p = ctx["primary"]
        htf = _htf_dir(ctx)
        if p["rsi"] <= 32 and p["zscore"] <= -1.5:
            if htf == "BEARISH": return None
            score = 50
            reasons = ["Sharp drop detected (RSI < 32)"]
            if p["rsi"] < 20: score += 20; reasons.append("Extreme oversold (RSI < 20)")
            if p["volume_ratio"] > 1.5: score += 15; reasons.append("High panic volume")
            if htf == "NEUTRAL": score += 10; reasons.append("HTF stabilizing")
            return {"strategy": self.name, "side": "LONG", "score": score, "reasons": reasons, "confirmed": True, "stop_mult": 1.5, "rr": 1.5}
        elif p["rsi"] >= 72 and p["zscore"] >= 1.5:
            if htf == "BULLISH": return None
            score = 50
            reasons = ["Sharp pump detected (RSI > 72)"]
            if p["rsi"] > 80: score += 20; reasons.append("Extreme overbought (RSI > 80)")
            if p["volume_ratio"] > 1.5: score += 15; reasons.append("High euphoria volume")
            if htf == "NEUTRAL": score += 10; reasons.append("HTF stabilizing")
            return {"strategy": self.name, "side": "SHORT", "score": score, "reasons": reasons, "confirmed": True, "stop_mult": 1.5, "rr": 1.5}
        return None

REGISTRY = {s.name: s for s in (TrendStrategy(), MeanReversionStrategy(), BreakoutStrategy(), DipBuyerStrategy())}

def _side_filters(name, cand, ctx):
    """Return (hard, soft)."""
    p = ctx["primary"]
    is_long = cand["side"] == "LONG"
    hard, soft = [], []

    # HARD 1: crowded funding
    if getattr(config, "USE_FUNDING_RATE_FILTER", False):
        funding = ctx.get("funding_rate", 0.0)
        if is_long and funding > config.MAX_LONG_FUNDING_RATE:
            hard.append(f"Funding high ({funding:.4f})")
        elif (not is_long) and funding < config.MIN_SHORT_FUNDING_RATE:
            hard.append(f"Funding low ({funding:.4f})")

    # HARD 2: BTC/ETH compass
    compass = ctx.get("compass")
    if compass and getattr(config, "USE_BTC_COMPASS", False) and ctx.get("symbol") not in config.DIRECTION_SYMBOLS:
        against = (is_long and compass == "BEARISH") or ((not is_long) and compass == "BULLISH")
        if against:
            (soft if name == "dip_buyer" else hard).append("BTC/ETH trend opposes")

    # HARD 3: Machine Learning Filter
    if getattr(config, "USE_ML_FILTER", False):
        ml_prob = ctx.get("ml_prob", 0.5)
        if is_long and ml_prob < config.ML_CONFIDENCE_THRESHOLD:
            hard.append(f"ML Rejection (Prob: {ml_prob:.2f})")
        elif (not is_long) and ml_prob > config.ML_NEUTRAL_THRESHOLD:
            hard.append(f"ML Rejection (Prob: {ml_prob:.2f})")

    # HARD 4: News Sentiment
    if getattr(config, "USE_SENTIMENT_FILTER", False):
        sent = ctx.get("sentiment", {})
        sent_score = sent.get("score", 0.0)
        if is_long and sent_score <= config.SENTIMENT_BEARISH_BLOCK:
            hard.append(f"News is too Bearish ({sent_score:.2f})")
        elif (not is_long) and sent_score >= config.SENTIMENT_BULLISH_BLOCK:
            hard.append(f"News is too Bullish ({sent_score:.2f})")

    # SOFT: VWAP and order flow
    if name in TREND_FOLLOWERS:
        vwap = _vwap(ctx)
        if vwap is not None:
            if is_long and p["price"] < vwap: soft.append("Price below VWAP")
            if (not is_long) and p["price"] > vwap: soft.append("Price above VWAP")
        taker = p.get("taker_buy_ratio", 0.5)
        if is_long and taker < config.TAKER_LONG_MIN: soft.append(f"Weak Takers ({taker:.2f})")
        if (not is_long) and taker > config.TAKER_SHORT_MAX: soft.append(f"Strong Takers ({taker:.2f})")

    # SOFT: market sentiment and breadth
    if name != "dip_buyer":
        fng = ctx.get("fear_greed", 50)
        breadth = ctx.get("breadth", 50.0)
        if is_long:
            if fng > config.FEAR_GREED_MAX_LONG: soft.append("Extreme Greed")
            if breadth < config.BREADTH_MIN_LONG: soft.append("Weak Breadth")
        else:
            if fng < config.FEAR_GREED_MIN_SHORT: soft.append("Extreme Fear")
            if breadth > config.BREADTH_MAX_SHORT: soft.append("Strong Breadth")

    # SOFT: Order Book Liquidity Walls
    if getattr(config, "USE_ORDER_BOOK_FILTER", False):
        ob = ctx.get("order_book", {})
        if is_long and ob.get("resistance_strength") == "STRONG":
            soft.append("Strong Ask Wall")
        elif (not is_long) and ob.get("support_strength") == "STRONG":
            soft.append("Strong Bid Wall")

    return hard, soft

def _decision(regime, cand, res):
    base = {"regime": regime, "strategy": cand["strategy"], "score": cand["score"], "stop_mult": cand["stop_mult"], "rr": cand["rr"]}
    base["reason"] = f"[{regime}/{cand['strategy']}] {res['reason']}"
    base["action"] = res["action"]
    if res["action"] != "HOLD": base["side"] = res["side"]
    return base

def select_signal(ctx, enabled=None):
    if getattr(config, 'USE_SESSION_FILTER', False):
        current_hour = ctx.get("hour_utc", datetime.datetime.now(datetime.timezone.utc).hour)
        if not (config.LONDON_OPEN <= current_hour < config.SESSION_END):
            return {"regime": "OUT_OF_SESSION", "strategy": None, "score": 0, "action": "HOLD", "reason": "Outside high-liquidity sessions", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}

    regime = detect_regime(ctx["primary"])
    results = []
    
    for name in (enabled or config.STRATEGIES):
        strat = REGISTRY.get(name)
        if not strat: continue
        if regime not in strat.regimes and name != "dip_buyer": continue

        cand = strat.evaluate(ctx)
        if not cand: continue

        blockers = []
        if not cand["confirmed"]:
            blockers.append("Higher timeframe opposes")
            
        hard, soft = _side_filters(name, cand, ctx)
        blockers.extend(hard)

        if soft:
            cand["score"] -= config.SOFT_FILTER_PENALTY * len(soft)
            cand["reasons"].extend(soft)
            
        if len(soft) > config.MAX_SOFT_FILTER_FAILS:
            blockers.append(f"Too many weak signals ({len(soft)})")
            
        if regime == "HIGH_VOL" and name != "dip_buyer" and cand["score"] < config.HIGH_VOL_MIN_SCORE:
            blockers.append(f"HIGH_VOL needs score {config.HIGH_VOL_MIN_SCORE}+ (got {cand['score']})")

        if name == "dip_buyer" and cand["score"] < config.COUNTER_TREND_MIN_SCORE:
            blockers.append(f"Dip needs score {config.COUNTER_TREND_MIN_SCORE}+ (got {cand['score']})")

        confirmed = not blockers
        shown = blockers + [x for x in soft if x not in blockers]
        
        tech = {"score": cand["score"], "side": cand["side"], "reasons": cand["reasons"]}
        if blockers:
            tech["blocked_reason"] = " | ".join(blockers)
            
        res = evaluate_setup(tech, ctx["source"], confirmed, ctx.get("news_risk", 0.0))
        results.append((cand, res))

    entries = [(c, r) for c, r in results if r["action"] != "HOLD"]
    if entries:
        cand, res = max(entries, key=lambda x: x[0]["score"])
        return _decision(regime, cand, res)
    if results:
        cand, res = max(results, key=lambda x: x[0]["score"])
        return _decision(regime, cand, res)
        
    hint = " (needs squeeze breakout, strong trend, or RSI<=32 dip)" if regime == "HIGH_VOL" else ""
    return {"regime": regime, "strategy": None, "score": 0, "action": "HOLD", "reason": f"[{regime}] No setup{hint}", "stop_mult": config.ATR_STOP_MULTIPLIER, "rr": config.REWARD_RISK_RATIO}
