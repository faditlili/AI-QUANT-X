"""Separate SQLite file for edge data (never the trading database / ledger).

One generic table. Every row has:
  ts            exchange timestamp of the observation (ms)
  available_at  earliest moment the value could have been KNOWN (ms) - queries with `as_of_ms`
                only ever return rows with available_at <= as_of_ms (no look-ahead).
Rules for available_at (conservative, documented assumptions):
  * period series (OI hist, long/short, taker volume): ts + period length, because Binance does not
    state whether `timestamp` marks the start or the end of the bucket; we assume the worse case.
  * point snapshots (open interest now, premium index, liquidation events): ts.
  * data collected LIVE additionally uses max(rule, fetched_at): we cannot have known it before we asked.
    Backfilled history (fetched_at=None) uses the rule only.
"""
import json
import os
import sqlite3
import threading

import config


def default_path():
    explicit = os.getenv("EDGE_DB_PATH")
    if explicit:
        return explicit
    return os.path.join(os.path.dirname(config.DB_PATH) or ".", "edge_data.db")


def make_row(kind, symbol, ts, payload, period="", lag_ms=0, uid="", fetched_at=None):
    avail = int(ts) + int(lag_ms)
    if fetched_at is not None:
        avail = max(avail, int(fetched_at))
    return {"kind": kind, "symbol": symbol, "period": period or "", "ts": int(ts), "available_at": avail,
            "uid": str(uid), "payload": payload}


class EdgeStore:
    def __init__(self, path=None):
        self.path = path or default_path()
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS edge_series("
            "kind TEXT NOT NULL, symbol TEXT NOT NULL, period TEXT NOT NULL DEFAULT '', "
            "ts INTEGER NOT NULL, available_at INTEGER NOT NULL, uid TEXT NOT NULL DEFAULT '', "
            "payload TEXT NOT NULL, PRIMARY KEY(kind, symbol, period, ts, uid))")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_edge_avail ON edge_series(kind, symbol, period, available_at)")
        self._db.commit()

    def insert_rows(self, rows):
        """Idempotent (duplicates ignored). Returns the number of NEW rows."""
        data = [(r["kind"], r["symbol"], r["period"], r["ts"], r["available_at"], r["uid"],
                 json.dumps(r["payload"], separators=(",", ":"), sort_keys=True)) for r in rows]
        if not data:
            return 0
        with self._lock:
            before = self._db.total_changes
            self._db.executemany("INSERT OR IGNORE INTO edge_series VALUES (?,?,?,?,?,?,?)", data)
            self._db.commit()
            return self._db.total_changes - before

    def fetch(self, kind, symbol, period="", start_ms=None, end_ms=None, as_of_ms=None, limit=None):
        """Rows oldest-first. as_of_ms enforces point-in-time visibility; limit keeps the NEWEST rows."""
        sql = "SELECT ts, available_at, uid, payload FROM edge_series WHERE kind=? AND symbol=? AND period=?"
        args = [kind, symbol, period or ""]
        if start_ms is not None:
            sql += " AND ts>=?"; args.append(int(start_ms))
        if end_ms is not None:
            sql += " AND ts<=?"; args.append(int(end_ms))
        if as_of_ms is not None:
            sql += " AND available_at<=?"; args.append(int(as_of_ms))
        sql += " ORDER BY ts DESC, uid DESC"
        if limit is not None:
            sql += " LIMIT ?"; args.append(int(limit))
        with self._lock:
            found = self._db.execute(sql, args).fetchall()
        return [{"ts": ts, "available_at": av, "uid": uid, **json.loads(p)} for ts, av, uid, p in reversed(found)]

    def count(self, kind=None):
        with self._lock:
            if kind:
                return self._db.execute("SELECT COUNT(*) FROM edge_series WHERE kind=?", (kind,)).fetchone()[0]
            return self._db.execute("SELECT COUNT(*) FROM edge_series").fetchone()[0]

    def close(self):
        with self._lock:
            self._db.close()
