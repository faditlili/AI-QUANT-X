#!/usr/bin/env python3
"""Standalone edge-data collector (public data only). Does nothing unless FF_ADVANCED_DATA=true.

  FF_ADVANCED_DATA=true EDGE_SYMBOLS=BTCUSDT,ETHUSDT python scripts/edge_collect.py
Env: EDGE_SYMBOLS (default BTCUSDT,ETHUSDT,SOLUSDT), EDGE_INTERVAL_SECONDS (default 300),
     EDGE_DB_PATH (default: edge_data.db next to DB_PATH), EDGE_LIQUIDATIONS (default true).
Needs the real aiohttp (+ websockets for liquidations). Not exercised against live Binance in the build sandbox.
"""
import asyncio
import logging
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge import flags                                   # noqa: E402
from edge.client import EdgeDataClient                   # noqa: E402
from edge.collector import collect_once                  # noqa: E402
from edge import liquidations                            # noqa: E402
from edge.store import EdgeStore                         # noqa: E402

log = logging.getLogger("edge_collect")


async def main():
    if not flags.enabled("ADVANCED_DATA"):
        print("FF_ADVANCED_DATA is off: nothing to do (Legacy Core unaffected).")
        return 0
    from market_data import MarketData
    symbols = [s.strip().upper() for s in os.getenv("EDGE_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",") if s.strip()]
    interval = float(os.getenv("EDGE_INTERVAL_SECONDS", "300"))
    store, md = EdgeStore(), MarketData()
    client, stop = EdgeDataClient.from_market_data(md), asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    tasks = []
    if os.getenv("EDGE_LIQUIDATIONS", "true").lower() in ("1", "true", "yes", "on"):
        wanted = set(symbols)
        def on_event(event):
            if event["symbol"] in wanted:
                store.insert_rows([liquidations.to_row(event, int(time.time() * 1000))])
        tasks.append(asyncio.create_task(liquidations.run_stream(on_event, stop=stop)))
    try:
        while not stop.is_set():
            res = await collect_once(client, store, symbols)
            log.info("cycle: +%d rows, %d errors, incomplete cvd: %s", res["inserted"], len(res["errors"]), res["incomplete_cvd"])
            for e in res["errors"][:5]:
                log.warning("  %s", e)
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except asyncio.TimeoutError:
                pass
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await md.close()
        store.close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(asyncio.run(main()))
