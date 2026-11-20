"""Regression tests for the defects found in the v7.2.0 audit. Each test fails on the unpatched code.

1. correlation filter asked for 50 candles, MarketData.get_klines() demands >= 60  -> every entry blocked
   as soon as one position was open.
2. monitor_positions() ran network-bound checks BEFORE evaluating stops.
3. a failed news-feed refresh was never cached -> 2 HTTP round-trips for EVERY symbol of every scan.
4. the price WebSocket pointed at legacy Binance futures URLs, retired on 2026-04-23.
"""
import asyncio
import json
import time
import unittest
from unittest import mock

import numpy as np

import _env  # noqa: F401
import config
import engine as engine_mod
import sentiment_engine as S
import websocket_streamer
from correlation import is_highly_correlated
from engine import Engine
from helpers import make_db, open_pos
from market_data import MarketData
from test_engine_integration import FakeMarket


def run(coro):
    return asyncio.run(coro)


def _klines(limit, seed):
    """Closed hourly candles in Binance's 12-field row format, oldest first (independent random walk per seed)."""
    rng = np.random.RandomState(seed)
    price, now, hour, rows = 100.0, int(time.time() * 1000), 3_600_000, []
    for i in range(limit):
        open_t = now - (limit - i + 1) * hour
        nxt = price * (1 + rng.normal(0, 0.01))
        hi, lo = max(price, nxt) * 1.002, min(price, nxt) * 0.998
        rows.append([open_t, str(price), str(hi), str(lo), str(nxt), "1000", open_t + hour - 1,
                     "100000", 10, "500", "50000", "0"])
        price = nxt
    return rows


class CorrelationUsesARealisticCandleRequest(unittest.TestCase):
    def test_entry_is_not_blocked_by_missing_data_when_a_position_is_open(self):
        requested = []

        async def go():
            md = MarketData()

            async def fake_get(source, path, params=None):
                requested.append(int(params["limit"]))
                return _klines(int(params["limit"]), seed=sum(map(ord, params["symbol"])))   # Binance honours `limit`

            md._get = fake_get
            return await is_highly_correlated("SOLUSDT", ["BTCUSDT"], md, threshold=0.99, source="futures")

        blocked, why = run(go())
        self.assertFalse(blocked, why)
        self.assertTrue(requested and min(requested) >= config.MIN_CANDLES_REQUIRED,
                        "get_klines rejects fewer than MIN_CANDLES_REQUIRED candles: %s" % requested)

    def test_correlation_window_is_still_50_candles(self):
        async def go():
            md = MarketData()

            async def fake_get(source, path, params=None):
                return _klines(int(params["limit"]), seed=7)       # same seed -> identical series

            md._get = fake_get
            return await is_highly_correlated("AUSDT", ["BUSDT"], md, threshold=0.8, source="futures")

        blocked, why = run(go())
        self.assertTrue(blocked)
        self.assertIn("Highly correlated", why)                    # a real correlation verdict, not a data error


class StopsAreEvaluatedBeforeSlowNetworkChecks(unittest.TestCase):
    def setUp(self):
        websocket_streamer.live_prices.clear()

    def _engine_with_losing_position(self, market):
        db = make_db(1000)
        eng = Engine(db, market)
        pos = open_pos(eng.trader, "SOLUSDT", price=100.0, atr=1.0, side="LONG")["position"]
        market.price = pos["stop_price"] * 0.97                    # crash through the stop
        return db, eng, pos

    def test_slow_klines_do_not_delay_the_stop(self):
        class Slow(FakeMarket):
            async def get_klines(self, *a, **k):
                await asyncio.sleep(2.0)
                return self.df.copy()

        db, eng, pos = self._engine_with_losing_position(Slow())
        t0 = time.monotonic()
        run(eng.monitor_positions())
        self.assertLess(time.monotonic() - t0, 1.0, "the stop must not wait for the slow whale check")
        self.assertEqual(db.get_position(pos["id"])["exit_reason"], "STOP_LOSS")

    def test_hanging_auxiliary_check_is_bounded_and_stops_still_work(self):
        db, eng, pos = self._engine_with_losing_position(FakeMarket())

        async def hang():
            await asyncio.sleep(3600)

        eng.check_whale_emergency_exit = hang
        with mock.patch.object(engine_mod, "AUX_CHECK_TIMEOUT_SECONDS", 0.2):
            t0 = time.monotonic()
            run(eng.monitor_positions())
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(db.get_position(pos["id"])["status"], "CLOSED")


