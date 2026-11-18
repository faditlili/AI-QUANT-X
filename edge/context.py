"""Point-in-time feature snapshot for one symbol, built ONLY from rows with available_at <= as_of_ms.

Not wired into the Legacy trading path (Phase 2 = data only). Every component is None when unavailable and
is listed in `missing`; components older than `max_age_ms` are listed in `stale`. Nothing is defaulted.
"""
from . import liquidations, orderflow
from .client import PERIOD_MS


def edge_snapshot(store, symbol, as_of_ms, period="5m", oi_bars_back=12, cvd_bars_n=12,
                  liq_window_ms=3_600_000, price_change_pct=None, max_age_ms=None):
    as_of_ms = int(as_of_ms)
    max_age = max_age_ms if max_age_ms is not None else 3 * PERIOD_MS[period]
    snap, missing, stale = {"symbol": symbol, "as_of": as_of_ms}, [], []

    def last(kind, per, n=1):
        rows = store.fetch(kind, symbol, per, as_of_ms=as_of_ms, limit=n)
        return rows

    def note(name, rows):
        if not rows:
            missing.append(name)
        elif as_of_ms - rows[-1]["available_at"] > max_age:
            stale.append(name)

    oi = last("oi_hist", period, oi_bars_back + 1)
    note("oi", oi)
    snap["oi_change_pct"] = orderflow.oi_change_pct(oi, oi_bars_back) if oi else None
    snap["oi_latest"] = oi[-1]["oi"] if oi else None

    taker = last("taker", period, cvd_bars_n)
    note("taker", taker)
    if taker and all("buy_vol" in r for r in taker):
        snap["taker_imbalance"] = orderflow.taker_imbalance(sum(r["buy_vol"] for r in taker), sum(r["sell_vol"] for r in taker))
    else:
        snap["taker_imbalance"] = None
    snap["taker_ratio_latest"] = taker[-1]["ratio"] if taker else None

    ls = last("ls_global_account", period)
    note("long_short", ls)
    snap["long_short_ratio"] = ls[-1]["ratio"] if ls else None

    prem = last("premium", "")
    note("premium", prem)
    snap["mark_price"] = prem[-1]["mark"] if prem else None
    snap["funding"] = prem[-1]["funding"] if prem else None
    snap["premium_pct"] = prem[-1]["premium_pct"] if prem else None

    cvd = last("cvd", period, cvd_bars_n)
    note("cvd", cvd)
    snap["cvd_sum"] = sum(b["delta"] for b in cvd) if cvd else None
    snap["cvd_last_delta"] = cvd[-1]["delta"] if cvd else None

    liq = store.fetch("liq", symbol, "", start_ms=as_of_ms - liq_window_ms, end_ms=as_of_ms, as_of_ms=as_of_ms)
    snap["liquidations"] = liquidations.summarize(liq, as_of_ms - liq_window_ms, as_of_ms) if liq else None
    snap["oi_price_quadrant"] = orderflow.oi_price_quadrant(price_change_pct, snap["oi_change_pct"])
    snap["missing"], snap["stale"] = missing, stale
    return snap
