import unittest
import _env  # noqa: F401
import accounting as A
import config


class FillsAndPnl(unittest.TestCase):
    def test_slippage_is_always_adverse(self):
        self.assertAlmostEqual(A.entry_fill(100, "LONG", 10), 100.1)
        self.assertAlmostEqual(A.entry_fill(100, "SHORT", 10), 99.9)
        self.assertAlmostEqual(A.exit_fill(100, "LONG", 10), 99.9)
        self.assertAlmostEqual(A.exit_fill(100, "SHORT", 10), 100.1)

    def test_gross_pnl_signs(self):
        self.assertAlmostEqual(A.gross_pnl("LONG", 100, 110, 2), 20)
        self.assertAlmostEqual(A.gross_pnl("SHORT", 100, 110, 2), -20)
        self.assertAlmostEqual(A.gross_pnl("SHORT", 100, 90, 2), 20)

    def test_fee_rates_are_per_market(self):
        self.assertEqual(config.fee_rate("spot"), config.FEE_RATE_SPOT)
        self.assertEqual(config.fee_rate("futures"), config.FEE_RATE)

    def test_funding_direction(self):
        self.assertAlmostEqual(A.funding_payment("LONG", 1000, 0.0001), 0.1)     # long pays
        self.assertAlmostEqual(A.funding_payment("SHORT", 1000, 0.0001), -0.1)   # short receives
        self.assertAlmostEqual(A.funding_payment("LONG", 1000, -0.0001), -0.1)

    def test_liquidation_price(self):
        self.assertAlmostEqual(A.liquidation_price("LONG", 100, 10, 0.005), 90.5)
        self.assertAlmostEqual(A.liquidation_price("SHORT", 100, 10, 0.005), 109.5)
        self.assertGreater(A.liquidation_price("SHORT", 100, 1, 0.005), 190)   # fully collateralised short

    def test_floor_to_step_is_exact(self):
        self.assertEqual(A.floor_to_step(0.123456, 0.001), 0.123)
        self.assertEqual(A.floor_to_step(1.0, 0.1), 1.0)         # no float drift (0.1*10)
        self.assertEqual(A.floor_to_step(5, None), 5)


class StopRisk(unittest.TestCase):
    def test_long_includes_exit_costs(self):
        r = A.stop_risk("LONG", 100, 95, 2, "futures", fee=0.001, slippage_bps=10)
        self.assertAlmostEqual(r, 10 + 2 * 95 * (0.001 + 0.001))

    def test_locked_profit_is_zero_risk(self):
        self.assertEqual(A.stop_risk("LONG", 100, 120, 1, "futures", fee=0.0004, slippage_bps=5), 0.0)

    def test_short(self):
        self.assertGreater(A.stop_risk("SHORT", 100, 105, 1, "futures"), 5)

    def test_entry_fee_added_for_candidates_only(self):
        a = A.stop_risk("LONG", 100, 95, 1, "spot")
        b = A.stop_risk("LONG", 100, 95, 1, "spot", entry_fee=0.1)
        self.assertAlmostEqual(b - a, 0.1)


class Sizing(unittest.TestCase):
    def size(self, **kw):
        base = dict(equity=200, cash=200, entry=100, stop=98, side="LONG", source="futures", risk_budget=4.0)
        base.update(kw)
        return A.size_position(**base)

    def test_stop_out_never_exceeds_budget(self):
        for src in ("spot", "futures"):
            s, why = self.size(source=src, cash=10000, equity=10000, risk_budget=20)
            self.assertIsNotNone(s, why)
            self.assertLessEqual(s["risk_amount"], 20 + 1e-9)
            self.assertGreater(s["risk_amount"], 19.9)          # sized to use the budget, not far below

    def test_actual_loss_at_stop_matches_risk(self):
        s, _ = self.size(cash=10000, equity=10000, risk_budget=20)
        exit_price = A.exit_fill(98, "LONG")
        loss = -(A.gross_pnl("LONG", 100, exit_price, s["quantity"]) - s["opening_fee"]
                 - exit_price * s["quantity"] * config.fee_rate("futures"))
        self.assertAlmostEqual(loss, s["risk_amount"], delta=0.02)

    def test_cash_limits_quantity(self):
        s, _ = self.size(cash=50, equity=200, risk_budget=1000)
        self.assertLessEqual(s["margin_used"] + s["opening_fee"], 50)

    def test_leverage_reduces_margin_not_risk(self):
        a, _ = self.size(cash=10000, equity=10000, risk_budget=20, leverage=1)
        b, _ = self.size(cash=10000, equity=10000, risk_budget=20, leverage=5)
        self.assertAlmostEqual(a["quantity"], b["quantity"], places=6)
        self.assertAlmostEqual(b["margin_used"] * 5, b["notional"], places=6)

    def test_spot_ignores_leverage(self):
        s, _ = self.size(source="spot", leverage=10)
        self.assertEqual(s["leverage"], 1.0)

    def test_rejects_bad_inputs(self):
        for kw in (dict(entry=float("nan")), dict(entry=-1), dict(stop=101), dict(risk_budget=0), dict(stop=0)):
            s, why = self.size(**kw)
            self.assertIsNone(s, kw)
            self.assertTrue(why)

    def test_below_min_notional_rejected(self):
        s, why = self.size(risk_budget=0.01)
        self.assertIsNone(s)

    def test_exchange_rules_respected(self):
        rules = {"step": 0.5, "min_qty": 0.5, "min_notional": 5}
        s, why = self.size(cash=10000, equity=10000, risk_budget=20, rules=rules)
        self.assertEqual(round(s["quantity"] / 0.5) * 0.5, s["quantity"])
        s, why = self.size(rules={"step": 1, "min_qty": 1000})
        self.assertIsNone(s)


