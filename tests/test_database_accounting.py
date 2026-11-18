import json
import os
import sqlite3
import threading
import unittest

import _env  # noqa: F401
import accounting as A
import config
from database import Database
from helpers import make_db, make_trader, open_pos, check_integrity, tmp_db_path, RULES


class OpenAtomicity(unittest.TestCase):
    def test_open_records_everything_and_reserves_cash(self):
        db, tr = make_trader(200)
        r = open_pos(tr)
        self.assertTrue(r["success"], r)
        p = r["position"]
        self.assertEqual(p["status"], "OPEN")
        self.assertEqual(p["initial_quantity"], p["quantity"])
        self.assertAlmostEqual(p["initial_risk"], p["quantity"] * abs(p["entry_price"] - p["stop_price"]))
        port = db.get_portfolio()
        self.assertAlmostEqual(port["cash_balance"], 200 - p["margin_used"] - p["opening_fee"])
        self.assertAlmostEqual(port["equity"], 200 - p["opening_fee"])          # only the fee is lost at open
        check_integrity(self, db)

    def test_second_open_of_same_symbol_rejected_in_db(self):
        db, tr = make_trader(200)
        self.assertTrue(open_pos(tr)["success"])
        r = open_pos(tr)
        self.assertFalse(r["success"])
        self.assertEqual(r["reason"], "Duplicate open position")
        self.assertEqual(len(db.get_open_positions()), 1)

    def test_db_gate_cannot_be_bypassed_by_forged_risk(self):
        db = make_db(200)
        data = dict(symbol="X", source="futures", side="LONG", quantity=100.0, entry_price=100.0,
                    stop_price=50.0, target_price=200.0, margin_used=10.0, risk_amount=0.01,  # forged tiny risk
                    opening_fee=0.01)
        with self.assertRaises(ValueError) as cm:
            db.create_position(data)
        self.assertIn("risk", str(cm.exception).lower())
        self.assertEqual(db.get_open_positions(), [])
        check_integrity(self, db)

    def test_failed_open_changes_nothing(self):
        db = make_db(200)
        before = db.get_portfolio()
        with self.assertRaises(ValueError):
            db.create_position(dict(symbol="X", source="spot", side="SHORT", quantity=1, entry_price=10,
                                    stop_price=11, target_price=8, margin_used=10, risk_amount=1, opening_fee=0.01))
        self.assertEqual(db.get_portfolio()["cash_balance"], before["cash_balance"])
        self.assertEqual(db.get_ledger(), [])

    def test_concurrent_opens_never_exceed_aggregate_cap(self):
        db, tr = make_trader(200)
        syms = [f"C{i}USDT" for i in range(12)]
        old_max_open, old_same = config.MAX_OPEN_POSITIONS, config.MAX_SAME_SIDE
        config.MAX_OPEN_POSITIONS = config.MAX_SAME_SIDE = 12      # let ONLY the risk cap bind
        try:
            results, barrier = [], threading.Barrier(len(syms))

            def worker(sym):
                barrier.wait()
                results.append(open_pos(tr, sym, 100.0, 2.0, "LONG", "futures"))
            ts = [threading.Thread(target=worker, args=(s,)) for s in syms]
            [t.start() for t in ts]
            [t.join() for t in ts]
        finally:
            config.MAX_OPEN_POSITIONS, config.MAX_SAME_SIDE = old_max_open, old_same
        port = db.get_portfolio()
        self.assertLessEqual(port["open_risk"], port["equity"] * 0.10 + 1e-6)
        self.assertGreaterEqual(sum(1 for r in results if r["success"]), 1)
        check_integrity(self, db)

    def test_two_database_connections_race_is_serialised_by_sqlite(self):
        path = tmp_db_path()
        db1, db2 = make_db(200, path), Database(path)
        data = lambda s: dict(symbol=s, source="futures", side="LONG", quantity=1.0, entry_price=100.0,
                              stop_price=88.0, target_price=130.0, margin_used=100.0, risk_amount=12.1,
                              opening_fee=0.04)
        db1.create_position(data("AAA"))
        with self.assertRaises(ValueError):          # 12.1 + 12.1 > 20 : second connection sees the first
            db2.create_position(data("BBB"))


