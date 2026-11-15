# websocket_streamer.py
#
# Add this line to requirements.txt:
#     websockets

import asyncio
import inspect
import json

import websockets

WS_URL = "wss://fstream.binance.com/ws/!ticker@arr"
PING_INTERVAL_SECONDS = 20
PING_TIMEOUT_SECONDS = 20
RECONNECT_MIN_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0

# Shared in-memory state: {"BTCUSDT": 97123.5, ...}
live_prices = {}


def get_live_price(symbol):
    """Return the latest streamed price for a symbol from memory (no network request).

    Returns None if the symbol has not been received yet.
    """
    if not symbol:
        return None
    return live_prices.get(str(symbol).upper())


async def _call_callback(callback, symbol, price):
    """Call the callback (sync or async) without letting its errors kill the stream."""
    try:
        result = callback(symbol, price)
        if inspect.isawaitable(result):
            await result
    except Exception as error:
        print("[WS] callback error: " + str(error))


async def _handle_message(raw_message, callback):
    """Parse one ticker-array message and update live_prices."""
    try:
        data = json.loads(raw_message)
    except (ValueError, TypeError):
        return

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return

    for ticker in data:
        try:
            symbol = ticker["s"]
            price = float(ticker["c"])
        except (KeyError, TypeError, ValueError):
            continue

        live_prices[symbol] = price
        if callback is not None:
            await _call_callback(callback, symbol, price)


async def start_price_stream(callback=None):
    """Connect to the Binance Futures all-market ticker stream and keep live_prices updated.

    callback(symbol, price) is optional and may be a normal or an async function.
    Reconnects automatically (with exponential backoff) when the connection drops.
    Runs forever; cancel the task to stop it.
    """
    delay = RECONNECT_MIN_DELAY

    while True:
        try:
            print("[WS] connecting to " + WS_URL)
            async with websockets.connect(
                WS_URL,
                ping_interval=PING_INTERVAL_SECONDS,
                ping_timeout=PING_TIMEOUT_SECONDS,
                close_timeout=5,
            ) as connection:
                print("[WS] connected")
                async for raw_message in connection:
                    delay = RECONNECT_MIN_DELAY
                    await _handle_message(raw_message, callback)
            print("[WS] connection closed by server")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print("[WS] connection error: " + str(error))

        print("[WS] reconnecting in " + str(round(delay, 1)) + "s")
        await asyncio.sleep(delay)
        delay = min(delay * 2.0, RECONNECT_MAX_DELAY)
