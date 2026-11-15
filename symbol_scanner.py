# symbol_scanner.py
#
# No new line is needed in requirements.txt (aiohttp is already used by the bot).

import aiohttp

TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"
MIN_QUOTE_VOLUME = 50000000.0
MIN_ABS_CHANGE_PERCENT = 3.0
TOP_COUNT = 50
REQUEST_TIMEOUT_SECONDS = 15


def _fallback_symbols():
    """Return the default symbol list from config.SYMBOLS (empty list if unavailable)."""
    try:
        import config
        return list(getattr(config, "SYMBOLS", []))
    except Exception:
        return []


async def get_top_symbols():
    """Scan Binance Futures and return the top 50 liquid and volatile USDT symbols.

    Filters: symbol ends with USDT, 24h quote volume > 50M USD,
    absolute 24h price change > 3%. Sorted by quote volume (highest first).
    On any failure (or if nothing passes the filters) it returns config.SYMBOLS.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(TICKER_URL) as response:
                if response.status != 200:
                    print("[SCANNER] bad status: " + str(response.status))
                    return _fallback_symbols()
                tickers = await response.json()

        if not isinstance(tickers, list):
            return _fallback_symbols()

        candidates = []
        for ticker in tickers:
            try:
                symbol = ticker["symbol"]
                if not symbol.endswith("USDT"):
                    continue
                quote_volume = float(ticker["quoteVolume"])
                change_percent = float(ticker["priceChangePercent"])
            except (KeyError, TypeError, ValueError):
                continue

            if quote_volume > MIN_QUOTE_VOLUME and abs(change_percent) > MIN_ABS_CHANGE_PERCENT:
                candidates.append((quote_volume, symbol))

        if not candidates:
            print("[SCANNER] no symbol passed the filters, using default list")
            return _fallback_symbols()

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [symbol for _, symbol in candidates[:TOP_COUNT]]
    except Exception as error:
        print("[SCANNER] failed: " + str(error))
        return _fallback_symbols()
