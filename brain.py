"""Adaptive risk: half-Kelly sizing and per-strategy kill-switch (pure functions + DB adapter)."""
import json
from datetime import datetime, timezone

import config


def _parse_time(value):
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp()
    except Exception:
        return None


def kelly_risk_pct(net_pnls):
    """Half-Kelly risk per trade in percent, from the most recent net P&L values (newest first).

    Used by BOTH the live risk manager and the backtester. Returns the configured fixed risk until
    there is a meaningful sample. Never above RISK_PER_TRADE_PCT*1.75 / 3.5 and never below 0.5.
    Break-even trades are neither wins nor losses.
    """
    vals = [float(x) for x in net_pnls][:100]
    if len(vals) < config.BRAIN_MIN_TRADES:
        return config.RISK_PER_TRADE_PCT
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    if not wins or not losses:
        return 0.5 if not wins else min(config.RISK_PER_TRADE_PCT, 3.5)
    win_rate = len(wins) / len(vals)
    payoff = (sum(wins) / len(wins)) / (abs(sum(losses)) / len(losses))
    kelly = win_rate - (1 - win_rate) / payoff
    return max(0.5, min(kelly / 2 * 100, 3.5, config.RISK_PER_TRADE_PCT * 1.75))


def strategy_healthy(trades, strategy_name, now=None):
    """trades: closed trade dicts with net_pnl, closed_at (ISO) and strategy/metadata."""
    mine = []
    for t in trades:
        name = t.get("strategy")
        if not name:
            meta = t.get("metadata")
            try:
                meta = json.loads(meta or "{}") if isinstance(meta, str) else (meta or {})
            except Exception:
                meta = {}
            name = meta.get("strategy")
        if name == strategy_name:
            mine.append(t)
    need = config.MAX_CONSECUTIVE_LOSSES
    if len(mine) < need:
        return True
    mine.sort(key=lambda t: t["closed_at"] or "", reverse=True)
    last = mine[:need]
    if not all(float(t["net_pnl"]) < 0 for t in last):
        return True
    closed_at = _parse_time(last[0]["closed_at"])
    if closed_at is None:
        return True
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    return (now - closed_at) >= config.STRATEGY_PAUSE_SECONDS


class Brain:
    def __init__(self, db):
        self.db = db

    def _closed(self, limit):
        return [t for t in self.db.get_closed_trades(limit) if t["net_pnl"] is not None]

    def get_dynamic_risk(self):
        return kelly_risk_pct([t["net_pnl"] for t in self._closed(100)])

    def is_strategy_healthy(self, strategy_name, metadata=None):
        return strategy_healthy(self._closed(200), strategy_name)
