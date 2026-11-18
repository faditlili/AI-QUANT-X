"""Liquidation events from Binance's public `!forceOrder@arr` WebSocket stream.

IMPORTANT LIMITS (Binance behaviour): for each symbol the stream pushes at most ONE liquidation per
1000 ms (the latest). During a cascade the real volume is therefore UNDER-counted - treat totals as a
lower bound/sample, never as the exact liquidated amount. There is no public REST history, so a
history only exists from the day the collector started running.
"""
import asyncio
import json
import logging

from .store import make_row

log = logging.getLogger(__name__)
DEFAULT_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"


def parse_force_order(message):
    """Return a normalised event dict, or None for anything that is not a valid liquidation event.
    side SELL = a LONG position was liquidated (forced sell); BUY = a SHORT was liquidated."""
    try:
        if isinstance(message, (str, bytes)):
            message = json.loads(message)
        if isinstance(message, dict) and "data" in message:
            message = message["data"]
        if not isinstance(message, dict) or message.get("e") != "forceOrder":
            return None
        o = message["o"]
        side = o["S"]
        if side not in ("BUY", "SELL"):
            return None
        price = float(o.get("ap") or 0) or float(o["p"])
        qty = float(o.get("z") or 0) or float(o["q"])
        ts = int(o["T"])
        if not (price > 0 and qty > 0 and ts > 0) or price != price or qty != qty:
            return None
        return {"symbol": str(o["s"]).upper(), "ts": ts, "side": side,
                "liquidated": "LONG" if side == "SELL" else "SHORT",
                "price": price, "qty": qty, "notional": price * qty}
    except (KeyError, TypeError, ValueError):
        return None


def summarize(events, start_ms, end_ms):
    """Notional liquidated per side inside [start_ms, end_ms] (a lower bound, see module docstring)."""
    out = {"long_notional": 0.0, "short_notional": 0.0, "events": 0}
    for e in events:
        if start_ms <= e["ts"] <= end_ms:
            out["long_notional" if e["liquidated"] == "LONG" else "short_notional"] += e["notional"]
            out["events"] += 1
    return out


async def run_stream(on_event, url=DEFAULT_URL, connect=None, stop=None, max_backoff=60.0, sleep=asyncio.sleep):
    """Reconnecting consumer. `on_event(event)` may be sync or async. Stops when `stop` (asyncio.Event) is set.
    `connect` defaults to websockets.connect (imported lazily so the package works without it)."""
    if connect is None:
        import websockets
        connect = websockets.connect
    stop = stop or asyncio.Event()
    delay = 1.0
    while not stop.is_set():
        try:
            async with connect(url) as ws:
                delay = 1.0
                async for raw in ws:
                    event = parse_force_order(raw)
                    if event is not None:
                        result = on_event(event)
                        if asyncio.iscoroutine(result):
                            await result
                    if stop.is_set():
                        return
        except Exception as exc:
            log.warning("liquidation stream dropped: %s", exc)
        if stop.is_set():
            return
        await sleep(delay)
        delay = min(delay * 2, max_backoff)


def to_row(event, received_ms):
    """Store row for a liquidation event (live: available only once we received it)."""
    uid = "%s:%s:%s" % (event["side"], event["qty"], event["price"])
    return make_row("liq", event["symbol"], event["ts"],
                    {k: event[k] for k in ("side", "liquidated", "price", "qty", "notional")},
                    uid=uid, fetched_at=received_ms)
