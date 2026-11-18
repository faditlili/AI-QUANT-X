import asyncio
import os
import tempfile
import unittest

import numpy as np

import _env  # noqa: F401
import config
import ml_filter
import optimizer
import order_book
import sentiment_engine
import symbol_scanner
from indicators import compute_frame, snapshot
from test_indicators_backtest import make_df
from test_market_data import FakeResp, FakeSession


def run(c):
    return asyncio.run(c)


class MLFilter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old = (config.ML_MODEL_PATH, ml_filter._path_cache["path"])
        config.ML_MODEL_PATH = os.path.join(self.tmp, "model.pkl")
        ml_filter._path_cache["path"] = None
        ml_filter._cache.update({"mtime": None, "bundle": None})
        self.addCleanup(self._restore)

    def _restore(self):
        config.ML_MODEL_PATH, ml_filter._path_cache["path"] = self._old
        ml_filter._cache.update({"mtime": None, "bundle": None})

    def test_no_model_means_no_opinion(self):
        self.assertIsNone(ml_filter.get_ml_probability(snapshot(compute_frame(make_df(200)))))
        self.assertIsNone(ml_filter.model_age_seconds())

    def test_pure_noise_is_not_declared_a_valid_edge(self):
        valid = 0
        for seed in range(4):
            frames = [compute_frame(make_df(1500, seed=100 + seed * 7 + k, vol=0.01)) for k in range(3)]
            res = ml_filter.train_model(frames)
            self.assertIsNotNone(res)
            valid += bool(res["valid"])
        self.assertLessEqual(valid, 1, "noise must essentially never pass the out-of-sample edge test")

    def test_invalid_model_returns_none_even_though_file_exists(self):
        res = ml_filter.train_model([compute_frame(make_df(1500, seed=9, vol=0.01))])
        if res and not res["valid"]:
            self.assertIsNone(ml_filter.get_ml_probability(snapshot(compute_frame(make_df(200, seed=3)))))

    def test_holdout_is_later_in_time_than_training(self):
        rec = {}
        real = ml_filter._build_model

        class Spy:
            def __init__(self):
                self.m = real()

            def fit(self, X, y):
                rec.setdefault("fits", []).append(X.index)
                self.m.fit(X, y)
                return self

            def score(self, X, y):
                rec["test"] = X.index
                return self.m.score(X, y)

            def __getattr__(self, n):
                return getattr(self.m, n)
        ml_filter._build_model = Spy
        real_dump = ml_filter.joblib.dump
        ml_filter.joblib.dump = lambda *a, **k: None      # the spy is not picklable; persistence is tested elsewhere
        try:
            res = ml_filter.train_model([compute_frame(make_df(1000, seed=4, vol=0.01))])
        finally:
            ml_filter._build_model = real
            ml_filter.joblib.dump = real_dump
        self.assertIsNotNone(res)
        train_idx, test_idx = rec["fits"][0], rec["test"]
        # embargo: the label of the last training row (horizon bars ahead) must not reach into the hold-out
        self.assertLess(train_idx.max() + config.ML_HORIZON_CANDLES, test_idx.min())
        self.assertEqual(len(set(train_idx) & set(test_idx)), 0)

    def test_too_little_data_returns_none(self):
        self.assertIsNone(ml_filter.train_model([compute_frame(make_df(120))]))
        self.assertIsNone(ml_filter.train_model([]))

    def test_features_are_scale_free(self):
        a = ml_filter.feature_frame(compute_frame(make_df(300, seed=1, start=100)))
        b = ml_filter.feature_frame(compute_frame(make_df(300, seed=1, start=100000)))
        np.testing.assert_allclose(a.iloc[-1].values, b.iloc[-1].values, rtol=1e-6, atol=1e-9)

    def test_missing_snapshot_fields_give_none(self):
        self.assertIsNone(ml_filter.get_ml_probability({"price": 1.0}))
        self.assertIsNone(ml_filter.get_ml_probability(None))


