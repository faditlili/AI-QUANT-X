"""Parsers for Binance public-data archive files (data.binance.vision, USD-M futures).

UNVERIFIED AGAINST REAL FILES: written from the documented layouts and covered by synthetic-sample tests
only (this build had no network). Parsers are header-driven and tolerant of column order; a column that is
missing yields None for that field - never a default. Run scripts/edge_backfill.py on a connected machine
and check the first file by eye before trusting a long backfill.
"""
import csv
import io
import zipfile
from datetime import datetime, timezone

from .store import make_row

BASE = "https://data.binance.vision/data/futures/um"


def url_for(dataset, symbol, day=None, month=None):
    """e.g. url_for("metrics", "BTCUSDT", day="2024-05-01"); datasets: metrics, aggTrades, fundingRate."""
    if dataset not in ("metrics", "aggTrades", "fundingRate"):
        raise ValueError("unknown dataset %r" % (dataset,))
    if (day is None) == (month is None):
        raise ValueError("give exactly one of day / month")
    freq = "daily" if day else "monthly"
    return "%s/%s/%s/%s/%s-%s-%s.zip" % (BASE, freq, dataset, symbol, symbol, dataset, day or month)


def read_zip_csv(path_or_bytes):
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    with zipfile.ZipFile(src) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError("expected exactly one csv in archive, found %d" % len(names))
        return z.read(names[0]).decode("utf-8")


def _time_ms(value):
    s = str(value).strip()
    if s.isdigit():
        n = int(s)
        return n * 1000 if n < 10 ** 11 else n
    return int(datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _f(value):
    if value in (None, ""):
        return None
    x = float(value)
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def _dict_rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def parse_metrics(text, symbol, period_ms=300_000, period="5m"):
    """`metrics` daily file -> edge rows (oi_hist, ls_top_account, ls_top_position, ls_global_account, taker).
    Mapping of archive columns (assumed): count_toptrader_long_short_ratio = top ACCOUNT ratio,
    sum_toptrader_long_short_ratio = top POSITION ratio, count_long_short_ratio = global account ratio."""
    rows = []
    for r in _dict_rows(text):
        ts = _time_ms(r["create_time"])
        oi, oiv = _f(r.get("sum_open_interest")), _f(r.get("sum_open_interest_value"))
        if oi is not None:
            rows.append(make_row("oi_hist", symbol, ts, {"oi": oi, "oi_value": oiv}, period, period_ms))
        for kind, col in (("ls_top_account", "count_toptrader_long_short_ratio"),
                          ("ls_top_position", "sum_toptrader_long_short_ratio"),
                          ("ls_global_account", "count_long_short_ratio")):
            v = _f(r.get(col))
            if v is not None:
                rows.append(make_row(kind, symbol, ts, {"ratio": v}, period, period_ms))
        t = _f(r.get("sum_taker_long_short_vol_ratio"))
        if t is not None:
            rows.append(make_row("taker", symbol, ts, {"ratio": t}, period, period_ms))
    return rows


def parse_funding(text, symbol):
    rows = []
    for r in _dict_rows(text):
        rate = _f(r.get("last_funding_rate"))
        if rate is not None:
            ts = _time_ms(r["calc_time"])
            rows.append(make_row("funding_hist", symbol, ts, {"funding": rate}))
    return rows


def parse_agg_trades(text):
    """aggTrades file -> trade dicts compatible with orderflow.cvd_bars. Handles files with or without a header."""
    lines = text.strip().splitlines()
    if not lines:
        return []
    header = not lines[0].split(",")[0].strip().lstrip("-").isdigit()
    out = []
    for cols in csv.reader(lines[1:] if header else lines):
        if len(cols) < 7:
            raise ValueError("aggTrades row has %d columns, expected 7" % len(cols))
        price, qty = float(cols[1]), float(cols[2])
        if not (price > 0 and qty >= 0):
            raise ValueError("invalid aggTrades row: %r" % (cols,))
        out.append({"id": int(cols[0]), "ts": _time_ms(cols[5]), "price": price, "qty": qty,
                    "buyer_is_maker": cols[6].strip().lower() == "true"})
    return out
