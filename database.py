"""SQLite persistence for the VIRTUAL portfolio only.

Every money movement happens inside ONE `BEGIN IMMEDIATE` transaction and is mirrored in the
append-only `ledger` table, so cash can always be reconciled:  cash == initial_balance + sum(ledger).
The database is also the last line of defence for the risk limits: create_position() re-validates
every hard limit (accounting.check_portfolio_limits) inside the transaction, so no code path can
open a position that breaks them, even when two opens race.
"""
import json
import logging
import math
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import accounting
import config

log = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


_NEW_COLUMNS = {
    "strategy": "TEXT", "initial_stop": "REAL", "initial_quantity": "REAL",
    "partial_pnl": "REAL DEFAULT 0", "initial_risk": "REAL", "mark_price": "REAL", "mark_time": "REAL",
    "scale_out_done": "INTEGER DEFAULT 0", "partial_gross": "REAL DEFAULT 0", "partial_fees": "REAL DEFAULT 0",
    "funding_paid": "REAL DEFAULT 0", "fees_total": "REAL", "leverage": "REAL DEFAULT 1",
    "liquidation_price": "REAL",
}


class Database:
    def __init__(self, db_path=None, initial_balance=None):
        self.path = str(db_path or config.DB_PATH)
        self.fallback_used = False
        if self.path != ":memory:":
            try:
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
                probe = Path(self.path).parent / ".write_test"
                probe.write_text("ok")
                probe.unlink()
            except OSError:
                fallback = Path("./data/ai_quant_x.db")
                log.warning("DB path %s not writable; using %s (NOT persistent on Railway).", self.path, fallback)
                fallback.parent.mkdir(parents=True, exist_ok=True)
                self.path = str(fallback)
                self.fallback_used = True
        self.lock = threading.RLock()
        # autocommit mode: transactions are managed explicitly in _tx()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=20, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=20000")
        self._schema()
        start = float(initial_balance or config.INITIAL_BALANCE)
        with self._tx():
            if not self.conn.execute("SELECT 1 FROM state WHERE key='initial_balance'").fetchone():
                for k in ("initial_balance", "daily_baseline", "cash_balance"):
                    self.conn.execute("INSERT OR IGNORE INTO state(key,value) VALUES(?,?)", (k, str(start)))
            self._migrate_ledger()

    # ------------------------------------------------------------------ infrastructure
    @contextmanager
    def _tx(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def _schema(self):
        with self.lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS positions(
              id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, source TEXT NOT NULL,
              side TEXT NOT NULL, quantity REAL NOT NULL, entry_price REAL NOT NULL,
              stop_price REAL NOT NULL, target_price REAL NOT NULL, margin_used REAL NOT NULL,
              risk_amount REAL NOT NULL, opening_fee REAL NOT NULL, status TEXT NOT NULL,
              opened_at TEXT NOT NULL, closed_at TEXT, exit_price REAL, gross_pnl REAL,
              net_pnl REAL, closing_fee REAL, exit_reason TEXT, metadata TEXT,
              CHECK(source IN ('spot','futures')), CHECK(side IN ('LONG','SHORT'))
            );
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            CREATE TABLE IF NOT EXISTS decisions(
              id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, action TEXT,
              score REAL, reason TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS equity_snapshots(
              id INTEGER PRIMARY KEY AUTOINCREMENT, equity REAL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger(
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, kind TEXT NOT NULL,
              position_id INTEGER, amount REAL NOT NULL, cash_after REAL NOT NULL, note TEXT
            );
            """)
            cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(positions)").fetchall()}
            for name, decl in _NEW_COLUMNS.items():
                if name not in cols:
                    self.conn.execute(f"ALTER TABLE positions ADD COLUMN {name} {decl}")
            # Back-fill rows written by older versions (idempotent).
            self.conn.execute("UPDATE positions SET initial_quantity=quantity WHERE initial_quantity IS NULL")
            self.conn.execute("UPDATE positions SET initial_stop=stop_price WHERE initial_stop IS NULL")
            self.conn.execute("""UPDATE positions SET initial_risk=initial_quantity*ABS(entry_price-initial_stop)
                                 WHERE initial_risk IS NULL""")
            self.conn.execute("UPDATE positions SET partial_pnl=0 WHERE partial_pnl IS NULL")
            self.conn.execute("UPDATE positions SET partial_gross=0 WHERE partial_gross IS NULL")
            self.conn.execute("UPDATE positions SET partial_fees=0 WHERE partial_fees IS NULL")
            self.conn.execute("UPDATE positions SET funding_paid=0 WHERE funding_paid IS NULL")
            self.conn.execute("UPDATE positions SET scale_out_done=CASE WHEN quantity<initial_quantity THEN 1 ELSE 0 END WHERE scale_out_done IS NULL")
            # Legacy marks lived in the state table as 'mark:<id>'.
            for r in self.conn.execute("SELECT id, entry_price FROM positions WHERE mark_price IS NULL").fetchall():
                legacy = self.conn.execute("SELECT value FROM state WHERE key=?", (f"mark:{r['id']}",)).fetchone()
                try:
                    mark = float(legacy["value"]) if legacy else float(r["entry_price"])
                except (TypeError, ValueError):
                    mark = float(r["entry_price"])
                self.conn.execute("UPDATE positions SET mark_price=? WHERE id=?", (mark, r["id"]))
            self.conn.execute("DELETE FROM state WHERE key LIKE 'mark:%'")

    def _migrate_ledger(self):
        """Databases created before the ledger existed: record the historic cash difference once."""
        if self.conn.execute("SELECT 1 FROM ledger LIMIT 1").fetchone():
            return
        cash = float(self._state(self.conn, "cash_balance", 0))
        initial = float(self._state(self.conn, "initial_balance", cash))
        if abs(cash - initial) > 1e-9:
            self.conn.execute("INSERT INTO ledger(created_at,kind,position_id,amount,cash_after,note) VALUES(?,?,?,?,?,?)",
                              (utc_now(), "MIGRATION", None, cash - initial, cash,
                               "cash movements before the ledger existed"))

    @staticmethod
    def _state(conn, key, default=None):
        r = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    @staticmethod
    def _put_state(conn, key, value):
        conn.execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, str(value)))

    def _cash_move(self, conn, delta, kind, pid=None, note=None):
        cash = float(self._state(conn, "cash_balance", 0)) + delta
        if not math.isfinite(cash):
            raise ValueError("Non-finite cash balance")
        self._put_state(conn, "cash_balance", repr(cash))
        conn.execute("INSERT INTO ledger(created_at,kind,position_id,amount,cash_after,note) VALUES(?,?,?,?,?,?)",
                     (utc_now(), kind, pid, delta, cash, note))
        return cash

    @staticmethod
    def _equity_of(cash, rows):
        margin = sum(float(r["margin_used"]) for r in rows)
        unreal = 0.0
        for r in rows:
            mark = r["mark_price"] if r["mark_price"] else r["entry_price"]
            unreal += accounting.gross_pnl(r["side"], r["entry_price"], float(mark), r["quantity"])
        return cash + margin + unreal, margin, unreal

    # ------------------------------------------------------------------ key/value state
    def get_state(self, key, default=None):
        with self.lock:
            return self._state(self.conn, key, default)

    def set_state(self, key, value):
        with self.lock:
            self._put_state(self.conn, key, value)

    def refresh_daily_baseline(self):
        today = datetime.now(timezone.utc).date().isoformat()
        with self._tx() as c:
            if self._state(c, "daily_baseline_date") != today:
                cash = float(self._state(c, "cash_balance", config.INITIAL_BALANCE))
                rows = c.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
                self._put_state(c, "daily_baseline", repr(self._equity_of(cash, rows)[0]))
                self._put_state(c, "daily_baseline_date", today)
            return float(self._state(c, "daily_baseline", config.INITIAL_BALANCE))

    def get_peak_equity(self):
        eq = self.get_portfolio()["equity"]
        peak = max(float(self.get_state("peak_equity", eq)), eq)
        self.set_state("peak_equity", peak)
        return peak

    def reset_peak(self, equity=None):
        eq = self.get_portfolio()["equity"] if equity is None else equity
        self.set_state("peak_equity", eq)

    # ------------------------------------------------------------------ reads
    def get_portfolio(self):
        with self.lock:
            cash = float(self._state(self.conn, "cash_balance", self._state(self.conn, "initial_balance", config.INITIAL_BALANCE)))
            rows = self.conn.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
            realized = float(self._state(self.conn, "realized_pnl", 0))
        equity, margin, unreal = self._equity_of(cash, rows)
        return {"cash_balance": cash, "open_margin": margin, "unrealized_pnl": unreal, "realized_pnl": realized,
                "equity": equity, "open_count": len(rows),
                "open_risk": accounting.total_open_risk([dict(r) for r in rows])}

    def get_open_positions(self):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM positions WHERE status='OPEN' ORDER BY opened_at, id").fetchall()
        return [dict(r) for r in rows]

    def get_position(self, pid):
        with self.lock:
            r = self.conn.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    def get_recent_trades(self, limit=50):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM positions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_closed_trades(self, limit=5000):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM positions WHERE status='CLOSED' ORDER BY closed_at DESC, id DESC LIMIT ?",
                                     (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_recent_decisions(self, limit=50):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def equity_history(self, limit=2000):
        with self.lock:
            rows = self.conn.execute("SELECT equity, created_at FROM equity_snapshots ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_ledger(self, limit=200):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ writes: open / stop / mark
    def create_position(self, data):
        """Open a position atomically. Raises ValueError if ANY hard limit would be broken."""
        for k in ("quantity", "entry_price", "stop_price", "target_price", "margin_used"):
            if not accounting.is_valid_price(float(data[k])):
                raise ValueError(f"Invalid {k}")
        if not accounting.is_valid_number(float(data["opening_fee"])) or float(data["opening_fee"]) < 0:
            raise ValueError("Invalid opening_fee")
        side, entry, stop = data["side"], float(data["entry_price"]), float(data["stop_price"])
        if accounting.side_sign(side) * (entry - stop) <= 0:
            raise ValueError("Stop is on the wrong side of entry")
        with self._tx() as c:
            cash = float(self._state(c, "cash_balance", config.INITIAL_BALANCE))
            rows = c.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
            equity, _, _ = self._equity_of(cash, rows)
            positions = [dict(r) for r in rows]
            # never trust a caller-supplied risk number: recompute and keep the larger
            true_risk = accounting.stop_risk(side, entry, stop, float(data["quantity"]), data["source"],
                                             entry_fee=float(data["opening_fee"]))
            risk = max(float(data["risk_amount"]), true_risk)
            today = datetime.now(timezone.utc).date().isoformat()
            if self._state(c, "daily_baseline_date") != today:
                self._put_state(c, "daily_baseline", repr(equity))
                self._put_state(c, "daily_baseline_date", today)
            baseline = float(self._state(c, "daily_baseline", equity))
            cand = {"symbol": data["symbol"], "source": data["source"], "side": side,
                    "margin_used": float(data["margin_used"]), "opening_fee": float(data["opening_fee"]), "risk_amount": risk}
            ok, why = accounting.check_portfolio_limits(
                equity=equity, cash=cash, positions=positions, cand=cand, daily_change=equity - baseline,
                daily_limit=baseline * config.DAILY_LOSS_LIMIT_PCT / 100.0)
            if not ok:
                raise ValueError(why)
            # the entry fee is paid the moment the position opens (already out of equity), so the stored
            # open risk excludes it; only the admission check above counted it
            stored_risk = accounting.stop_risk(side, entry, stop, float(data["quantity"]), data["source"])
            cur = c.execute("""INSERT INTO positions
                (symbol,source,side,quantity,initial_quantity,entry_price,stop_price,target_price,margin_used,
                 risk_amount,initial_risk,opening_fee,status,opened_at,metadata,strategy,initial_stop,
                 mark_price,mark_time,leverage,liquidation_price)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',?,?,?,?,?,?,?,?)""",
                (data["symbol"], data["source"], side, data["quantity"], data["quantity"], entry, stop,
                 data["target_price"], data["margin_used"], stored_risk,
                 float(data.get("initial_risk") or data["quantity"] * abs(entry - stop)), data["opening_fee"],
                 utc_now(), json.dumps(data.get("metadata", {})), data.get("strategy"),
                 data.get("initial_stop") or stop, entry, time.time(),
                 float(data.get("leverage") or 1.0), data.get("liquidation_price")))
            pid = cur.lastrowid
            self._cash_move(c, -(float(data["margin_used"]) + float(data["opening_fee"])), "OPEN", pid,
                            f"{data['source']} {data['symbol']} {side}")
        return self.get_position(pid)

    def update_stop(self, pid, stop, allow_loosen=False):
        """Move the stop. A stop may only tighten (towards/over the price) unless allow_loosen=True."""
        stop = float(stop)
        if not accounting.is_valid_price(stop):
            raise ValueError("Invalid stop")
        with self._tx() as c:
            row = c.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'", (pid,)).fetchone()
            if not row:
                return False
            sign = accounting.side_sign(row["side"])
            if not allow_loosen and sign * (stop - row["stop_price"]) < -1e-12:
                return False
            risk = accounting.stop_risk(row["side"], row["entry_price"], stop, row["quantity"], row["source"])
            c.execute("UPDATE positions SET stop_price=?, risk_amount=? WHERE id=?", (stop, risk, pid))
        return True

    def mark_position(self, pid, price):
        price = float(price)
        if not accounting.is_valid_price(price):
            return False
        with self.lock:
            self.conn.execute("UPDATE positions SET mark_price=?, mark_time=? WHERE id=? AND status='OPEN'",
                              (price, time.time(), pid))
        return True

    # ------------------------------------------------------------------ writes: partial / full close / funding
    def partial_close(self, pid, exit_price, close_qty, reason, fee):
        with self._tx() as c:
            row = c.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'", (pid,)).fetchone()
            if not row or close_qty <= 0 or close_qty >= row["quantity"] or not accounting.is_valid_price(exit_price):
                return None
            if str(reason).startswith("SCALE_OUT") and row["scale_out_done"]:
                return None
            sign = accounting.side_sign(row["side"])
            frac = close_qty / row["quantity"]
            gross = (exit_price - row["entry_price"]) * close_qty * sign
            open_fee_part = row["opening_fee"] * frac
            margin_part = row["margin_used"] * frac
            net = gross - fee - open_fee_part
            self._cash_move(c, margin_part + gross - fee, "PARTIAL_CLOSE", pid, reason)
            self._put_state(c, "realized_pnl", repr(float(self._state(c, "realized_pnl", 0)) + net))
            try:
                meta = json.loads(row["metadata"] or "{}")
            except (TypeError, ValueError):
                meta = {}
            meta["partial_close_reason"] = reason
            new_qty = row["quantity"] - close_qty
            new_risk = accounting.stop_risk(row["side"], row["entry_price"], row["stop_price"], new_qty, row["source"])
            c.execute("""UPDATE positions SET quantity=?, margin_used=?, risk_amount=?, opening_fee=?,
                         partial_pnl=COALESCE(partial_pnl,0)+?, partial_gross=COALESCE(partial_gross,0)+?,
                         partial_fees=COALESCE(partial_fees,0)+?, scale_out_done=1, metadata=? WHERE id=?""",
                      (new_qty, row["margin_used"] - margin_part, new_risk, row["opening_fee"] - open_fee_part,
                       net, gross, fee + open_fee_part, json.dumps(meta), pid))
        return self.get_position(pid)

    def close_position(self, pid, exit_price, reason, closing_fee):
        if not accounting.is_valid_price(exit_price):
            raise ValueError("Invalid exit price")
        with self._tx() as c:
            row = c.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'", (pid,)).fetchone()
            if not row:
                return None
            sign = accounting.side_sign(row["side"])
            gross = (exit_price - row["entry_price"]) * row["quantity"] * sign
            rest_net = gross - row["opening_fee"] - closing_fee
            gross_total = gross + float(row["partial_gross"] or 0)
            fees_total = float(row["partial_fees"] or 0) + row["opening_fee"] + closing_fee
            funding = float(row["funding_paid"] or 0)
            net_total = gross_total - fees_total - funding
            self._cash_move(c, row["margin_used"] + gross - closing_fee, "CLOSE", pid, reason)
            self._put_state(c, "realized_pnl", repr(float(self._state(c, "realized_pnl", 0)) + rest_net))
            c.execute("""UPDATE positions SET status='CLOSED', closed_at=?, exit_price=?, gross_pnl=?, net_pnl=?,
                         closing_fee=?, fees_total=?, exit_reason=?, risk_amount=0 WHERE id=?""",
                      (utc_now(), exit_price, gross_total, net_total, closing_fee, fees_total, reason, pid))
        return self.get_position(pid)

    def apply_funding(self, pid, amount, note=None):
        """amount > 0: the trader PAYS funding, amount < 0: the trader RECEIVES it."""
        amount = float(amount)
        if not math.isfinite(amount):
            raise ValueError("Invalid funding amount")
        with self._tx() as c:
            row = c.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'", (pid,)).fetchone()
            if not row:
                return None
            self._cash_move(c, -amount, "FUNDING", pid, note)
            self._put_state(c, "realized_pnl", repr(float(self._state(c, "realized_pnl", 0)) - amount))
            c.execute("UPDATE positions SET funding_paid=COALESCE(funding_paid,0)+? WHERE id=?", (amount, pid))
        return self.get_position(pid)

    # ------------------------------------------------------------------ misc
    def prune(self, decisions_keep=5000, snapshots_keep=20000):
        with self.lock:
            self.conn.execute("DELETE FROM decisions WHERE id NOT IN (SELECT id FROM decisions ORDER BY id DESC LIMIT ?)", (decisions_keep,))
            self.conn.execute("DELETE FROM equity_snapshots WHERE id NOT IN (SELECT id FROM equity_snapshots ORDER BY id DESC LIMIT ?)", (snapshots_keep,))

    def add_decision(self, symbol, source, action, score, reason):
        with self.lock:
            self.conn.execute("INSERT INTO decisions(symbol,source,action,score,reason,created_at) VALUES(?,?,?,?,?,?)",
                              (symbol, source, action, score, reason, utc_now()))

    def get_performance(self):
        rows = self.get_closed_trades(100000)
        vals = [float(r["net_pnl"] or 0) for r in rows]
        wins = [x for x in vals if x > 0]
        losses = [x for x in vals if x < 0]
        gp, gl = sum(wins), abs(sum(losses))
        rs = [float(r["net_pnl"] or 0) / float(r["initial_risk"]) for r in rows if r["initial_risk"]]
        return {"total_trades": len(vals), "wins": len(wins), "losses": len(losses),
                "win_rate": (len(wins) / len(vals) * 100 if vals else 0),
                "profit_factor": (gp / gl if gl else (None if gp else 0)), "net_pnl": sum(vals),
                "gross_profit": gp, "gross_loss": gl,
                "avg_r": (sum(rs) / len(rs)) if rs else 0.0,
                "total_fees": sum(float(r["fees_total"] or 0) for r in rows),
                "total_funding": sum(float(r["funding_paid"] or 0) for r in rows)}

    def snapshot(self):
        eq = self.get_portfolio()["equity"]
        with self.lock:
            self.conn.execute("INSERT INTO equity_snapshots(equity,created_at) VALUES(?,?)", (eq, utc_now()))
        return eq

    def integrity_report(self):
        """Reconcile cash with the ledger and realised P&L with trade records (used by tests and /api/pro/system).

        All three differences must be ~0.
        """
        with self.lock:
            initial = float(self._state(self.conn, "initial_balance", 0))
            cash = float(self._state(self.conn, "cash_balance", 0))
            ledger_sum = self.conn.execute("SELECT COALESCE(SUM(amount),0) s FROM ledger").fetchone()["s"]
            realized = float(self._state(self.conn, "realized_pnl", 0))
            closed_net = self.conn.execute("SELECT COALESCE(SUM(net_pnl),0) s FROM positions WHERE status='CLOSED'").fetchone()["s"]
            rows = self.conn.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
        margin = sum(float(r["margin_used"]) for r in rows)
        open_fees = sum(float(r["opening_fee"]) for r in rows)
        open_realized = sum(float(r["partial_pnl"] or 0) - float(r["funding_paid"] or 0) for r in rows)
        return {"cash_minus_ledger": cash - (initial + ledger_sum),
                "cash_margin_identity": (cash + margin) - (initial + realized - open_fees),
                "realized_minus_trades": realized - (closed_net + open_realized),
                "cash": cash, "ledger_sum": ledger_sum}

    def storage_info(self):
        on_mount = None
        try:
            on_mount = os.path.ismount(os.path.dirname(os.path.abspath(self.path)))
        except OSError:
            pass
        return {"path": self.path, "fallback_used": self.fallback_used,
                "persistent": self.path == ":memory:" or not self.fallback_used, "on_mount": on_mount}

    def close(self):
        with self.lock:
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            self.conn.close()
