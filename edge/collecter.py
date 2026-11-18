"""One collection cycle: pull public data for each symbol and store it (idempotent, errors isolated).

Standalone: run via scripts/edge_collect.py. Nothing here touches the trading database or any order endpoint.
"""
import logging
import time

from . import orderflow
from .client import PERIOD_MS
from .store import make_row

log = logging.getLogger(__name__)


async def collect_once(client, store, symbols, now_ms=None, period="5m", hist_limit=12, cvd_bars_n=2):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    lag = PERIOD_MS[period]
    inserted, errors, incomplete = 0, [], []

    async def guard(symbol, what, coro):
        try:
            return await coro
        except Exception as exc:          # one failing endpoint must not stop the others
            errors.append((symbol, what, "%s: %s" % (type(exc).__name__, exc)))
            return None

    for symbol in symbols:
        rows = []
        p = await guard(symbol, "premium", client.premium_index(symbol))
        if p:
            rows.append(make_row("premium", symbol, p["ts"], {k: p[k] for k in ("mark", "index", "funding", "premium_pct", "next_funding_ts")},
                                 fetched_at=now_ms))
        o = await guard(symbol, "oi_now", client.open_interest_now(symbol))
        if o:
            rows.append(make_row("oi_now", symbol, o["ts"], {"oi": o["oi"]}, fetched_at=now_ms))
        for r in await guard(symbol, "oi_hist", client.open_interest_hist(symbol, period, hist_limit)) or []:
            rows.append(make_row("oi_hist", symbol, r["ts"], {"oi": r["oi"], "oi_value": r["oi_value"]}, period, lag, fetched_at=now_ms))
        for kind in ("global_account", "top_account", "top_position"):
            for r in await guard(symbol, "ls_" + kind, client.long_short_ratio(symbol, kind, period, hist_limit)) or []:
                rows.append(make_row("ls_" + kind, symbol, r["ts"], {"ratio": r["ratio"], "long": r["long"], "short": r["short"]},
                                     period, lag, fetched_at=now_ms))
        for r in await guard(symbol, "taker", client.taker_ratio(symbol, period, hist_limit)) or []:
            rows.append(make_row("taker", symbol, r["ts"], {"ratio": r["ratio"], "buy_vol": r["buy_vol"], "sell_vol": r["sell_vol"]},
                                 period, lag, fetched_at=now_ms))

        # CVD: only buckets that already ended, and only when the trade window was fetched COMPLETELY
        # (a partial bucket stored once would be permanent because rows are insert-once).
        end = (now_ms // lag) * lag
        start = end - lag * cvd_bars_n
        res = await guard(symbol, "agg_trades", client.agg_trades(symbol, start, end - 1))
        if res is not None:
            if not res["complete"]:
                incomplete.append(symbol)
            else:
                for b in orderflow.closed_bars(orderflow.cvd_bars(res["trades"], lag), end):
                    rows.append(make_row("cvd", symbol, b["bucket_start"],
                                         {k: b[k] for k in ("buy", "sell", "delta", "trades")}, period, lag, fetched_at=now_ms))
        inserted += store.insert_rows(rows)
    return {"inserted": inserted, "errors": errors, "incomplete_cvd": incomplete}
