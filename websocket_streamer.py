"""Binance Futures all-market ticker stream (public). Prices carry a timestamp so a dead stream
can never feed stale prices into stop-loss or entry decisions."""
import asyncio
import inspect
import json
import logging
import time

import config

try:
    import websockets
except ImportError:           # the engine then runs on REST prices only
    websockets = None

log = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 20
PING_TIMEOUT_SECONDS = 20
RECONNECT_MIN_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0

live_prices = {}    # {"BTCUSDT": (price, monotonic_timestamp)}
stream_state = {"connected": False, "last_message": 0.0}


def get_live_price(symbol, max_age=None):
    """Latest streamed price, or None if unknown OR older than PRICE_MAX_AGE_SECONDS."""
    if not symbol:
        return None
    item = live_prices.get(str(symbol).upper())
    if not item:
        return None
    price, ts = item
    max_age = config.PRICE_MAX_AGE_SECONDS if max_age is None else max_age
    if time.monotonic() - ts > max_age:
        return None
    return price


async def _call_callback(callback, symbol, price):
    try:
        result = callback(symbol, price)
        if inspect.isawaitable(result):
            await result
    except Exception as error:
        log.warning("WS callback error: %s", error)


async def _handle_message(raw_message, callback):
    try:
        data = json.loads(raw_message)
    except (ValueError, TypeError):
        return
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return
    now = time.monotonic()
    stream_state["last_message"] = now
    for ticker in data:
        try:
            symbol, price = ticker["s"], float(ticker["c"])
        except (KeyError, TypeError, ValueError):
            continue
        if not price > 0 or price != price or price == float("inf"):
            continue
        live_prices[symbol] = (price, now)
        if callback is not None:
            await _call_callback(callback, symbol, price)


async def start_price_stream(callback=None):
    """Keep live_prices updated; reconnect with exponential backoff. Runs until cancelled."""
    if websockets is None:
        log.warning("websockets package missing: using REST prices only")
        return
    delay = RECONNECT_MIN_DELAY
    while True:
        try:
            async with websockets.connect(config.WS_URL, ping_interval=PING_INTERVAL_SECONDS,
                                          ping_timeout=PING_TIMEOUT_SECONDS, close_timeout=5) as connection:
                stream_state["connected"] = True
                log.info("WS connected")
                async for raw_message in connection:
                    delay = RECONNECT_MIN_DELAY
                    await _handle_message(raw_message, callback)
            log.warning("WS closed by server")
        except asyncio.CancelledError:
            stream_state["connected"] = False
            raise
        except Exception as error:
            log.warning("WS error: %s", error)
        stream_state["connected"] = False
        await asyncio.sleep(delay)
        delay = min(delay * 2.0, RECONNECT_MAX_DELAY)
