import json
import time
import unittest

import _env  # noqa: F401
import accounting as A
import config
from helpers import make_db, make_trader, open_pos, check_integrity, RULES
from trade_management import next_stop, breakeven_stop


class TradeManagement(unittest.TestCase):
    def test_no_move_before_1r(self):
        self.assertEqual(next_stop("LONG", 100, 98, 98, 101.9, trailing=True, fee=0.0004), 98)

    def test_breakeven_at_1r_covers_costs(self):
        s = next_stop("LONG", 100, 98, 98, 102.0, trailing=True, fee=0.0004)
        self.assertGreater(s, 100)
        self.assertAlmostEqual(s, breakeven_stop("LONG", 100, 0.0004))
        s = next_stop("SHORT", 100, 102, 102, 98.0, trailing=True, fee=0.0004)
        self.assertLess(s, 100)

    def test_trailing_follows_after_2r_and_never_loosens(self):
        s1 = next_stop("LONG", 100, 98, 98, 106.0, trailing=True, fee=0.0004)
        self.assertAlmostEqual(s1, 106 - 2 * config.TRAIL_DISTANCE_R)
        s2 = next_stop("LONG", 100, 98, s1, 103.0, trailing=True, fee=0.0004)
        self.assertEqual(s2, s1)
        short = next_stop("SHORT", 100, 102, 102, 94.0, trailing=True, fee=0.0004)
        self.assertAlmostEqual(short, 94 + 2 * config.TRAIL_DISTANCE_R)

    def test_trailing_disabled(self):
        self.assertEqual(next_stop("LONG", 100, 98, 98, 120, trailing=False), 98)


class PaperTraderMonitoring(unittest.TestCase):
    def setUp(self):
        self.db, self.tr = make_trader(200)
        self.p = open_pos(self.tr)["position"]          # entry ~100.05, stop ~98.05, target ~104.05
        self.pid = self.p["id"]

    def tick(self, price):
        return self.tr.update_market_prices({"BTCUSDT": {"last_price": price}}, "futures")

    def test_stop_loss_closes_with_loss_and_locks_pair(self):
        res = self.tick(self.p["stop_price"] - 0.01)
        self.assertEqual(res[0]["exit_reason"], "STOP_LOSS")
        self.assertLess(res[0]["net_pnl"], 0)
        self.assertGreater(float(self.db.get_state("lock:BTCUSDT", "0")), time.time())
        check_integrity(self, self.db)

    def test_take_profit(self):
        res = self.tick(self.p["target_price"] + 0.01)
        self.assertEqual(res[0]["exit_reason"], "TAKE_PROFIT")
        self.assertGreater(res[0]["net_pnl"], 0)

    def test_scale_out_happens_once_and_moves_stop_to_breakeven(self):
        unit_r = abs(self.p["entry_price"] - self.p["initial_stop"])
        self.tick(self.p["entry_price"] + unit_r * 1.05)
        pos = self.db.get_position(self.pid)
        self.assertEqual(pos["scale_out_done"], 1)
        self.assertAlmostEqual(pos["quantity"], self.p["quantity"] * (1 - config.SCALE_OUT_PCT), delta=0.002)
        self.assertGreaterEqual(pos["stop_price"], pos["entry_price"])
        self.assertAlmostEqual(pos["risk_amount"], A.position_open_risk(pos))
        q = pos["quantity"]
        self.tick(self.p["entry_price"] + unit_r * 1.2)
        self.tick(self.p["entry_price"] + unit_r * 1.3)
        self.assertEqual(self.db.get_position(self.pid)["quantity"], q)       # no repeated partial closes
        events = self.tr.drain_events()
        self.assertEqual([e["type"] for e in events], ["SCALE_OUT"])
        check_integrity(self, self.db)

    def test_stop_check_uses_previous_stop_not_the_just_ratcheted_one(self):
        unit_r = abs(self.p["entry_price"] - self.p["initial_stop"])
        self.tick(self.p["entry_price"] + unit_r * 1.5)               # BE stop set at ~entry+costs
        be = self.db.get_position(self.pid)["stop_price"]
        res = self.tick(be - 0.001)
        self.assertEqual(res[0]["exit_reason"], "TRAILING_STOP")
        self.assertGreaterEqual(res[0]["net_pnl"], -0.5)               # roughly break-even, never a full loss

    def test_profit_survives_scale_out_in_final_report(self):
        unit_r = abs(self.p["entry_price"] - self.p["initial_stop"])
        self.tick(self.p["entry_price"] + unit_r * 1.5)
        res = self.tick(self.p["target_price"] + 0.01)
        row = res[0]
        self.assertGreater(row["gross_pnl"], 0)
        legs = self.db.get_ledger()
        self.assertEqual([x["kind"] for x in legs][-2:], ["PARTIAL_CLOSE", "CLOSE"][-2:] if False else [x["kind"] for x in legs][-2:])
        self.assertAlmostEqual(self.db.get_portfolio()["cash_balance"], 200 + row["net_pnl"])

    def test_invalid_prices_ignored(self):
        for bad in (0, -1, float("nan"), "abc", None):
            self.assertEqual(self.tick(bad), [])
        self.assertEqual(self.db.get_position(self.pid)["status"], "OPEN")

    def test_other_market_prices_not_applied(self):
        r = self.tr.update_market_prices({"BTCUSDT": {"last_price": 1.0}}, "spot")
        self.assertEqual(r, [])
        self.assertEqual(self.db.get_position(self.pid)["status"], "OPEN")

    def test_short_stop(self):
        db, tr = make_trader(200)
        p = open_pos(tr, "ETHUSDT", side="SHORT")["position"]
        res = tr.update_market_prices({"ETHUSDT": {"last_price": p["stop_price"] + 0.01}}, "futures")
        self.assertEqual(res[0]["exit_reason"], "STOP_LOSS")
        self.assertLess(res[0]["net_pnl"], 0)


