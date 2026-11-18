#!/usr/bin/env python3
"""Print what the edge collector has stored (read-only):  python scripts/edge_inspect.py [path-to-edge_data.db]"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge.store import default_path   # noqa: E402


def fmt(ms):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ms / 1000)) if ms else "-"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else default_path()
    if not os.path.exists(path):
        print("no such database:", path)
        return 1
    db = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    rows = db.execute("SELECT kind, symbol, period, COUNT(*), MIN(ts), MAX(ts) FROM edge_series "
                      "GROUP BY kind, symbol, period ORDER BY symbol, kind, period").fetchall()
    print("%-18s %-10s %-4s %7s  %-19s  %-19s" % ("kind", "symbol", "per", "rows", "first (UTC)", "last (UTC)"))
    for kind, sym, per, n, lo, hi in rows:
        print("%-18s %-10s %-4s %7d  %-19s  %-19s" % (kind, sym, per or "-", n, fmt(lo), fmt(hi)))
    print("total rows:", sum(r[3] for r in rows), "| file:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
