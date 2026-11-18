import asyncio
import time
import unittest

import numpy as np
import pandas as pd

import _env  # noqa: F401
import config
import engine as engine_mod
import strategies
import websocket_streamer
from engine import Engine
from helpers import make_db, check_integrity, RULES
from test_indicators_backtest import make_df

SIGNAL = {"action": "PAPER_BUY", "side": "LONG", "score": 80, "reason": "unit-test signal", "regime": "TREND",
          "strategy": "trend", "stop_mult": 2.0, "rr": 2.0}


def run(coro):
    return asyncio.run(coro)


class FakeMarket:
    def __init__(self, price=None, age=1.0):
        self.df = make_df(220, seed=2, vol=0.004)
        self.price = float(self.df.close.iloc[-1]) if price is None else price
        self.age, self.rules, self.funding = age, dict(RULES), 0.0001
        self.klines_error = None
        self.funding_events = []
        self.price_error = False
        self.session = None

    async def start(self): pass
    async def close(self): pass

    def get_status(self):
        return {"connected": True, "last_success_age_s": self.age}

    async def get_klines(self, symbol, interval="1h", limit=None, source="futures"):
        if self.klines_error:
            raise RuntimeError(self.klines_error)
        return self.df.copy()

    async def get_last_prices(self, source="futures"):
        if self.price_error:
            raise RuntimeError("no prices")
        return {s: {"last_price": self.price} for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")}

    async def get_tickers_24h(self, source="futures"):
        return {s: {"last_price": self.price, "quote_volume": 1e9, "change_percent": 1.0}
                for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")}

    async def get_symbol_rules(self, symbol, source):
        if self.rules is None:
            raise RuntimeError("no exchange info")
        return self.rules

    async def get_funding_rate(self, symbol, source="futures"):
        return self.funding

    async def get_funding_history(self, symbol, start_ms=None, limit=100):
        return [e for e in self.funding_events if e["fundingTime"] >= (start_ms or 0)]

    async def get_depth(self, symbol, source="futures", limit=50):
        raise RuntimeError("no depth")

    async def get_fear_and_greed(self): return None
    async def get_market_breadth(self, source="futures"): return None
    async def liquid_symbols(self, source="futures"): return ["SOLUSDT", "XRPUSDT"]


class Notifier:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    async def _rec(self, name, *a):
        self.calls.append((name, a))
        if self.fail:
            raise RuntimeError("telegram down")

    async def notify_trade_opened(self, p): await self._rec("opened", p)
    async def notify_trade_closed(self, p): await self._rec("closed", p)
    async def notify_event(self, e): await self._rec("event", e)
    async def send(self, m): await self._rec("send", m)


class EngineBase(unittest.TestCase):
    def setUp(self):
        self.db = make_db(1000)
        self.market = FakeMarket()
        self.eng = Engine(self.db, self.market)
        self.eng.notifier = Notifier()
        self.captured = {}
        self._patch("select_signal", self._signal)
        self._patch("get_market_sentiment", self._sentiment)
        self.sig = dict(SIGNAL)
        websocket_streamer.live_prices.clear()
        self.macro = {"compass": "NEUTRAL", "fng": None, "breadth": None}

    def _patch(self, name, value):
        old = getattr(engine_mod, name)
        setattr(engine_mod, name, value)
        self.addCleanup(lambda: setattr(engine_mod, name, old))

    def _signal(self, ctx, enabled=None):
        self.captured["ctx"] = ctx
        return dict(self.sig)

    async def _sentiment(self):
        return None

    def analyze(self, symbol="SOLUSDT", source="futures"):
        run(self.eng._analyze(symbol, source, self.macro))


class OpenPath(EngineBase):
    def test_signal_opens_a_persisted_position_with_notification(self):
        self.analyze()
        pos = self.db.get_open_positions()
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos[0]["symbol"], "SOLUSDT")
        self.assertEqual(pos[0]["strategy"], "trend")
        self.assertEqual([c[0] for c in self.eng.notifier.calls], ["opened"])
        self.assertLessEqual(self.db.get_portfolio()["open_risk"], 1000 * 0.10 + 1e-9)
        check_integrity(self, self.db)

    def test_context_carries_unknowns_as_none_not_fake_neutrals(self):
        self.analyze()
        ctx = self.captured["ctx"]
        self.assertIsNone(ctx["fear_greed"])
        self.assertIsNone(ctx["breadth"])
        self.assertIsNone(ctx["order_book"])
        self.assertIsNone(ctx["sentiment"])
        self.assertEqual(ctx["funding_rate"], 0.0001)

    def test_missing_funding_is_passed_as_none_for_futures_and_absent_for_spot(self):
        self.market.funding = None
        self.analyze(source="futures")
        self.assertIsNone(self.captured["ctx"]["funding_rate"])
        self.analyze("XRPUSDT", "spot")
        self.assertNotIn("funding_rate", self.captured["ctx"])

    def test_strategy_filter_blocks_futures_entry_without_funding(self):
        cand = {"side": "LONG", "strategy": "trend", "score": 80, "reasons": [], "confirmed": True}
        ctx = {"primary": {"price": 100.0, "vwap24": 99.0, "taker_buy_ratio": 0.5}, "source": "futures",
               "funding_rate": None, "symbol": "SOLUSDT", "compass": "NEUTRAL"}
        hard, _ = strategies._side_filters("trend", cand, ctx)
        self.assertTrue(any("unavailable" in h.lower() for h in hard), hard)
        ctx["funding_rate"] = 0.0001
        hard, _ = strategies._side_filters("trend", cand, ctx)
        self.assertFalse(any("unavailable" in h.lower() for h in hard))

    def test_no_entry_on_market_data_outage(self):
        self.market.age = 10_000
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("outage", self.db.get_recent_decisions(1)[0]["reason"].lower())

    def test_no_entry_without_live_price(self):
        self.market.price_error = True
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("live price", self.db.get_recent_decisions(1)[0]["reason"].lower())

    def test_stale_setup_skipped(self):
        self.market.price = float(self.market.df.close.iloc[-1]) * 3
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("Stale", self.db.get_recent_decisions(1)[0]["reason"])

    def test_stale_websocket_price_is_not_used(self):
        websocket_streamer.live_prices["SOLUSDT"] = (1.0, time.monotonic() - 3600)
        self.assertIsNone(websocket_streamer.get_live_price("SOLUSDT"))
        self.analyze()
        self.assertEqual(len(self.db.get_open_positions()), 1)           # fell back to REST, not price 1.0
        self.assertGreater(self.db.get_open_positions()[0]["entry_price"], 10)

    def test_exchange_rules_unavailable_blocks_entry(self):
        self.market.rules = None
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("rules", self.db.get_recent_decisions(1)[0]["reason"].lower())

    def test_candle_fetch_failure_means_no_trade_and_error_propagates(self):
        self.market.klines_error = "HTTP 500"
        with self.assertRaises(RuntimeError):
            self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])

    def test_notifier_failure_cannot_break_trading(self):
        self.eng.notifier = Notifier(fail=True)
        self.analyze()
        self.assertEqual(len(self.db.get_open_positions()), 1)

    def test_paused_engine_never_opens(self):
        self.eng.set_paused(True)
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertEqual(self.db.get_state("paused"), "1")
        self.assertTrue(Engine(self.db, self.market).paused)             # survives restart

    def test_hold_signal_records_decision_only(self):
        self.sig = {"action": "HOLD", "score": 10, "reason": "no setup", "regime": "RANGE", "strategy": None,
                    "stop_mult": 2, "rr": 2}
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertEqual(self.db.get_recent_decisions(1)[0]["action"], "HOLD")

    def test_cooldown_and_pair_lock(self):
        self.analyze()
        pid = self.db.get_open_positions()[0]["id"]
        self.eng.trader.close_position(pid, self.market.price, "MANUAL")
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])               # cooldown
        self.db.set_state("cooldown:futures:SOLUSDT", 0)
        self.db.set_state("lock:SOLUSDT", time.time() + 600)
        self.analyze()
        self.assertEqual(self.db.get_open_positions(), [])               # pair lock after stop-loss

    def test_correlation_check_fails_closed(self):
        self.analyze("SOLUSDT")
        self.market.klines_error = None
        orig = self.market.get_klines

        async def flaky(symbol, *a, **k):
            if symbol == "XRPUSDT" and a[0] == "1h" and a[1] == 50:
                raise RuntimeError("boom")
            return await orig(symbol, *a, **k)
        self.market.get_klines = flaky
        self.analyze("XRPUSDT")
        self.assertEqual(len(self.db.get_open_positions()), 1)
        self.assertIn("Correlation", self.db.get_recent_decisions(1)[0]["reason"])

    def test_highly_correlated_symbol_blocked(self):
        self.analyze("SOLUSDT")
        self.analyze("XRPUSDT")                                          # identical fake series -> corr ~ 1
        self.assertEqual(len(self.db.get_open_positions()), 1)

    def test_same_symbol_not_opened_twice(self):
        self.analyze()
        self.db.set_state("cooldown:futures:SOLUSDT", 0)
        self.analyze()
        self.assertEqual(len(self.db.get_open_positions()), 1)


