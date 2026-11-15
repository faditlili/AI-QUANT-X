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


class Brain:
    def __init__(self, db):
        self.db = db

    def _closed(self, limit):
        return [t for t in self.db.get_recent_trades(limit) if t["status"] == "CLOSED" and t["net_pnl"] is not None]

    def get_dynamic_risk(self):
        """Half-Kelly risk per trade, used only once there is a meaningful sample."""
        trades = self._closed(200)[:100]
        if len(trades) < config.BRAIN_MIN_TRADES:
            return config.RISK_PER_TRADE_PCT

        wins = sum(1 for t in trades if float(t["net_pnl"]) > 0)
        losses = len(trades) - wins
        win_rate = wins / len(trades)

        gross_win = sum(float(t["net_pnl"]) for t in trades if float(t["net_pnl"]) > 0)
        gross_loss = abs(sum(float(t["net_pnl"]) for t in trades if float(t["net_pnl"]) < 0))

        avg_win = gross_win / wins if wins > 0 else 0
        avg_loss = gross_loss / losses if losses > 0 else 0

        if avg_loss == 0 or avg_win == 0 or win_rate == 0:
            return 0.5

        payoff_ratio = avg_win / avg_loss
        kelly = win_rate - ((1 - win_rate) / payoff_ratio)
        half_kelly = kelly / 2
        # Never above the configured per-trade risk and never below 0.5 percent.
        return max(0.5, min(half_kelly * 100, 3.5, config.RISK_PER_TRADE_PCT * 1.75))

    def is_strategy_healthy(self, strategy_name, metadata=None):
        """Kill-switch: a strategy with N losses in a row is paused for STRATEGY_PAUSE_SECONDS, then retried."""
        strat_trades = []
        for t in self._closed(100):
            try:
                meta = json.loads(t["metadata"] or "{}") if isinstance(t["metadata"], str) else t["metadata"]
            except Exception:
                continue
            if (meta or {}).get("strategy") == strategy_name:
                strat_trades.append(t)

        need = config.MAX_CONSECUTIVE_LOSSES
        if len(strat_trades) < need:
            return True

        strat_trades.sort(key=lambda t: t["closed_at"] or "", reverse=True)
        last = strat_trades[:need]
        if not all(float(t["net_pnl"]) < 0 for t in last):
            return True

        closed_at = _parse_time(last[0]["closed_at"])
        if closed_at is None:
            return True
        now = datetime.now(timezone.utc).timestamp()
        return (now - closed_at) >= config.STRATEGY_PAUSE_SECONDS
