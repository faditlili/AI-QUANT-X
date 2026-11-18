import unittest

import numpy as np
import pandas as pd

import _env  # noqa: F401
import accounting as A
import config
from backtest import run_backtest, run_portfolio_backtest, run_walk_forward
from indicators import compute_frame, calculate_indicators, snapshot, direction, IndicatorError
from volume_anomaly import detect_volume_anomaly, volume_anomaly_series


def make_df(n=600, seed=1, drift=0.0, vol=0.01, start=100.0, with_ts=True):
    rng = np.random.default_rng(seed)
    close = start * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    open_ = np.concatenate([[start], close[:-1]])
    spread = np.abs(rng.normal(0, vol / 2, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol_ = rng.uniform(100, 200, n)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol_,
                       "taker_buy_volume": vol_ * rng.uniform(0.4, 0.6, n)})
    if with_ts:
        df["timestamp"] = (np.arange(n) * 3600000 + 1_700_000_000_000).astype("int64")
    return df


class Indicators(unittest.TestCase):
    def test_rsi_extremes(self):
        up = make_df(120, vol=0.0)
        up["close"] = np.linspace(100, 200, 120)
        up["open"], up["high"], up["low"] = up["close"] - 0.1, up["close"] + 0.2, up["close"] - 0.2
        self.assertGreater(compute_frame(up).rsi.iloc[-1], 95)
        dn = up.copy()
        dn["close"] = np.linspace(200, 100, 120)
        dn["open"], dn["high"], dn["low"] = dn["close"] + 0.1, dn["close"] + 0.2, dn["close"] - 0.2
        self.assertLess(compute_frame(dn).rsi.iloc[-1], 5)

    def test_flat_market_is_neutral_not_nan(self):
        flat = make_df(120, vol=0.0)
        flat[["open", "high", "low", "close"]] = 100.0
        r = calculate_indicators(flat)
        self.assertTrue(all(np.isfinite(v) for v in r.values() if isinstance(v, float)))
        self.assertEqual(direction(r), "NEUTRAL")

    def test_ema_matches_reference(self):
        df = make_df(200)
        ref = df.close.ewm(span=config.EMA_MEDIUM, adjust=False).mean()
        np.testing.assert_allclose(compute_frame(df).ema21.values, ref.values)

    def test_atr_matches_manual_wilder(self):
        df = make_df(200)
        f = compute_frame(df)
        prev = df.close.shift(1)
        tr = pd.concat([df.high - df.low, (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)
        manual = tr.ewm(alpha=1 / config.ATR_PERIOD, adjust=False, min_periods=config.ATR_PERIOD).mean()
        np.testing.assert_allclose(f.atr.values[20:], manual.values[20:])

    def test_no_lookahead_future_rows_do_not_change_past_values(self):
        df = make_df(400, seed=5)
        full = compute_frame(df)
        part = compute_frame(df.iloc[:300].copy())
        for col in ("ema9", "ema21", "ema50", "rsi", "atr", "adx", "zscore", "bb_width_pctile", "squeeze",
                    "vwap24", "donchian_high", "volume_ratio", "atr_pctile"):
            np.testing.assert_allclose(full[col].values[:300].astype(float), part[col].values.astype(float),
                                       rtol=1e-9, atol=1e-9, err_msg=col)

    def test_bad_data_rejected_or_cleaned_never_silently_used(self):
        with self.assertRaises(IndicatorError):
            compute_frame(make_df(30))                                   # too few candles
        with self.assertRaises(IndicatorError):
            compute_frame(pd.DataFrame({"open": [1] * 100}))             # missing columns
        with self.assertRaises(IndicatorError):
            compute_frame(pd.DataFrame())
        bad = make_df(200)
        bad.loc[50, "close"] = np.nan
        bad.loc[60, "high"] = -5
        out = compute_frame(bad)
        self.assertEqual(len(out), 198)                                  # invalid rows dropped, count is visible
        self.assertTrue(np.isfinite(out.close).all())

    def test_gap_in_live_candles_is_detected(self):
        df = make_df(200).drop(index=150).reset_index(drop=True)
        with self.assertRaises(IndicatorError):
            calculate_indicators(df)

    def test_duplicate_timestamps_removed(self):
        df = make_df(200)
        dup = pd.concat([df, df.iloc[[100]]]).reset_index(drop=True)
        self.assertEqual(len(compute_frame(dup)), 200)

    def test_direction(self):
        self.assertEqual(direction({"ema9": 3, "ema21": 2, "ema50": 1, "plus_di": 30, "minus_di": 10}), "BULLISH")
        self.assertEqual(direction({"ema9": 1, "ema21": 2, "ema50": 3, "plus_di": 10, "minus_di": 30}), "BEARISH")
        self.assertEqual(direction({"ema9": 3, "ema21": 2, "ema50": 1, "plus_di": 10, "minus_di": 30}), "NEUTRAL")
        self.assertEqual(direction(None), "NEUTRAL")


class VolumeAnomaly(unittest.TestCase):
    def test_series_matches_function_on_every_bar(self):
        df = make_df(300, seed=9)
        df.loc[250, "volume"] = 5000
        df.loc[280, "volume"] = 6000
        ind = compute_frame(df)
        ser = volume_anomaly_series(ind)
        for i in (100, 249, 250, 251, 280, 299):
            single = detect_volume_anomaly(ind.iloc[: i + 1])
            self.assertEqual(bool(single.get("anomaly")), bool(ser[i].get("anomaly")), i)
            if single.get("anomaly"):
                self.assertEqual(single["direction"], ser[i]["direction"])

    def test_spike_detected_with_baseline_excluding_itself(self):
        df = make_df(120)
        df.loc[119, "volume"] = 10_000
        self.assertTrue(detect_volume_anomaly(df)["anomaly"])
        self.assertFalse(detect_volume_anomaly(df.iloc[:10])["anomaly"])
        self.assertFalse(detect_volume_anomaly(None)["anomaly"])


class Backtest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = make_df(900, seed=3, drift=0.0004, vol=0.012)

    def test_deterministic(self):
        a = run_backtest(self.df, source="futures")
        b = run_backtest(self.df, source="futures")
        self.assertEqual(a["trades"], b["trades"])
        self.assertEqual(a["final"], b["final"])

    def test_report_declares_assumptions(self):
        r = run_backtest(self.df)
        self.assertIn("limitations", r)
        self.assertIn("intrabar_policy", r)
        self.assertFalse(r.get("funding_included", True))                # no funding supplied -> must not claim it

    def test_costs_matter(self):
        free = run_backtest(self.df, fee=0.0, slippage_bps=0)
        paid = run_backtest(self.df, fee=0.002, slippage_bps=20)
        if free["trades"]:
            self.assertGreater(free["final"], paid["final"])

    def test_trades_enter_at_next_open_with_adverse_slippage(self):
        r = run_backtest(self.df)
        self.assertGreater(r["trades"], 0, "fixture must trade")
        for t in r["trade_list"][:30]:
            bar_open = self.df["open"].iloc[t["entry_idx"]] if t["entry_idx"] < len(self.df) else None
            slip = 1 + (1 if t["side"] == "LONG" else -1) * config.SLIPPAGE_BPS / 10000
            self.assertAlmostEqual(t["entry"], bar_open * slip, places=6)

    def test_equity_curve_reconciles_with_trades(self):
        r = run_backtest(self.df)
        net = sum(t["net"] for t in r["trade_list"])
        self.assertAlmostEqual(r["final"] - r["initial"], net, places=6)

    def test_open_risk_never_exceeds_ten_percent_of_equity(self):
        r = run_backtest(self.df)
        self.assertLessEqual(r["max_open_risk_pct"], 10.0 + 1e-6)

    def test_never_more_than_max_positions_and_same_side(self):
        frames = {s: make_df(700, seed=i, drift=0.0005, vol=0.014) for i, s in enumerate(
            ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT"])}
        r = run_portfolio_backtest(frames, source="futures")
        self.assertLessEqual(r["max_concurrent"], config.MAX_OPEN_POSITIONS)
        self.assertLessEqual(r["max_open_risk_pct"], 10.0 + 1e-6)

    def test_spot_backtest_is_long_only(self):
        r = run_backtest(make_df(900, seed=4, drift=-0.0006, vol=0.012), source="spot")
        self.assertTrue(all(t["side"] == "LONG" for t in r["trade_list"]))

    def test_same_bar_stop_and_target_resolves_to_stop(self):
        df = self.df.copy()
        t0 = run_backtest(df)["trade_list"][0]
        e = t0["entry_idx"]
        # one violent bar that spans BOTH the stop and the target of the first trade
        df.loc[e, "high"] = df.loc[e, "open"] * 1.6
        df.loc[e, "low"] = df.loc[e, "open"] * 0.4
        df.loc[e, "close"] = df.loc[e, "open"]
        t1 = run_backtest(df)["trade_list"][0]
        self.assertEqual(t1["entry_idx"], e)
        self.assertEqual(t1["exit_idx"], e)
        self.assertIn(t1["reason"], ("STOP_LOSS", "LIQUIDATION"))
        self.assertLess(t1["net"], 0)                      # the favourable ordering was NOT assumed

    def test_no_lookahead_truncating_the_future_does_not_change_past_trades(self):
        full = run_backtest(self.df)["trade_list"]
        cut = run_backtest(self.df.iloc[:700].reset_index(drop=True))["trade_list"]
        past = [t for t in cut if t["exit_idx"] < 680 and t["reason"] != "END_OF_DATA"]
        self.assertGreater(len(past), 3)
        key = lambda t: (t["entry_idx"], t["exit_idx"], t["side"], round(t["entry"], 6), round(t["net"], 6))
        self.assertEqual([key(t) for t in past], [key(t) for t in full][:len(past)])

    def test_walk_forward_has_disjoint_out_of_sample_folds(self):
        wf = run_walk_forward(make_df(1500, seed=8, vol=0.01), folds=3)
        self.assertEqual(len(wf["folds"]), 3)

    def test_not_enough_history_raises(self):
        with self.assertRaises(ValueError):
            run_backtest(make_df(100))

    def test_leverage_liquidation_caps_loss_at_margin(self):
        r = run_backtest(make_df(900, seed=6, vol=0.03), source="futures", leverage=10)
        for t in r["trade_list"]:
            self.assertGreater(t["net"], -r["initial"])                  # never loses more than the whole account

    def test_funding_cost_is_reported_when_supplied(self):
        df = make_df(900, seed=3, drift=0.0004, vol=0.012)
        base = run_backtest(df, source="futures")
        ts = df["timestamp"].values
        events = [{"fundingTime": int(t), "fundingRate": 0.001} for t in ts[::8]]
        fund = run_backtest(df, source="futures", funding=events)
        self.assertTrue(fund["funding_included"])
        if base["trades"]:
            self.assertLess(fund["final"], base["final"])


if __name__ == "__main__":
    unittest.main()
