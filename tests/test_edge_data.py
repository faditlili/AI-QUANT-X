import _env  # noqa: F401
import asyncio
import glob
import io
import json
import os
import re
import tempfile
import unittest
import zipfile

from edge import flags, historical, liquidations, orderflow
from edge.client import EdgeDataClient, EdgeDataError
from edge.collector import collect_once
from edge.context import edge_snapshot
from edge.store import EdgeStore, make_row

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H, M5 = 3_600_000, 300_000


class Fake:
    """Fake fetch(path, params): routes path -> value or callable(params); records every call."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def __call__(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        r = self.routes[path]
        r = r(params) if callable(r) else r
        if isinstance(r, Exception):
            raise r
        return r


def run(coro):
    return asyncio.run(coro)


def tmp_store():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(path)
    return EdgeStore(path)


class Flags(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(v) for k, v in flags._ENV.items()}
        for v in flags._ENV.values():
            os.environ.pop(v, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(flags._ENV[k], None)
            else:
                os.environ[flags._ENV[k]] = v

    def test_everything_off_by_default(self):
        self.assertFalse(any(flags.snapshot().values()))

    def test_dependencies(self):
        os.environ["FF_ORDER_FLOW"] = "true"
        self.assertFalse(flags.enabled("ORDER_FLOW"))          # needs ADVANCED_DATA
        os.environ["FF_ADVANCED_DATA"] = "true"
        self.assertTrue(flags.enabled("ORDER_FLOW"))
        os.environ["FF_META_LABELING"] = "1"
        self.assertFalse(flags.enabled("META_LABELING"))        # needs LIGHTGBM

    def test_unknown_flag_raises(self):
        with self.assertRaises(KeyError):
            flags.enabled("ORDERFLOW")


class Client(unittest.TestCase):
    def test_oi_hist_sorted_and_typed(self):
        rows = [{"timestamp": 2000, "sumOpenInterest": "5", "sumOpenInterestValue": "50"},
                {"timestamp": 1000, "sumOpenInterest": "4", "sumOpenInterestValue": "40"}]
        c = EdgeDataClient(Fake({"/futures/data/openInterestHist": rows}))
        out = run(c.open_interest_hist("btcusdt", "5m", 10))
        self.assertEqual([r["ts"] for r in out], [1000, 2000])
        self.assertEqual(out[1]["oi"], 5.0)

    def test_nan_and_garbage_rejected_not_defaulted(self):
        bad = [{"timestamp": 1000, "sumOpenInterest": "nan", "sumOpenInterestValue": "1"}]
        c = EdgeDataClient(Fake({"/futures/data/openInterestHist": bad, "/fapi/v1/openInterest": {"openInterest": "x", "time": 1}}))
        with self.assertRaises(EdgeDataError):
            run(c.open_interest_hist("BTCUSDT"))
        with self.assertRaises(EdgeDataError):
            run(c.open_interest_now("BTCUSDT"))

    def test_non_list_payload_rejected(self):
        c = EdgeDataClient(Fake({"/futures/data/takerlongshortRatio": {"code": -1121}}))
        with self.assertRaises(EdgeDataError):
            run(c.taker_ratio("BTCUSDT"))

    def test_input_validation(self):
        c = EdgeDataClient(Fake({}))
        for coro in (c.open_interest_now("../etc"), c.open_interest_hist("BTCUSDT", "7m"),
                     c.long_short_ratio("BTCUSDT", "bogus")):
            with self.assertRaises(ValueError):
                run(coro)

    def test_premium_index(self):
        d = {"markPrice": "101", "indexPrice": "100", "lastFundingRate": "0.0001", "nextFundingTime": 9, "time": 5}
        p = run(EdgeDataClient(Fake({"/fapi/v1/premiumIndex": d})).premium_index("BTCUSDT"))
        self.assertAlmostEqual(p["premium_pct"], 1.0)

    def test_agg_trades_paginates_with_fromid_and_dedupes(self):
        start, end = 10_000, 20_000
        page1 = [{"a": i, "p": "100", "q": "1", "T": start + i, "m": False} for i in range(1, 1001)]
        page2 = [{"a": i, "p": "100", "q": "1", "T": start + i, "m": True} for i in range(1000, 1004)]   # 1000 repeats
        fake = Fake({"/fapi/v1/aggTrades": lambda p: page1 if "startTime" in p else page2})
        res = run(EdgeDataClient(fake).agg_trades("BTCUSDT", start, end))
        self.assertTrue(res["complete"])
        self.assertEqual(len(res["trades"]), 1003)
        self.assertEqual(fake.calls[1][1].get("fromId"), 1001)
        self.assertNotIn("startTime", fake.calls[1][1])        # Binance rejects fromId + startTime together

    def test_agg_trades_reports_incomplete_when_page_cap_hit(self):
        page = lambda p: [{"a": p.get("fromId", 0) + i, "p": "1", "q": "1", "T": 10_000 + i, "m": False} for i in range(1000)]
        res = run(EdgeDataClient(Fake({"/fapi/v1/aggTrades": page})).agg_trades("BTCUSDT", 10_000, 99_999, max_pages=2))
        self.assertFalse(res["complete"])

    def test_agg_trades_filters_outside_window(self):
        page = [{"a": 1, "p": "1", "q": "1", "T": 5, "m": False}, {"a": 2, "p": "1", "q": "1", "T": 15, "m": False}]
        res = run(EdgeDataClient(Fake({"/fapi/v1/aggTrades": page})).agg_trades("BTCUSDT", 10, 20))
        self.assertEqual([t["id"] for t in res["trades"]], [2])


class OrderFlow(unittest.TestCase):
    def test_cvd_sign_convention(self):
        trades = [{"id": 1, "ts": 0, "qty": 3.0, "buyer_is_maker": False},     # taker bought
                  {"id": 2, "ts": 10, "qty": 1.0, "buyer_is_maker": True},      # taker sold
                  {"id": 2, "ts": 10, "qty": 1.0, "buyer_is_maker": True}]      # duplicate id ignored
        b = orderflow.cvd_bars(trades, 1000)[0]
        self.assertEqual((b["buy"], b["sell"], b["delta"], b["trades"]), (3.0, 1.0, 2.0, 2))

    def test_open_bucket_is_not_returned(self):
        trades = [{"id": 1, "ts": 100, "qty": 1.0, "buyer_is_maker": False},
                  {"id": 2, "ts": 1100, "qty": 1.0, "buyer_is_maker": False}]
        bars = orderflow.cvd_bars(trades, 1000)
        self.assertEqual(len(orderflow.closed_bars(bars, 1500)), 1)           # second bucket ends at 2000
        self.assertEqual(len(orderflow.closed_bars(bars, 2000)), 2)

    def test_cumulative(self):
        bars = [{"delta": 2.0}, {"delta": -5.0}, {"delta": 1.0}]
        self.assertEqual(orderflow.cumulative(bars), [2.0, -3.0, -2.0])

    def test_taker_imbalance(self):
        self.assertAlmostEqual(orderflow.taker_imbalance(3, 1), 0.5)
        self.assertIsNone(orderflow.taker_imbalance(0, 0))

    def test_oi_change_needs_history(self):
        s = [{"oi": 100.0}, {"oi": 110.0}, {"oi": 121.0}]
        self.assertAlmostEqual(orderflow.oi_change_pct(s, 2), 21.0)
        self.assertIsNone(orderflow.oi_change_pct(s, 3))

    def test_quadrants(self):
        q = orderflow.oi_price_quadrant
        self.assertEqual(q(1.0, 2.0), "LONG_BUILDUP")
        self.assertEqual(q(1.0, -2.0), "SHORT_COVERING")
        self.assertEqual(q(-1.0, 2.0), "SHORT_BUILDUP")
        self.assertEqual(q(-1.0, -2.0), "LONG_LIQUIDATION")
        self.assertEqual(q(0.01, 2.0), "NEUTRAL")
        self.assertIsNone(q(None, 2.0))


class Store(unittest.TestCase):
    def test_insert_is_idempotent(self):
        st = tmp_store()
        rows = [make_row("oi_hist", "BTCUSDT", 1000, {"oi": 1.0}, "5m", M5)]
        self.assertEqual(st.insert_rows(rows), 1)
        self.assertEqual(st.insert_rows(rows), 0)
        self.assertEqual(st.count(), 1)

    def test_as_of_hides_future_availability(self):
        st = tmp_store()
        st.insert_rows([make_row("oi_hist", "BTCUSDT", 1000, {"oi": 1.0}, "5m", M5),
                        make_row("oi_hist", "BTCUSDT", 1000 + M5, {"oi": 2.0}, "5m", M5)])
        seen = st.fetch("oi_hist", "BTCUSDT", "5m", as_of_ms=1000 + M5 + 1)
        self.assertEqual([r["oi"] for r in seen], [1.0])       # second bar only known at 1000+2*M5
        self.assertEqual(len(st.fetch("oi_hist", "BTCUSDT", "5m", as_of_ms=1000 + 2 * M5)), 2)

    def test_limit_keeps_newest_oldest_first(self):
        st = tmp_store()
        st.insert_rows([make_row("k", "S", t, {"v": t}) for t in (1, 2, 3, 4)])
        self.assertEqual([r["v"] for r in st.fetch("k", "S", limit=2)], [3, 4])

    def test_live_vs_backfill_availability(self):
        backfill = make_row("oi_hist", "S", 1000, {}, "5m", M5)
        live = make_row("oi_hist", "S", 1000, {}, "5m", M5, fetched_at=10 * M5)
        self.assertEqual(backfill["available_at"], 1000 + M5)
        self.assertEqual(live["available_at"], 10 * M5)        # we could not know it before we asked

    def test_separate_file_from_trading_db(self):
        import config
        self.assertNotEqual(os.path.basename(tmp_store().path), os.path.basename(config.DB_PATH))


class Liquidations(unittest.TestCase):
    def msg(self, side="SELL", **o):
        base = {"s": "BTCUSDT", "S": side, "p": "100", "ap": "99", "q": "2", "z": "2", "T": 1700000000000}
        base.update(o)
        return {"e": "forceOrder", "E": 1, "o": base}

    def test_sell_means_long_liquidated(self):
        e = liquidations.parse_force_order(self.msg("SELL"))
        self.assertEqual((e["liquidated"], e["notional"]), ("LONG", 198.0))
        self.assertEqual(liquidations.parse_force_order(self.msg("BUY"))["liquidated"], "SHORT")

    def test_accepts_wrapped_and_json_string(self):
        self.assertIsNotNone(liquidations.parse_force_order(json.dumps({"stream": "x", "data": self.msg()})))

    def test_garbage_is_none(self):
        for bad in (None, "not json", {"e": "trade"}, self.msg(q="0", z="0"), self.msg(side="HOLD"), self.msg(T="x")):
            self.assertIsNone(liquidations.parse_force_order(bad))

    def test_summarize_window(self):
        ev = [liquidations.parse_force_order(self.msg("SELL", T=1000)), liquidations.parse_force_order(self.msg("BUY", T=2000)),
              liquidations.parse_force_order(self.msg("SELL", T=9000))]
        s = liquidations.summarize(ev, 500, 2500)
        self.assertEqual((s["events"], s["long_notional"], s["short_notional"]), (2, 198.0, 198.0))

    def test_stream_reconnects_and_stops(self):
        got, stop_holder = [], {}
        class WS:
            def __init__(self, msgs, then_fail): self.msgs, self.fail = msgs, then_fail
            def __aiter__(self): return self._gen()
            async def _gen(self):
                for m in self.msgs: yield m
                if self.fail: raise RuntimeError("drop")
        class Ctx:
            def __init__(self, ws): self.ws = ws
            async def __aenter__(self): return self.ws
            async def __aexit__(self, *a): return False
        plan = [WS([json.dumps(self.msg(T=1)), "garbage", json.dumps(self.msg(T=2))], True), WS([json.dumps(self.msg(T=3))], False)]
        conns = []
        def connect(url):
            conns.append(url); return Ctx(plan[len(conns) - 1])
        async def sleep(_): pass
        async def go():
            stop = asyncio.Event()
            def on_event(e):
                got.append(e["ts"])
                if len(got) == 3: stop.set()
            await liquidations.run_stream(on_event, connect=connect, stop=stop, sleep=sleep)
        run(go())
        self.assertEqual(got, [1, 2, 3])
        self.assertEqual(len(conns), 2)


class Historical(unittest.TestCase):
    METRICS = ("create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,"
               "sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
               "2024-05-01 00:05:00,BTCUSDT,100.5,6000000,1.2,1.3,1.1,0.9\n"
               "2024-05-01 00:10:00,BTCUSDT,101.5,6100000,,,1.0,\n")

    def test_metrics_rows_and_availability(self):
        rows = historical.parse_metrics(self.METRICS, "BTCUSDT")
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds.count("oi_hist"), 2)
        self.assertEqual(kinds.count("ls_top_account"), 1)          # blank cells are skipped, not zero-filled
        first = rows[0]
        self.assertEqual(first["available_at"], first["ts"] + M5)
        self.assertEqual(first["ts"], 1714521900000)

    def test_funding(self):
        rows = historical.parse_funding("calc_time,funding_interval_hours,last_funding_rate\n1714521600000,8,0.0001\n", "BTCUSDT")
        self.assertEqual(rows[0]["payload"]["funding"], 0.0001)

    def test_agg_trades_with_and_without_header(self):
        body = "1,100.0,2.0,1,1,1714521600000,true\n2,101.0,1.0,2,2,1714521600500,false\n"
        hdr = "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        for text in (body, hdr + body):
            t = historical.parse_agg_trades(text)
            self.assertEqual([(x["id"], x["buyer_is_maker"]) for x in t], [(1, True), (2, False)])

    def test_bad_agg_row_raises(self):
        with self.assertRaises(ValueError):
            historical.parse_agg_trades("1,100.0,2.0\n")

    def test_zip_and_urls(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("x.csv", "a,b\n1,2\n")
        self.assertIn("a,b", historical.read_zip_csv(buf.getvalue()))
        self.assertTrue(historical.url_for("metrics", "BTCUSDT", day="2024-05-01").endswith("/daily/metrics/BTCUSDT/BTCUSDT-metrics-2024-05-01.zip"))
        with self.assertRaises(ValueError):
            historical.url_for("metrics", "BTCUSDT")


def full_routes(now):
    t0 = (now // M5) * M5
    def agg(p):
        return [{"a": 1, "p": "100", "q": "3", "T": t0 - M5 + 10, "m": False},
                {"a": 2, "p": "100", "q": "1", "T": t0 - M5 + 20, "m": True}]
    hist = lambda key, extra: [{"timestamp": t0 - (12 - i) * M5, **extra(i)} for i in range(12)]
    return {
        "/fapi/v1/premiumIndex": {"markPrice": "101", "indexPrice": "100", "lastFundingRate": "0.0001", "nextFundingTime": now + H, "time": now - 1000},
        "/fapi/v1/openInterest": {"openInterest": "150", "time": now - 1000},
        "/futures/data/openInterestHist": hist("oi", lambda i: {"sumOpenInterest": str(100 + 5 * i), "sumOpenInterestValue": "1"}),
        "/futures/data/globalLongShortAccountRatio": hist("ls", lambda i: {"longShortRatio": "1.5", "longAccount": "0.6", "shortAccount": "0.4"}),
        "/futures/data/topLongShortAccountRatio": hist("ls", lambda i: {"longShortRatio": "1.2", "longAccount": "0.55", "shortAccount": "0.45"}),
        "/futures/data/topLongShortPositionRatio": hist("ls", lambda i: {"longShortRatio": "1.1", "longAccount": "0.52", "shortAccount": "0.48"}),
        "/futures/data/takerlongshortRatio": hist("tk", lambda i: {"buySellRatio": "1.2", "buyVol": "60", "sellVol": "40"}),
        "/fapi/v1/aggTrades": agg,
    }


class CollectorAndContext(unittest.TestCase):
    NOW = 1_700_000_000_000 + 123_456

    def test_collect_then_snapshot_point_in_time(self):
        st = tmp_store()
        res = run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))
        self.assertEqual(res["errors"], [])
        self.assertGreater(res["inserted"], 40)
        self.assertEqual(run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))["inserted"], 0)   # idempotent
        snap = edge_snapshot(st, "BTCUSDT", self.NOW, oi_bars_back=6, price_change_pct=1.0)
        self.assertEqual(snap["missing"], [])
        self.assertEqual(snap["stale"], [])
        self.assertAlmostEqual(snap["premium_pct"], 1.0)
        self.assertAlmostEqual(snap["taker_imbalance"], 0.2)
        self.assertEqual(snap["oi_price_quadrant"], "LONG_BUILDUP")
        self.assertGreater(snap["oi_change_pct"], 0)

    def test_not_enough_oi_history_gives_none_not_a_guess(self):
        st = tmp_store()
        run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))
        snap = edge_snapshot(st, "BTCUSDT", self.NOW, oi_bars_back=12, price_change_pct=1.0)   # only 12 bars stored
        self.assertIsNone(snap["oi_change_pct"])
        self.assertIsNone(snap["oi_price_quadrant"])

    def test_snapshot_before_data_was_fetched_sees_nothing(self):
        st = tmp_store()
        run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))
        early = edge_snapshot(st, "BTCUSDT", self.NOW - 10 * H)           # a decision made 10h BEFORE we collected
        for key in ("oi_latest", "mark_price", "funding", "cvd_sum", "long_short_ratio", "taker_imbalance"):
            self.assertIsNone(early[key], key)
        self.assertIn("oi", early["missing"])

    def test_cvd_value_and_only_closed_bucket(self):
        st = tmp_store()
        run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))
        bars = st.fetch("cvd", "BTCUSDT", "5m")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["delta"], 2.0)
        self.assertLessEqual(bars[0]["ts"] + M5, (self.NOW // M5) * M5)   # bucket had ended

    def test_one_failing_endpoint_does_not_stop_others(self):
        routes = full_routes(self.NOW)
        routes["/futures/data/takerlongshortRatio"] = RuntimeError("boom")
        st = tmp_store()
        res = run(collect_once(EdgeDataClient(Fake(routes)), st, ["BTCUSDT"], now_ms=self.NOW))
        self.assertEqual([e[1] for e in res["errors"]], ["taker"])
        self.assertGreater(st.count("oi_hist"), 0)
        self.assertEqual(st.count("taker"), 0)

    def test_incomplete_trade_window_stores_no_partial_cvd(self):
        routes = full_routes(self.NOW)
        routes["/fapi/v1/aggTrades"] = lambda p: [{"a": p.get("fromId", 0) + i, "p": "1", "q": "1", "T": self.NOW - M5, "m": False} for i in range(1000)]
        st = tmp_store()
        res = run(collect_once(EdgeDataClient(Fake(routes)), st, ["BTCUSDT"], now_ms=self.NOW))
        self.assertEqual(res["incomplete_cvd"], ["BTCUSDT"])
        self.assertEqual(st.count("cvd"), 0)

    def test_stale_data_is_flagged(self):
        st = tmp_store()
        run(collect_once(EdgeDataClient(Fake(full_routes(self.NOW))), st, ["BTCUSDT"], now_ms=self.NOW))
        snap = edge_snapshot(st, "BTCUSDT", self.NOW + 5 * H)
        self.assertIn("premium", snap["stale"])


class Isolation(unittest.TestCase):
    def test_legacy_core_never_imports_edge(self):
        for f in glob.glob(os.path.join(ROOT, "*.py")):
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
            self.assertIsNone(re.search(r"^\s*(from|import)\s+edge\b", src, re.M), os.path.basename(f))

    def test_edge_has_no_trading_or_account_access(self):
        banned = ("signature", "X-MBX-APIKEY", "apiKey", "api_key", "secret", "/fapi/v1/order", "/api/v3/order",
                  "/fapi/v2/account", "/fapi/v1/listenKey", "import database", "from database")
        for f in glob.glob(os.path.join(ROOT, "edge", "*.py")):
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
            for word in banned:
                self.assertNotIn(word.lower(), src.lower(), "%s contains %r" % (os.path.basename(f), word))

    def test_edge_only_uses_public_endpoints(self):
        with open(os.path.join(ROOT, "edge", "client.py"), encoding="utf-8") as fh:
            src = fh.read()
        paths = set(re.findall(r'"(/(?:fapi|futures)/[A-Za-z0-9/_]+)"', src))
        self.assertTrue(paths and all(("/fapi/v1/" in p or "/futures/data/" in p) for p in paths), paths)


if __name__ == "__main__":
    unittest.main()
