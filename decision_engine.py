"""Conservative signal scoring for educational paper simulation."""
import config
from indicators import direction

def calculate_technical_score(indicators):
    d=direction(indicators)
    score=0
    reasons=[]
    if d=="BULLISH":
        score+=35; reasons.append("EMA trend and directional movement bullish")
    elif d=="BEARISH":
        score+=35; reasons.append("EMA trend and directional movement bearish")
    rsi=indicators["rsi"]
    if (d=="BULLISH" and 45<=rsi<=68) or (d=="BEARISH" and 32<=rsi<=55):
        score+=15; reasons.append("RSI in a non-extreme zone")
    if indicators["adx"]>=20:
        score+=15; reasons.append("ADX trend-strength filter passed")
    if indicators["volume_ratio"]>=1:
        score+=10; reasons.append("Volume at/above average")
    return {"score":score,"side":("LONG" if d=="BULLISH" else "SHORT" if d=="BEARISH" else "NONE"),
            "direction":d,"reasons":reasons}

def evaluate_setup(technical,source="futures",timeframe_confirmed=False,news_risk=0.0):
    action="HOLD"
    reason="; ".join(technical.get("reasons",[])) or "No confirmed setup"
    if source not in ("spot","futures"):
        return {"action":"HOLD","reason":"Invalid source"}
    side=technical.get("side")
    if side=="SHORT" and source=="spot":
        return {"action":"HOLD","reason":"Spot simulation does not open short positions"}
    if side not in ("LONG","SHORT"):
        return {"action":"HOLD","reason":reason or "No direction"}
    score=technical.get("score",0)
    if score<config.MIN_SIGNAL_SCORE:
        return {"action":"HOLD","reason":"Score %s below %s: %s" % (score,config.MIN_SIGNAL_SCORE,reason)}
    if not timeframe_confirmed or news_risk>=config.MAX_NEWS_RISK:
        blockers=list(technical.get("blockers") or [])
        if news_risk>=config.MAX_NEWS_RISK:
            blockers.append("News risk %.2f" % news_risk)
        why="; ".join(blockers) or "Timeframe confirmation failed"
        return {"action":"HOLD","reason":"Blocked: "+why}
    return {"action":"PAPER_BUY" if side=="LONG" else "PAPER_SHORT","side":side,"reason":reason}