class MonitorPath(EngineBase):
    def open(self):
        self.analyze()
        return self.db.get_open_positions()[0]

    def test_stop_loss_closes_and_notifies(self):
        p = self.open()
        self.market.price = p["stop_price"] - 0.5
        run(self.eng.monitor_positions())
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("closed", [c[0] for c in self.eng.notifier.calls])
        check_integrity(self, self.db)

    def test_scale_out_event_is_notified(self):
        p = self.open()
        self.market.price = p["entry_price"] + abs(p["entry_price"] - p["initial_stop"]) * 1.2
        run(self.eng.monitor_positions())
        kinds = [(c[0], c[1][0]["type"]) for c in self.eng.notifier.calls if c[0] == "event"]
        self.assertEqual(kinds, [("event", "SCALE_OUT")])

    def test_monitor_survives_total_price_outage_and_alerts_once(self):
        self.open()
        self.market.price_error = True
        old = config.DATA_STALE_SECONDS
        config.DATA_STALE_SECONDS = 0
        try:
            run(self.eng.monitor_positions())
            time.sleep(0.01)
            run(self.eng.monitor_positions())
            run(self.eng.monitor_positions())
        finally:
            config.DATA_STALE_SECONDS = old
        sends = [c for c in self.eng.notifier.calls if c[0] == "send"]
        self.assertEqual(len(sends), 1)
        self.assertEqual(len(self.db.get_open_positions()), 1)           # nothing closed blindly

    def test_funding_settled_for_open_futures_positions_only(self):
        p = self.open()
        opened_ms = int(time.time() * 1000)
        self.market.funding_events = [{"fundingTime": opened_ms + 60_000, "fundingRate": 0.0005}]
        self.eng.last_funding_check = 0
        run(self.eng.settle_funding())
        row = self.db.get_position(p["id"])
        self.assertGreater(row["funding_paid"], 0)                       # LONG pays positive funding
        self.eng.last_funding_check = 0
        run(self.eng.settle_funding())
        self.assertAlmostEqual(self.db.get_position(p["id"])["funding_paid"], row["funding_paid"])   # not twice
        check_integrity(self, self.db)

    def test_restart_with_open_positions_resumes_monitoring(self):
        p = self.open()
        eng2 = Engine(self.db, self.market)
        eng2.notifier = Notifier()
        self.market.price = p["target_price"] + 1
        run(eng2.monitor_positions())
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertEqual(self.db.get_closed_trades()[0]["exit_reason"], "TAKE_PROFIT")

    def test_scan_once_runs_both_markets_and_snapshots_equity(self):
        run(self.eng.scan_once())
        self.assertGreaterEqual(len(self.db.equity_history()), 1)
        self.assertIsNotNone(self.eng.last_scan)
        self.assertLessEqual(self.db.get_portfolio()["open_risk"], self.db.get_portfolio()["equity"] * 0.1 + 1e-9)


if __name__ == "__main__":
    unittest.main()