class FailedSentimentRefreshIsCached(unittest.TestCase):
    def setUp(self):
        self._saved = dict(S._cache)
        S._cache.update({"time": None, "result": None, "retry_at": 0.0})
        self.fetches = 0

    def tearDown(self):
        S._cache.clear()
        S._cache.update(self._saved)

    def _run(self, headlines, calls):
        class FakeSession:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class Analyzer:
            def polarity_scores(self, text): return {"compound": 0.5}

        async def fake_fetch(session, url):
            self.fetches += 1
            return list(headlines)

        async def go():
            out = None
            for _ in range(calls):
                out = await S.get_market_sentiment()
            return out

        with mock.patch.object(S.aiohttp, "ClientSession", FakeSession), \
                mock.patch.object(S, "_fetch_headlines", fake_fetch), \
                mock.patch.object(S, "_get_analyzer", lambda: Analyzer()):
            return run(go())

    def test_feeds_down_means_one_refresh_attempt_per_scan_not_per_symbol(self):
        result = self._run([], calls=50)                           # 50 symbols analysed, feeds empty/down
        self.assertIsNone(result)
        self.assertEqual(self.fetches, len(S.RSS_FEEDS), "one attempt over all feeds, not one per symbol")

    def test_retry_resumes_after_the_failure_window(self):
        self._run([], calls=3)
        S._cache["retry_at"] = 0.0                                 # window elapsed
        result = self._run(["bitcoin rallies"], calls=1)
        self.assertIsNotNone(result)
        self.assertEqual(S._cache["retry_at"], 0.0)


class PriceStreamUsesTheCurrentBinanceEndpoint(unittest.TestCase):
    def test_default_url_is_not_a_retired_legacy_path(self):
        self.assertNotIn("fstream.binance.com/ws/", config.WS_URL)
        self.assertIn("fstream.binance.com/market/ws/", config.WS_URL)

    def test_legacy_url_from_an_old_env_variable_is_rewritten(self):
        self.assertEqual(config._ws_url("wss://fstream.binance.com/ws/!ticker@arr"),
                         "wss://fstream.binance.com/market/ws/!ticker@arr")
        self.assertEqual(config._ws_url("wss://example.org/ws/x"), "wss://example.org/ws/x")

    def test_mini_ticker_payload_feeds_live_prices(self):
        websocket_streamer.live_prices.clear()
        msg = json.dumps([{"e": "24hrMiniTicker", "E": 1, "s": "BTCUSDT", "c": "64000.5", "o": "63000",
                           "h": "65000", "l": "62000", "v": "10", "q": "640000"}])
        run(websocket_streamer._handle_message(msg, None))
        self.assertEqual(websocket_streamer.get_live_price("BTCUSDT"), 64000.5)


class FundingNeverOverdrawsCash(unittest.TestCase):
    def test_fully_allocated_account_pays_funding_from_position_margin(self):
        from helpers import make_trader, check_integrity
        db, tr = make_trader(200)
        pos = open_pos(tr, "SOLUSDT", price=100.0, atr=1.0, side="SHORT")["position"]
        db.set_state("cash_balance", "0.01")                       # fully allocated: almost no free cash
        eq_before = db.get_portfolio()["equity"]
        db.apply_funding(pos["id"], 0.5, "test")
        port = db.get_portfolio()
        self.assertGreaterEqual(port["cash_balance"], -1e-9)
        self.assertAlmostEqual(port["equity"], eq_before - 0.5, 7)  # the funding is still fully charged

    def test_seeds_that_used_to_overdraw_now_pass_every_invariant(self):
        from test_financial_invariants import Invariants
        sim = Invariants("test_random_runs_1x")
        for seed in (328, 300, 301, 305, 310, 315, 320):
            sim.run_sim(seed, steps=300)


if __name__ == "__main__":
    unittest.main()
