import asyncio
import time
import unittest

import _env  # noqa: F401
import aiohttp
import config
import market_data
from market_data import MarketData, MarketDataError


class FakeResp:
    def __init__(self, status=200, body=None, headers=None):
        self.status, self._body, self.headers = status, body, headers or {}

    async def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    async def text(self):
        return str(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class FakeSession:
    closed = False

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self):
        self.closed = True


def md(script):
    m = MarketData()
    m.session = FakeSession(script)
    return m


def run(coro):
    return asyncio.run(coro)


def kline(i, closed=True, base=100.0):
    open_t = 1_700_000_000_000 + i * 3_600_000
    close_t = open_t + 3_599_999
    if not closed:
        close_t = int(time.time() * 1000) + 600_000
    return [open_t, str(base), str(base + 1), str(base - 1), str(base + 0.5), "10.0", close_t, "1000.0", 5, "5.0", "500.0", "0"]


class Retry(unittest.TestCase):
    def setUp(self):
        self._sleep = asyncio.sleep
        market_data.asyncio.sleep = self._fast_sleep
        self.addCleanup(lambda: setattr(market_data.asyncio, "sleep", self._sleep))

    async def _fast_sleep(self, *_):
        return None

    def test_http_500_is_retried_then_succeeds(self):
        m = md([FakeResp(500, "x"), FakeResp(200, {"ok": 1})])
        self.assertEqual(run(m._get("futures", "/x")), {"ok": 1})
        self.assertEqual(len(m.session.calls), 2)

    def test_persistent_500_raises_after_bounded_attempts(self):
        m = md([FakeResp(503, "down")])
        with self.assertRaises(MarketDataError):
            run(m._get("futures", "/x"))
        self.assertLessEqual(len(m.session.calls), config.HTTP_RETRY_ATTEMPTS + 1)

    def test_client_error_and_timeout_become_marketdataerror(self):
        for exc in (aiohttp.ClientError("boom"), asyncio.TimeoutError()):
            m = md([exc])
            with self.assertRaises(MarketDataError):
                run(m._get("spot", "/x"))

    def test_4xx_not_retried(self):
        m = md([FakeResp(400, "bad symbol")])
        with self.assertRaises(MarketDataError):
            run(m._get("spot", "/x"))
        self.assertEqual(len(m.session.calls), 1)

    def test_rate_limit_triggers_cooldown_and_blocks_further_calls(self):
        m = md([FakeResp(429, "slow", {"Retry-After": "30"}), FakeResp(200, {})])
        with self.assertRaises(MarketDataError):
            run(m._get("spot", "/x"))
        calls = len(m.session.calls)
        with self.assertRaises(MarketDataError) as cm:
            run(m._get("spot", "/x"))
        self.assertIn("cooldown", str(cm.exception))
        self.assertEqual(len(m.session.calls), calls)                 # no hammering while banned

    def test_invalid_json_is_an_error_not_empty_data(self):
        m = md([FakeResp(200, ValueError("not json"))])
        with self.assertRaises(MarketDataError):
            run(m._get("spot", "/x"))

    def test_success_updates_freshness(self):
        m = md([FakeResp(200, {})])
        self.assertIsNone(m.get_status()["last_success_age_s"])
        run(m._get("spot", "/x"))
        self.assertLess(m.get_status()["last_success_age_s"], 5)