class OrderBook(unittest.TestCase):
    class M:
        def __init__(self, book): self.book = book
        async def get_depth(self, symbol, source, limit):
            if isinstance(self.book, Exception): raise self.book
            return self.book

    def test_none_not_neutral_when_unavailable(self):
        for book in (RuntimeError("x"), {}, {"bids": [], "asks": []}, {"bids": [["10", "1"]], "asks": [["9", "1"]]},
                     {"bids": [["0", "0"]], "asks": [["0", "0"]]}):
            self.assertIsNone(run(order_book.get_order_book_imbalance("BTCUSDT", self.M(book))), book)

    def test_labels(self):
        book = {"bids": [["99.9", "9"]], "asks": [["100.1", "1"]]}
        r = run(order_book.get_order_book_imbalance("BTCUSDT", self.M(book)))
        self.assertEqual(r["support_strength"], "STRONG")
        self.assertEqual(r["resistance_strength"], "WEAK")

    def test_uses_requested_market(self):
        seen = []

        class M2(self.M):
            async def get_depth(self, symbol, source, limit):
                seen.append(source)
                return {"bids": [["1", "1"]], "asks": [["1.001", "1"]]}
        run(order_book.get_order_book_imbalance("BTCUSDT", M2(None), "spot"))
        self.assertEqual(seen, ["spot"])


class Sentiment(unittest.TestCase):
    def test_unavailable_is_none_not_neutral(self):
        sentiment_engine._cache.update({"time": None, "result": None})
        old = sentiment_engine._get_analyzer
        sentiment_engine._get_analyzer = lambda: None
        try:
            self.assertIsNone(run(sentiment_engine.get_market_sentiment()))
        finally:
            sentiment_engine._get_analyzer = old

    def test_analyze_scores_headlines(self):
        class A:
            def polarity_scores(self, t): return {"compound": 0.5 if "up" in t else -0.5}
        r = sentiment_engine._analyze(A(), ["prices up", "market up", "crash"])
        self.assertEqual(r["state"], "BULLISH")
        self.assertEqual(len(r["top_news"]), 3)
        self.assertIsNone(sentiment_engine._analyze(A(), []))


class Scanner(unittest.TestCase):
    def test_failure_returns_none_so_the_watchlist_is_kept(self):
        import aiohttp

        class S:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            def get(self, *a, **k): return FakeResp(500, "x")
        old = aiohttp.ClientSession
        aiohttp.ClientSession = S
        try:
            self.assertIsNone(run(symbol_scanner.get_top_symbols()))
        finally:
            aiohttp.ClientSession = old


class Optimizer(unittest.TestCase):
    def test_sweep_uses_held_out_validation_and_never_mutates_global_params(self):
        before = (config.RSI_PERIOD, config.EMA_FAST, config.STRATEGIES)
        df = make_df(1000, seed=21, vol=0.01)
        cut = int(len(df) * 0.7)
        res = optimizer._sweep(df.iloc[:cut].reset_index(drop=True), df.iloc[cut:].reset_index(drop=True))
        self.assertIn("stats", res)
        self.assertEqual(before, (config.RSI_PERIOD, config.EMA_FAST, config.STRATEGIES))   # thread-local overrides only
        if res["params"]:                                                                    # accepted only if OOS held
            self.assertGreaterEqual(res["test"]["trades"], config.AUTOTUNE_TEST_MIN_TRADES)
            self.assertGreater(res["test"]["return_pct"], 0)

    def test_noise_rarely_passes_validation(self):
        accepted = 0
        for seed in (31, 32, 33):
            df = make_df(1000, seed=seed, vol=0.01)
            cut = int(len(df) * 0.7)
            accepted += bool(optimizer._sweep(df.iloc[:cut].reset_index(drop=True),
                                              df.iloc[cut:].reset_index(drop=True))["params"])
        self.assertLessEqual(accepted, 1)


if __name__ == "__main__":
    unittest.main()
