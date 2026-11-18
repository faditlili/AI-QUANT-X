import os
import tempfile
import _env  # noqa: F401
import config
from database import Database
from paper_trading import PaperTrader
from risk_manager import RiskManager

RULES = {"step": 0.001, "min_qty": 0.001, "min_notional": 5.0, "tick": 0.01}


def tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def make_db(balance=200.0, path=None):
    return Database(path or tmp_db_path(), initial_balance=balance)


def make_trader(balance=200.0, path=None):
    db = make_db(balance, path)
    return db, PaperTrader(db, RiskManager(db))


def open_pos(trader, symbol="BTCUSDT", price=100.0, atr=1.0, side="LONG", source="futures", strategy="trend",
             stop_mult=2.0, rr=2.0):
    return trader.open_position(symbol, price, atr, side, source, {}, stop_mult=stop_mult, rr=rr,
                                strategy=strategy, rules=RULES)


def check_integrity(tc, db, places=7):
    rep = db.integrity_report()
    for k in ("cash_minus_ledger", "cash_margin_identity", "realized_minus_trades"):
        tc.assertAlmostEqual(rep[k], 0.0, places=places, msg=f"{k}: {rep}")