class Endpoints(unittest.TestCase):
    def test_spot_and_futures_use_their_own_hosts_and_paths(self):
        m = MarketData()
        self.assertTrue(m._base("spot").startswith("https://api.binance.com"))
        self.assertTrue(m._base("futures").startswith("https://fapi.binance.com"))
        self.assertEqual(m._path("spot", "klines"), "/api/v3/klines")
        self.assertEqual(m._path("futures", "klines"), "/fapi/v1/klines")
        self.assertEqual(m._path("spot", "depth"), "/api/v3/depth")
        self.assertEqual(m._path("futures", "depth"), "/fapi/v1/depth")
        with self.assertRaises(ValueError):
            m._base("margin")

    def test_no_trading_or_account_endpoints_anywhere(self):
        import pathlib, re
        bad = re.compile(r"/(api/v3/order|fapi/v1/order|sapi/|api/v3/account|fapi/v2/account|withdraw|listenKey)")
        for f in pathlib.Path(_env.ROOT).glob("*.py"):
            self.assertIsNone(bad.search(f.read_text()), f.name)

    def test_symbol_and_interval_validation(self):
        m = md([FakeResp(200, [])])
        for bad in ("BTC/USDT", "btc usdt", "", "A" * 40, "BTCUSDT&limit=1"):
            with self.assertRaises(Exception):
                run(m.get_klines(bad, "1h"))
        with self.assertRaises(ValueError):
            run(m.get_klines("BTCUSDT", "7m"))
        self.assertEqual(m.session.calls, [])

    def test_klines_drop_forming_candle_and_enforce_minimum(self):
        raw = [kline(i) for i in range(70)] + [kline(70, closed=False)]
        m = md([FakeResp(200, raw)])
        df = run(m.get_klines("BTCUSDT", "1h", 200, "futures"))
        self.assertEqual(len(df), 70)
        self.assertTrue((df.close_time < time.time() * 1000).all())
        m = md([FakeResp(200, [kline(i) for i in range(10)])])
        with self.assertRaises(MarketDataError):
            run(m.get_klines("BTCUSDT", "1h"))

    def test_malformed_kline_row_raises(self):
        raw = [kline(i) for i in range(70)]
        raw[5] = [1, 2, 3]
        with self.assertRaises(MarketDataError):
            MarketData.parse_klines(raw)

    def test_kline_cache_prevents_duplicate_requests(self):
        m = md([FakeResp(200, [kline(i) for i in range(70)])])
        run(m.get_klines("BTCUSDT", "1h", 200))
        run(m.get_klines("BTCUSDT", "1h", 200))
        self.assertEqual(len(m.session.calls), 1)
        run(m.get_klines("BTCUSDT", "4h", 200))
        self.assertEqual(len(m.session.calls), 2)

    def test_funding_rate_none_on_failure_and_zero_is_real_zero(self):
        m = md([FakeResp(500, "x")])
        self.assertIsNone(run(m.get_funding_rate("BTCUSDT")))
        m = md([FakeResp(200, {"lastFundingRate": "0.00000000"})])
        self.assertEqual(run(m.get_funding_rate("BTCUSDT")), 0.0)          # real zero stays zero
        m = md([FakeResp(200, {})])
        self.assertIsNone(run(m.get_funding_rate("BTCUSDT")))              # missing != zero
        self.assertIsNone(run(m.get_funding_rate("BTCUSDT", "spot")))      # spot has no funding

    def test_funding_history_sorted_and_malformed_rows_skipped(self):
        m = md([FakeResp(200, [{"fundingTime": 3, "fundingRate": "0.0002"}, {"fundingTime": 1, "fundingRate": "0.0001"},
                               {"oops": 1}])])
        ev = run(m.get_funding_history("BTCUSDT", 0))
        self.assertEqual([e["fundingTime"] for e in ev], [1, 3])

    def test_last_prices_filter_invalid(self):
        m = md([FakeResp(200, [{"symbol": "A", "price": "1.5"}, {"symbol": "B", "price": "0"}, {"symbol": "C", "price": "x"}])])
        self.assertEqual(run(m.get_last_prices("spot")), {"A": {"last_price": 1.5}})
        m = md([FakeResp(200, [{"symbol": "B", "price": "0"}])])
        with self.assertRaises(MarketDataError):
            run(m.get_last_prices("spot"))

    def test_tickers_cached_and_invalid_dropped(self):
        body = [{"symbol": "AUSDT", "lastPrice": "2", "quoteVolume": "9e6", "priceChangePercent": "1"},
                {"symbol": "BUSDT", "lastPrice": "0", "quoteVolume": "9e6", "priceChangePercent": "1"},
                {"symbol": "CUSDT", "lastPrice": "nan?", "quoteVolume": "1", "priceChangePercent": "1"}]
        m = md([FakeResp(200, body)])
        t = run(m.get_tickers_24h("futures"))
        self.assertEqual(list(t), ["AUSDT"])
        run(m.get_tickers_24h("futures"))
        self.assertEqual(len(m.session.calls), 1)

    def test_breadth_none_when_unavailable(self):
        m = md([FakeResp(500, "x")])
        self.assertIsNone(run(m.get_market_breadth("futures")))

    def test_fear_greed_none_not_fifty_on_failure(self):
        m = md([FakeResp(500, "x")])
        self.assertIsNone(run(m.get_fear_and_greed()))

    def test_symbol_rules_parser(self):
        item = {"symbol": "BTCUSDT", "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.10"}, {"filterType": "MIN_NOTIONAL", "notional": "100"}]}
        self.assertEqual(MarketData.parse_symbol_rules(item),
                         {"step": 0.001, "min_qty": 0.001, "min_notional": 100.0, "tick": 0.1})
        self.assertIsNone(MarketData.parse_symbol_rules({"filters": []}))
        self.assertIsNone(MarketData.parse_symbol_rules({"filters": [{"filterType": "LOT_SIZE", "stepSize": "bad", "minQty": "1"}]}))

    def test_eligible_symbols_filters_by_market(self):
        info = {"symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING", "contractType": "PERPETUAL"},
            {"symbol": "BTCUSDT_250627", "status": "TRADING", "contractType": "CURRENT_QUARTER"},
            {"symbol": "ETHUPUSDT", "status": "TRADING"},
            {"symbol": "XUSDT", "status": "BREAK"},
            {"symbol": "ETHBTC", "status": "TRADING"}]}
        m = md([FakeResp(200, info)])
        self.assertEqual(run(m.eligible_symbols("futures")), ["BTCUSDT"])


if __name__ == "__main__":
    unittest.main()