class PortfolioLimits(unittest.TestCase):
    def pos(self, symbol, side="LONG", risk_dist=1.0, qty=1.0, source="futures"):
        entry = 100.0
        stop = entry - risk_dist if side == "LONG" else entry + risk_dist
        return {"symbol": symbol, "source": source, "side": side, "quantity": qty, "entry_price": entry,
                "stop_price": stop}

    def cand(self, symbol, risk, side="LONG", source="futures", margin=20, fee=0.01):
        return {"symbol": symbol, "source": source, "side": side, "margin_used": margin, "opening_fee": fee,
                "risk_amount": risk}

    def test_spec_example_200_equity_cap_20(self):
        self.assertAlmostEqual(A.portfolio_risk_cap(200), 20.0)

    def test_spec_example_15_used_blocks_over_5(self):
        open_ = [self.pos("A", qty=1, risk_dist=1), self.pos("B", "SHORT", qty=1, risk_dist=1)]
        used = A.total_open_risk(open_)
        remaining = 20 - used
        ok, _ = A.check_portfolio_limits(equity=200, cash=200, positions=open_,
                                         cand=self.cand("C", remaining - 0.01))
        self.assertTrue(ok)
        ok, why = A.check_portfolio_limits(equity=200, cash=200, positions=open_,
                                           cand=self.cand("C", remaining + 0.01))
        self.assertFalse(ok)

    def test_cap_tracks_equity(self):
        c = self.cand("C", 15)
        self.assertFalse(A.check_portfolio_limits(equity=100, cash=100, positions=[], cand=c)[0])
        self.assertTrue(A.check_portfolio_limits(equity=300, cash=300, positions=[], cand=c)[0])

    def test_hard_ceiling_even_if_config_raised(self):
        old = (config.MAX_PORTFOLIO_RISK_PCT, config.MAX_TOTAL_HEAT_PCT, config.MAX_DIRECTIONAL_HEAT_PCT)
        try:
            config.MAX_PORTFOLIO_RISK_PCT = config.MAX_TOTAL_HEAT_PCT = config.MAX_DIRECTIONAL_HEAT_PCT = 50.0
            self.assertAlmostEqual(A.portfolio_risk_cap(200), 20.0)
            ok, _ = A.check_portfolio_limits(equity=200, cash=200, positions=[], cand=self.cand("C", 25))
            self.assertFalse(ok)
        finally:
            config.MAX_PORTFOLIO_RISK_PCT, config.MAX_TOTAL_HEAT_PCT, config.MAX_DIRECTIONAL_HEAT_PCT = old

    def test_duplicate_symbol_across_markets(self):
        ok, why = A.check_portfolio_limits(equity=200, cash=200, positions=[self.pos("A", source="spot")],
                                           cand=self.cand("A", 1, source="futures"))
        self.assertFalse(ok)
        self.assertEqual(why, "Duplicate open position")

    def test_max_open_positions(self):
        open_ = [self.pos(f"S{i}", "LONG" if i % 2 else "SHORT", risk_dist=0.01) for i in range(config.MAX_OPEN_POSITIONS)]
        ok, why = A.check_portfolio_limits(equity=1e6, cash=1e6, positions=open_, cand=self.cand("Z", 0.1))
        self.assertFalse(ok)
        self.assertIn("Maximum open", why)

    def test_max_same_side(self):
        open_ = [self.pos(f"L{i}", risk_dist=0.01) for i in range(config.MAX_SAME_SIDE)]
        ok, why = A.check_portfolio_limits(equity=1e6, cash=1e6, positions=open_, cand=self.cand("Z", 0.1))
        self.assertFalse(ok)
        ok, _ = A.check_portfolio_limits(equity=1e6, cash=1e6, positions=open_, cand=self.cand("Z", 0.1, "SHORT"))
        self.assertTrue(ok)

    def test_spot_short_rejected_and_cash_checked(self):
        self.assertFalse(A.check_portfolio_limits(equity=200, cash=200, positions=[],
                                                  cand=self.cand("A", 1, "SHORT", "spot"))[0])
        self.assertFalse(A.check_portfolio_limits(equity=200, cash=10, positions=[],
                                                  cand=self.cand("A", 1, margin=50))[0])

    def test_daily_limit_and_bad_equity(self):
        c = self.cand("A", 1)
        self.assertFalse(A.check_portfolio_limits(equity=200, cash=200, positions=[], cand=c,
                                                  daily_change=-6.0, daily_limit=6.0)[0])
        self.assertFalse(A.check_portfolio_limits(equity=0, cash=200, positions=[], cand=c)[0])
        self.assertFalse(A.check_portfolio_limits(equity=float("nan"), cash=200, positions=[], cand=c)[0])


if __name__ == "__main__":
    unittest.main()