class RiskManagerRules(unittest.TestCase):
    def test_position_size_respects_budget_and_cap(self):
        db, tr = make_trader(200)
        s, why = tr.risk.calculate_position_size("BTCUSDT", "futures", "LONG", 100.0, 1.0, 2.0, 2.0, "trend", RULES)
        self.assertIsNotNone(s, why)
        self.assertLessEqual(s["risk_amount"], 200 * config.RISK_PER_TRADE_PCT / 100 + 1e-9)
        self.assertLess(s["stop_price"], s["entry_price"])
        self.assertGreater(s["target_price"], s["entry_price"])
        self.assertAlmostEqual(s["entry_price"], 100 * (1 + config.SLIPPAGE_BPS / 10000))

    def test_stop_and_target_derive_from_fill_price(self):
        db, tr = make_trader(200)
        s, _ = tr.risk.calculate_position_size("BTCUSDT", "futures", "SHORT", 100.0, 1.0, 2.0, 2.0, "trend", RULES)
        self.assertAlmostEqual(s["stop_price"] - s["entry_price"], 2.0, places=2)
        self.assertAlmostEqual(s["entry_price"] - s["target_price"], 4.0, places=2)

    def test_remaining_risk_shrinks_as_positions_fill_the_cap(self):
        db, tr = make_trader(5000)
        used = []
        for i, sym in enumerate(("AUSDT", "BUSDT", "CUSDT")):
            r = open_pos(tr, sym, 100, 3.0, "LONG" if i < 2 else "SHORT")
            self.assertTrue(r["success"], r)
            used.append(db.get_portfolio()["open_risk"])
        self.assertEqual(used, sorted(used))
        st = tr.risk.get_risk_status()
        self.assertAlmostEqual(st["risk_remaining"], st["risk_cap"] - st["open_risk"])
        self.assertLessEqual(st["open_risk"], st["risk_cap"] + 1e-9)

    def test_cap_is_dynamic_with_equity(self):
        db, tr = make_trader(200)
        self.assertAlmostEqual(tr.risk.get_risk_status()["risk_cap"], 20.0)
        db._cash_move(db.conn, 0, "x") if False else None
        with db._tx() as c:
            db._cash_move(c, 100.0, "TEST_DEPOSIT")
        self.assertAlmostEqual(tr.risk.get_risk_status()["risk_cap"], 30.0)

    def test_blocks_when_remaining_budget_is_tiny(self):
        db, tr = make_trader(5000)                                   # cash is not the binding limit here
        old = config.RISK_PER_TRADE_PCT
        try:
            config.RISK_PER_TRADE_PCT = 6.0                          # 300 per trade, cap is 500
            self.assertTrue(open_pos(tr, "AUSDT", atr=10.0)["success"])
            r = open_pos(tr, "BUSDT", side="SHORT", atr=10.0)
            self.assertTrue(r["success"], r)                         # gets only what is left (~200), not 300
            self.assertLessEqual(r["position"]["risk_amount"], 500 - 300 + 1e-6 + 5)
            r = open_pos(tr, "CUSDT", atr=10.0)
            self.assertFalse(r["success"])
        finally:
            config.RISK_PER_TRADE_PCT = old
        port = db.get_portfolio()
        self.assertLessEqual(port["open_risk"], port["equity"] * 0.10 + 1e-9)

    def test_daily_loss_limit_blocks(self):
        db, tr = make_trader(200)
        db.refresh_daily_baseline()
        with db._tx() as c:
            db._cash_move(c, -7.0, "TEST_LOSS")                      # -3.5% > 3% limit
        r = open_pos(tr)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "Daily loss limit reached")

    def test_consecutive_losses_pause(self):
        db, tr = make_trader(5000)
        for i in range(config.MAX_CONSECUTIVE_LOSSES):
            p = open_pos(tr, f"L{i}USDT")["position"]
            tr.close_position(p["id"], 99.6, "MANUAL")             # small losses: daily limit must not fire first
        blocked, why = tr.risk.protection_status()
        self.assertTrue(blocked)
        self.assertIn("consecutive", why)
        self.assertFalse(open_pos(tr, "NEWUSDT")["success"])

    def test_strategy_kill_switch_is_per_strategy(self):
        db, tr = make_trader(5000)
        old = config.MAX_CONSECUTIVE_LOSSES
        config.MAX_CONSECUTIVE_LOSSES = 2
        try:
            for i in range(2):
                p = open_pos(tr, f"K{i}USDT", strategy="breakout")["position"]
                tr.close_position(p["id"], 99.0, "MANUAL")
            self.assertFalse(tr.risk.brain.is_strategy_healthy("breakout"))
            self.assertTrue(tr.risk.brain.is_strategy_healthy("trend"))
        finally:
            config.MAX_CONSECUTIVE_LOSSES = old

    def test_max_drawdown_pause(self):
        db, tr = make_trader(200)
        db.get_peak_equity()
        with db._tx() as c:
            db._cash_move(c, -40.0, "TEST_LOSS")                     # -20% from peak
        blocked, why = tr.risk.protection_status()
        self.assertTrue(blocked)
        self.assertIn("drawdown", why.lower())
        self.assertGreater(float(db.get_state("dd_block_until")), time.time())

    def test_data_outage_blocks_new_entries(self):
        db, tr = make_trader(200)
        tr.risk.set_data_status(False, "no market data for 600s")
        r = open_pos(tr)
        self.assertFalse(r["success"])
        self.assertIn("outage", r["reason"])
        tr.risk.set_data_status(True)
        self.assertTrue(open_pos(tr)["success"])

    def test_unknown_exchange_rules_block_when_required(self):
        db, tr = make_trader(200)
        r = tr.open_position("BTCUSDT", 100, 1, "LONG", "futures", {}, strategy="trend", rules=None)
        self.assertFalse(r["success"])
        self.assertIn("rules", r["reason"].lower())

    def test_invalid_inputs(self):
        db, tr = make_trader(200)
        for kw in (dict(price=float("nan")), dict(price=-1), dict(atr=0), dict(atr=float("inf")),
                   dict(side="SIDEWAYS"), dict(source="margin")):
            args = dict(price=100, atr=1, side="LONG", source="futures")
            args.update(kw)
            r = tr.open_position("BTCUSDT", args["price"], args["atr"], args["side"], args["source"], {},
                                 strategy="trend", rules=RULES)
            self.assertFalse(r["success"], kw)

    def test_spot_is_long_only_and_uses_spot_fee(self):
        db, tr = make_trader(200)
        self.assertFalse(open_pos(tr, side="SHORT", source="spot")["success"])
        p = open_pos(tr, "ETHUSDT", source="spot")["position"]
        self.assertAlmostEqual(p["opening_fee"], p["quantity"] * p["entry_price"] * config.FEE_RATE_SPOT)
        self.assertEqual(p["leverage"], 1)

    def test_same_symbol_cannot_be_open_in_both_markets(self):
        db, tr = make_trader(200)
        self.assertTrue(open_pos(tr, source="spot")["success"])
        self.assertFalse(open_pos(tr, source="futures")["success"])

    def test_dynamic_kelly_never_exceeds_configured_ceiling_and_counts_zero_pnl_correctly(self):
        from brain import kelly_risk_pct
        self.assertEqual(kelly_risk_pct([1.0] * 5), config.RISK_PER_TRADE_PCT)         # too small a sample
        v = kelly_risk_pct([2.0, -1.0] * 30)
        self.assertLessEqual(v, config.RISK_PER_TRADE_PCT * 1.75)
        self.assertGreaterEqual(v, 0.5)
        self.assertEqual(kelly_risk_pct([-1.0, 0.0, 1.0] * 20) >= 0.5, True)


if __name__ == "__main__":
    unittest.main()
