"""Virtual fills only. Scale-out, trailing stops, liquidation and funding for the paper portfolio."""
import json
import logging
import time

import accounting
import config
from trade_management import next_stop, breakeven_stop

log = logging.getLogger(__name__)


def _meta(pos):
    raw = pos.get("metadata")
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


def _iso_ms(iso):
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(iso)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp() * 1000)
    except (TypeError, ValueError):
        return None


class PaperTrader:
    def __init__(self, database, risk_manager=None):
        from risk_manager import RiskManager
        self.db = database
        self.risk = risk_manager or RiskManager(database)
        self.events = []   # partial closes / liquidations, drained by the engine for notifications

    def drain_events(self):
        out, self.events = self.events, []
        return out

    # ------------------------------------------------------------------ open
    def open_position(self, symbol, price, atr, side="LONG", source="futures", metadata=None,
                      stop_mult=None, rr=None, strategy=None, rules=None):
        try:
            price, atr = float(price), float(atr)
        except (TypeError, ValueError):
            return {"success": False, "reason": "Invalid price or ATR"}
        # The lock makes size -> validate -> reserve one unit; the DB re-validates inside its own
        # BEGIN IMMEDIATE transaction, so even a second connection/process cannot overshoot the limits.
        with self.db.lock:
            sized, reason = self.risk.calculate_position_size(symbol, source, side, price, atr, stop_mult, rr,
                                                              strategy or "trend", rules)
            if not sized:
                return {"success": False, "reason": reason}
            meta = {**(metadata or {}), "strategy": strategy}
            if rules:
                meta["rules"] = {k: rules.get(k) for k in ("step", "min_qty", "min_notional", "tick")}
            data = {"symbol": symbol, "source": source, "side": side, "quantity": sized["quantity"],
                    "entry_price": sized["entry_price"], "stop_price": sized["stop_price"],
                    "target_price": sized["target_price"], "margin_used": sized["margin_used"],
                    "risk_amount": sized["risk_amount"], "initial_risk": sized["initial_risk"],
                    "opening_fee": sized["opening_fee"], "initial_stop": sized["stop_price"],
                    "strategy": strategy, "metadata": meta, "leverage": sized["leverage"],
                    "liquidation_price": sized["liquidation_price"]}
            try:
                return {"success": True, "position": self.db.create_position(data)}
            except ValueError as exc:
                return {"success": False, "reason": str(exc)}

    # ------------------------------------------------------------------ close
    def close_position(self, pid, price, reason="MANUAL", raw_exit=False):
        """Close at `price` (+ adverse slippage unless raw_exit, used for liquidation fills)."""
        pos = self.db.get_position(pid)
        if not pos or pos["status"] != "OPEN":
            return None
        price = float(price)
        if not accounting.is_valid_price(price):
            log.warning("Refusing to close %s at invalid price %r", pid, price)
            return None
        exit_price = price if raw_exit else accounting.exit_fill(price, pos["side"])
        fee = exit_price * pos["quantity"] * config.fee_rate(pos["source"])
        row = self.db.close_position(pid, exit_price, reason, fee)
        lock_min = getattr(config, "PAIR_LOCK_AFTER_STOPLOSS_MIN", 0)
        if row and reason == "STOP_LOSS" and lock_min > 0:
            self.db.set_state(f"lock:{pos['symbol']}", time.time() + lock_min * 60)
        return row

    # ------------------------------------------------------------------ monitoring
    def _scale_out(self, pos, price):
        sign = accounting.side_sign(pos["side"])
        unit_r = abs(pos["entry_price"] - (pos["initial_stop"] or pos["stop_price"]))
        if unit_r <= 0 or (price - pos["entry_price"]) * sign / unit_r < config.SCALE_OUT_R:
            return pos
        qty = pos["quantity"] * config.SCALE_OUT_PCT
        rules = _meta(pos).get("rules") or {}
        qty = accounting.floor_to_step(qty, rules.get("step"))
        if qty <= 0 or qty >= pos["quantity"] or qty < (rules.get("min_qty") or 0):
            return pos
        if qty * price < max(config.MIN_NOTIONAL_USDT, rules.get("min_notional") or 0):
            return pos
        exit_price = accounting.exit_fill(price, pos["side"])
        fee = exit_price * qty * config.fee_rate(pos["source"])
        updated = self.db.partial_close(pos["id"], exit_price, qty, f"SCALE_OUT_{config.SCALE_OUT_R}R", fee)
        if not updated:
            return pos
        be = breakeven_stop(updated["side"], updated["entry_price"], config.fee_rate(updated["source"]))
        self.db.update_stop(updated["id"], be)
        updated = self.db.get_position(updated["id"])
        self.events.append({"type": "SCALE_OUT", "position": updated, "price": exit_price, "quantity": qty})
        return updated

    def update_market_prices(self, prices, source=None):
        closed = []
        for pos in self.db.get_open_positions():
            if source and pos["source"] != source:
                continue
            item = prices.get(pos["symbol"])
            if not item:
                continue
            try:
                price = float(item.get("last_price", 0))
            except (TypeError, ValueError):
                continue
            if not accounting.is_valid_price(price):
                continue
            self.db.mark_position(pos["id"], price)
            long_ = pos["side"] == "LONG"
            liq = pos.get("liquidation_price")
            initial = pos.get("initial_stop") or pos["stop_price"]
            moved = abs(pos["stop_price"] - initial) > 1e-12

            # 1) exits are evaluated against the stop that was in force BEFORE this tick
            if pos["source"] == "futures" and liq and ((long_ and price <= liq) or (not long_ and price >= liq)):
                row = self.close_position(pos["id"], liq, "LIQUIDATION", raw_exit=True)
                if row:
                    closed.append(row)
                continue
            hit = None
            if (long_ and price <= pos["stop_price"]) or (not long_ and price >= pos["stop_price"]):
                hit = "TRAILING_STOP" if moved else "STOP_LOSS"
            elif (long_ and price >= pos["target_price"]) or (not long_ and price <= pos["target_price"]):
                hit = "TAKE_PROFIT"
            if hit:
                row = self.close_position(pos["id"], price, hit)
                if row:
                    closed.append(row)
                continue

            # 2) partial profit, then ratchet the stop
            if config.SCALE_OUT_ENABLED and not pos.get("scale_out_done"):
                pos = self._scale_out(pos, price)
            new_stop = next_stop(pos["side"], pos["entry_price"], pos.get("initial_stop"), pos["stop_price"], price,
                                 fee=config.fee_rate(pos["source"]))
            if abs(new_stop - pos["stop_price"]) > 1e-12:
                self.db.update_stop(pos["id"], new_stop)
        return closed

    # ------------------------------------------------------------------ futures funding
    def apply_funding(self, pid, rate, funding_time_ms, mark_price=None):
        """Settle one funding event. Idempotent per (position, funding_time_ms)."""
        pos = self.db.get_position(pid)
        if not pos or pos["status"] != "OPEN" or pos["source"] != "futures" or not config.FUNDING_ENABLED:
            return None
        key = f"funding_last:{pid}"
        last = float(self.db.get_state(key, "0"))
        if funding_time_ms <= last:
            return None
        opened_ms = (_iso_ms(pos["opened_at"]) or 0)
        if funding_time_ms <= opened_ms:
            return None
        mark = float(mark_price or pos.get("mark_price") or pos["entry_price"])
        amount = accounting.funding_payment(pos["side"], pos["quantity"] * mark, float(rate))
        row = self.db.apply_funding(pid, amount, f"rate={rate} t={funding_time_ms}")
        self.db.set_state(key, funding_time_ms)
        return row

    def get_open_positions(self):
        return self.db.get_open_positions()