class ClosingAccounting(unittest.TestCase):
    def test_full_close_net_equals_gross_minus_all_fees(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        row = tr.close_position(p["id"], 104.0, "MANUAL")
        exit_px = A.exit_fill(104.0, "LONG")
        gross = (exit_px - p["entry_price"]) * p["quantity"]
        close_fee = exit_px * p["quantity"] * config.fee_rate("futures")
        self.assertAlmostEqual(row["gross_pnl"], gross)
        self.assertAlmostEqual(row["net_pnl"], gross - p["opening_fee"] - close_fee)
        self.assertAlmostEqual(row["fees_total"], p["opening_fee"] + close_fee)
        self.assertAlmostEqual(db.get_portfolio()["cash_balance"], 200 + row["net_pnl"])
        check_integrity(self, db)

    def test_fees_are_not_charged_twice(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        row = tr.close_position(p["id"], p["entry_price"] / (1 - config.SLIPPAGE_BPS / 10000), "MANUAL")
        # exit exactly at entry fill: loss is exactly entry fee + exit fee (one each)
        self.assertAlmostEqual(row["net_pnl"], -(row["opening_fee"] + row["closing_fee"]), places=9)
        self.assertAlmostEqual(row["fees_total"], row["opening_fee"] + row["closing_fee"])

    def test_short_profit_and_loss(self):
        db, tr = make_trader(200)
        p = open_pos(tr, side="SHORT")["position"]
        win = tr.close_position(p["id"], 97.0, "MANUAL")
        self.assertGreater(win["gross_pnl"], 0)
        p2 = open_pos(tr, "ETHUSDT", side="SHORT")["position"]
        loss = tr.close_position(p2["id"], 101.0, "MANUAL")
        self.assertLess(loss["gross_pnl"], 0)
        check_integrity(self, db)

    def test_double_close_is_noop(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        self.assertIsNotNone(tr.close_position(p["id"], 100.0, "MANUAL"))
        cash = db.get_portfolio()["cash_balance"]
        self.assertIsNone(tr.close_position(p["id"], 50.0, "MANUAL"))
        self.assertEqual(db.get_portfolio()["cash_balance"], cash)

    def test_invalid_exit_price_refused(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        for bad in (0, -5, float("nan"), float("inf"), None):
            self.assertIsNone(tr.close_position(p["id"], bad, "MANUAL") if bad is not None else None)
        self.assertEqual(db.get_position(p["id"])["status"], "OPEN")


class PartialClose(unittest.TestCase):
    def setUp(self):
        self.db, self.tr = make_trader(200)
        self.p = open_pos(self.tr)["position"]

    def test_partial_then_final_keeps_all_profit_and_fees(self):
        p = self.p
        half = p["quantity"] / 2
        ex1 = A.exit_fill(103.0, "LONG")
        fee1 = ex1 * half * config.fee_rate("futures")
        mid = self.db.partial_close(p["id"], ex1, half, "SCALE_OUT_1.0R", fee1)
        self.assertAlmostEqual(mid["quantity"], half)
        self.assertEqual(mid["scale_out_done"], 1)
        self.assertAlmostEqual(mid["initial_risk"], p["initial_risk"])                  # R unit never shrinks
        self.assertAlmostEqual(mid["initial_quantity"], p["initial_quantity"])
        row = self.tr.close_position(p["id"], 106.0, "TAKE_PROFIT")
        ex2 = A.exit_fill(106.0, "LONG")
        gross = (ex1 - p["entry_price"]) * half + (ex2 - p["entry_price"]) * half
        fees = p["opening_fee"] + fee1 + ex2 * half * config.fee_rate("futures")
        self.assertAlmostEqual(row["gross_pnl"], gross)
        self.assertAlmostEqual(row["fees_total"], fees)
        self.assertAlmostEqual(row["net_pnl"], gross - fees)
        self.assertAlmostEqual(self.db.get_portfolio()["cash_balance"], 200 + row["net_pnl"])
        r_multiple = row["net_pnl"] / row["initial_risk"]
        self.assertAlmostEqual(r_multiple, (gross - fees) / p["initial_risk"])
        check_integrity(self, self.db)

    def test_repeated_scale_out_is_rejected(self):
        p = self.p
        q = p["quantity"] / 4
        self.assertIsNotNone(self.db.partial_close(p["id"], 103.0, q, "SCALE_OUT_1.0R", 0.01))
        self.assertIsNone(self.db.partial_close(p["id"], 103.0, q, "SCALE_OUT_1.0R", 0.01))
        self.assertAlmostEqual(self.db.get_position(p["id"])["quantity"], p["quantity"] - q)

    def test_partial_cannot_close_everything_or_negative(self):
        for q in (0, -1, self.p["quantity"], self.p["quantity"] * 2):
            self.assertIsNone(self.db.partial_close(self.p["id"], 103.0, q, "MANUAL_PARTIAL", 0.0))

    def test_risk_after_partial_uses_current_stop_and_remaining_qty(self):
        p = self.p
        self.db.partial_close(p["id"], 103.0, p["quantity"] / 2, "SCALE_OUT_1.0R", 0.01)
        now = self.db.get_position(p["id"])
        self.assertAlmostEqual(now["risk_amount"], A.position_open_risk(now))
        self.assertLess(now["risk_amount"], p["risk_amount"])

    def test_losing_partial_then_stop(self):
        p = self.p
        self.db.partial_close(p["id"], 99.0, p["quantity"] / 2, "MANUAL_PARTIAL", 0.01)
        row = self.tr.close_position(p["id"], 95.0, "STOP_LOSS")
        self.assertLess(row["net_pnl"], 0)
        check_integrity(self, self.db)


class StopAndMarks(unittest.TestCase):
    def test_stop_only_tightens(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        self.assertFalse(db.update_stop(p["id"], p["stop_price"] - 1))
        self.assertTrue(db.update_stop(p["id"], p["stop_price"] + 1))
        self.assertTrue(db.update_stop(p["id"], p["stop_price"] - 1, allow_loosen=True))
        with self.assertRaises(ValueError):
            db.update_stop(p["id"], -1)

    def test_equity_uses_marks_and_ignores_invalid(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        db.mark_position(p["id"], p["entry_price"] + 2)
        self.assertAlmostEqual(db.get_portfolio()["unrealized_pnl"], 2 * p["quantity"])
        self.assertFalse(db.mark_position(p["id"], float("nan")))
        self.assertFalse(db.mark_position(p["id"], -3))
        self.assertAlmostEqual(db.get_portfolio()["unrealized_pnl"], 2 * p["quantity"])


class FundingAndFutures(unittest.TestCase):
    def test_funding_paid_reduces_cash_and_net(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        db.apply_funding(p["id"], 0.5, "test")
        db.apply_funding(p["id"], -0.2, "test")
        self.assertAlmostEqual(db.get_position(p["id"])["funding_paid"], 0.3)
        row = tr.close_position(p["id"], 100.0, "MANUAL")
        gross_fees = row["gross_pnl"] - row["fees_total"]
        self.assertAlmostEqual(row["net_pnl"], gross_fees - 0.3)
        check_integrity(self, db)

    def test_funding_idempotent_per_event(self):
        db, tr = make_trader(200)
        p = open_pos(tr)["position"]
        import time
        t_ms = int(time.time() * 1000) + 10_000
        self.assertIsNotNone(tr.apply_funding(p["id"], 0.0001, t_ms))
        self.assertIsNone(tr.apply_funding(p["id"], 0.0001, t_ms))
        self.assertEqual(len([x for x in db.get_ledger() if x["kind"] == "FUNDING"]), 1)

    def test_funding_never_applied_to_spot(self):
        db, tr = make_trader(200)
        p = open_pos(tr, source="spot")["position"]
        import time
        self.assertIsNone(tr.apply_funding(p["id"], 0.01, int(time.time() * 1000) + 5000))

    def test_leverage_position_margin_and_liquidation(self):
        old = config.FUTURES_LEVERAGE
        config.FUTURES_LEVERAGE = 5.0
        try:
            db, tr = make_trader(200)
            p = open_pos(tr, "ETHUSDT", 100, 3.0, "LONG")["position"]
        finally:
            config.FUTURES_LEVERAGE = old
        self.assertAlmostEqual(p["margin_used"] * 5, p["quantity"] * p["entry_price"], places=6)
        self.assertAlmostEqual(p["liquidation_price"], A.liquidation_price("LONG", p["entry_price"], 5.0))
        self.assertLess(p["liquidation_price"], p["stop_price"])
        res = tr.update_market_prices({"ETHUSDT": {"last_price": p["liquidation_price"] - 0.01}}, "futures")
        self.assertEqual(res[0]["exit_reason"], "LIQUIDATION")
        self.assertGreaterEqual(db.get_portfolio()["cash_balance"], 0)
        check_integrity(self, db)


class PersistenceAndMigration(unittest.TestCase):
    def test_restart_keeps_open_positions_and_stops(self):
        path = tmp_db_path()
        db, tr = make_trader(200, path)
        p = open_pos(tr)["position"]
        tr.update_market_prices({"BTCUSDT": {"last_price": 102.0}}, "futures")
        before = db.get_position(p["id"])
        port = db.get_portfolio()
        db.close()
        db2 = Database(path)
        after = db2.get_position(p["id"])
        for k in ("stop_price", "quantity", "entry_price", "initial_risk", "mark_price", "status"):
            self.assertEqual(before[k], after[k], k)
        self.assertAlmostEqual(db2.get_portfolio()["equity"], port["equity"])
        check_integrity(self, db2)

    def test_gap_through_stop_after_restart_closes_at_gap_price(self):
        path = tmp_db_path()
        db, tr = make_trader(200, path)
        p = open_pos(tr)["position"]
        db.close()
        from paper_trading import PaperTrader
        from risk_manager import RiskManager
        db2 = Database(path)
        tr2 = PaperTrader(db2, RiskManager(db2))
        res = tr2.update_market_prices({"BTCUSDT": {"last_price": p["stop_price"] - 5}}, "futures")
        self.assertEqual(res[0]["exit_reason"], "STOP_LOSS")
        self.assertLess(res[0]["exit_price"], p["stop_price"] - 5 + 1e-9)      # not magically filled AT the stop

    def test_legacy_database_is_migrated_without_losing_history(self):
        path = tmp_db_path()
        con = sqlite3.connect(path)
        con.executescript("""
        CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE positions(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, source TEXT NOT NULL,
          side TEXT NOT NULL, quantity REAL NOT NULL, entry_price REAL NOT NULL, stop_price REAL NOT NULL,
          target_price REAL NOT NULL, margin_used REAL NOT NULL, risk_amount REAL NOT NULL, opening_fee REAL NOT NULL,
          status TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT, exit_price REAL, gross_pnl REAL,
          net_pnl REAL, closing_fee REAL, exit_reason TEXT, metadata TEXT);
        CREATE TABLE decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, action TEXT,
          score REAL, reason TEXT, created_at TEXT NOT NULL);
        CREATE TABLE equity_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT, equity REAL, created_at TEXT NOT NULL);
        """)
        con.executemany("INSERT INTO state VALUES(?,?)", [("initial_balance", "200"), ("cash_balance", "190.5"),
                        ("realized_pnl", "-4.0"), ("mark:2", "101.5")])
        con.execute("INSERT INTO positions VALUES(1,'ETHUSDT','futures','LONG',1,100,98,104,100,2.0,0.04,'CLOSED',"
                    "'2025-01-01T00:00:00+00:00','2025-01-01T05:00:00+00:00',97,-3,-3.1,0.04,'STOP_LOSS','{}')")
        con.execute("INSERT INTO positions VALUES(2,'BTCUSDT','futures','LONG',1,100,98,104,100,2.0,0.04,'OPEN',"
                    "'2025-01-02T00:00:00+00:00',NULL,NULL,NULL,NULL,NULL,NULL,'{}')")
        con.commit(); con.close()
        db = Database(path)
        closed = db.get_position(1)
        self.assertEqual(closed["net_pnl"], -3.1)                       # history preserved
        self.assertAlmostEqual(closed["initial_risk"], 2.0)             # back-filled R unit
        opened = db.get_position(2)
        self.assertEqual(opened["initial_quantity"], 1)
        self.assertEqual(opened["mark_price"], 101.5)                   # legacy mark moved to the new column
        self.assertEqual(opened["scale_out_done"], 0)
        self.assertEqual(db.get_portfolio()["cash_balance"], 190.5)
        self.assertAlmostEqual(db.integrity_report()["cash_minus_ledger"], 0.0)
        Database(path)                                                  # idempotent second migration
        self.assertEqual(len(db.get_ledger()), 1)

    def test_wal_mode_and_foreign_keys(self):
        db = make_db()
        self.assertEqual(db.conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        self.assertEqual(db.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_unwritable_path_falls_back_and_reports_it(self):
        db = Database("/proc/definitely/not/writable/x.db")
        self.assertTrue(db.fallback_used)
        self.assertFalse(db.storage_info()["persistent"])


class Performance(unittest.TestCase):
    def test_performance_report_matches_trade_rows(self):
        db, tr = make_trader(500)
        for i, px in enumerate((104, 96, 103)):
            p = open_pos(tr, f"S{i}USDT")["position"]
            tr.close_position(p["id"], px, "MANUAL")
        perf = db.get_performance()
        rows = db.get_closed_trades()
        self.assertEqual(perf["total_trades"], 3)
        self.assertAlmostEqual(perf["net_pnl"], sum(r["net_pnl"] for r in rows))
        self.assertAlmostEqual(perf["total_fees"], sum(r["fees_total"] for r in rows))
        self.assertAlmostEqual(db.get_portfolio()["cash_balance"], 500 + perf["net_pnl"])


if __name__ == "__main__":
    unittest.main()
