"""Randomised (seeded, reproducible) stress run that checks the financial invariants after EVERY step."""
import random
import time
import unittest

import _env  # noqa: F401
import accounting as A
import config
from database import Database
from helpers import make_db, make_trader, tmp_db_path, RULES, check_integrity
from paper_trading import PaperTrader
from risk_manager import RiskManager

SYMS = ["AUSDT", "BUSDT", "CUSDT", "DUSDT", "EUSDT", "FUSDT", "GUSDT", "HUSDT"]


class Invariants(unittest.TestCase):
    def assert_invariants(self, db, where):
        port = db.get_portfolio()
        pos = db.get_open_positions()
        self.assertGreaterEqual(port["cash_balance"], -1e-6, where)
        self.assertLessEqual(len(pos), config.MAX_OPEN_POSITIONS, where)
        self.assertEqual(len({p["symbol"] for p in pos}), len(pos), where)
        for side in ("LONG", "SHORT"):
            self.assertLessEqual(sum(1 for p in pos if p["side"] == side), config.MAX_SAME_SIDE, where)
        self.assertAlmostEqual(port["equity"], port["cash_balance"] + port["open_margin"] + port["unrealized_pnl"], 7)
        rep = db.integrity_report()
        for k in ("cash_minus_ledger", "cash_margin_identity", "realized_minus_trades"):
            self.assertAlmostEqual(rep[k], 0.0, places=6, msg=f"{where}: {k} {rep}")
        closed = db.get_closed_trades()
        self.assertAlmostEqual(db.get_performance()["net_pnl"], sum(t["net_pnl"] for t in closed), 7)
        for t in closed:
            self.assertAlmostEqual(t["net_pnl"], t["gross_pnl"] - t["fees_total"] - t["funding_paid"], 7, msg=where)
            self.assertTrue(t["initial_risk"] > 0)
        for p in pos:
            self.assertGreaterEqual(p["risk_amount"], 0)
            self.assertAlmostEqual(p["risk_amount"], A.position_open_risk(p), 6, msg=where)

    def run_sim(self, seed, steps=250, spot_share=0.3, leverage=1.0):
        rnd = random.Random(seed)
        old_lev = config.FUTURES_LEVERAGE
        config.FUTURES_LEVERAGE = leverage
        try:
            path = tmp_db_path()
            db, tr = make_trader(200, path)
            prices = {s: 100.0 * rnd.uniform(0.5, 2) for s in SYMS}
            for step in range(steps):
                where = f"seed={seed} step={step}"
                action = rnd.random()
                if action < 0.30:
                    s = rnd.choice(SYMS)
                    src = "spot" if rnd.random() < spot_share else "futures"
                    side = "LONG" if src == "spot" else rnd.choice(["LONG", "SHORT"])
                    before = len(db.get_open_positions())
                    r = tr.open_position(s, prices[s], prices[s] * rnd.uniform(0.004, 0.04), side, src, {},
                                         stop_mult=rnd.uniform(1.2, 3), rr=rnd.uniform(1.5, 3), strategy="trend",
                                         rules=RULES)
                    if r["success"]:
                        port = db.get_portfolio()
                        self.assertLessEqual(port["open_risk"], port["equity"] * 0.10 + 1e-6, where)
                        self.assertEqual(len(db.get_open_positions()), before + 1, where)
                elif action < 0.80:
                    for s in SYMS:                                   # random walk with occasional gaps
                        shock = rnd.gauss(0, 0.012) + (rnd.choice([-0.08, 0.08]) if rnd.random() < 0.02 else 0)
                        prices[s] = max(1.0, prices[s] * (1 + shock))
                    tr.update_market_prices({s: {"last_price": prices[s]} for s in SYMS}, None)
                elif action < 0.88:
                    pos = db.get_open_positions()
                    if pos:
                        p = rnd.choice(pos)
                        tr.close_position(p["id"], prices[p["symbol"]], "MANUAL")
                elif action < 0.94:
                    pos = [p for p in db.get_open_positions() if p["source"] == "futures"]
                    if pos:
                        p = rnd.choice(pos)
                        tr.apply_funding(p["id"], rnd.uniform(-0.0008, 0.0008), int(time.time() * 1000) + step * 1000 + 5000)
                else:                                                # restart mid-flight
                    db.close()
                    db = Database(path)
                    tr = PaperTrader(db, RiskManager(db))
                self.assert_invariants(db, where)
            return db
        finally:
            config.FUTURES_LEVERAGE = old_lev

    def test_random_runs_1x(self):
        trades = 0
        for seed in range(12):
            db = self.run_sim(seed)
            trades += len(db.get_closed_trades())
        self.assertGreater(trades, 30, "the simulation must actually trade")

    def test_random_runs_leveraged_futures(self):
        for seed in range(100, 106):
            self.run_sim(seed, leverage=5.0, spot_share=0.0)

    def test_spot_only(self):
        for seed in range(200, 204):
            db = self.run_sim(seed, spot_share=1.0)
            self.assertTrue(all(t["side"] == "LONG" for t in db.get_closed_trades()))

    def test_fees_never_counted_twice_across_random_runs(self):
        db = self.run_sim(7, steps=300)
        for t in db.get_closed_trades():
            ledger_fee_cap = t["fees_total"]
            self.assertGreaterEqual(ledger_fee_cap, t["closing_fee"] - 1e-12)
            # entry fee + every closing fee == fees_total, and cash movement of the trade reconciles exactly
        led = db.get_ledger(100000)
        by_pos = {}
        for r in led:
            if r["position_id"]:
                by_pos[r["position_id"]] = by_pos.get(r["position_id"], 0.0) + r["amount"]
        for t in db.get_closed_trades():
            self.assertAlmostEqual(by_pos[t["id"]], t["net_pnl"], 7, msg=f"position {t['id']}")

    def test_portfolio_value_matches_trade_record_after_many_partials(self):
        db, tr = make_trader(5000)
        total_net = 0.0
        for i in range(40):
            p = tr.open_position(f"S{i}USDT", 100.0, 3.0, "LONG", "futures", {}, stop_mult=2, rr=2, strategy="trend",
                                 rules=RULES)["position"]
            unit = abs(p["entry_price"] - p["initial_stop"])
            tr.update_market_prices({p["symbol"]: {"last_price": p["entry_price"] + unit * 1.1}}, "futures")
            row = tr.close_position(p["id"], p["entry_price"] + unit * (i % 5 - 1), "MANUAL")
            total_net += row["net_pnl"]
            db.set_state(f"cooldown:futures:{p['symbol']}", 0)
        self.assertAlmostEqual(db.get_portfolio()["cash_balance"], 5000 + total_net, 7)
        check_integrity(self, db)


if __name__ == "__main__":
    unittest.main()
