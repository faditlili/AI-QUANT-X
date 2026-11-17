"""Dynamic watch-list from Binance Futures 24h tickers (public data)."""
import logging

import aiohttp

import config

log = logging.getLogger(__name__)

MIN_QUOTE_VOLUME = 50000000.0
MIN_ABS_CHANGE_PERCENT = 3.0
TOP_COUNT = 50
REQUEST_TIMEOUT_SECONDS = 15


async def get_top_symbols():
    """Top liquid and volatile USDT perpetuals, highest quote volume first.

    Returns None when the data could not be fetched or nothing passed the filters, so the caller
    keeps its current list and can tell that no refresh happened (instead of "refreshing" to a fallback).
    """
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": config.USER_AGENT}) as session:
            url = config.BINANCE_FUTURES_BASE_URL + config.FUTURES_TICKER_24H_PATH
            async with session.get(url) as response:
                if response.status != 200:
                    log.warning("Symbol scanner: HTTP %s", response.status)
                    return None
                tickers = await response.json()
    except Exception as error:
        log.warning("Symbol scanner failed: %s", error)
        return None
    if not isinstance(tickers, list):
        return None
    candidates = []
    for t in tickers:
        try:
            symbol = t["symbol"]
            if not symbol.endswith("USDT") or any(k in symbol for k in config.EXCLUDED_KEYWORDS):
                continue
            qv, chg = float(t["quoteVolume"]), float(t["priceChangePercent"])
        except (KeyError, TypeError, ValueError):
            continue
        if qv > MIN_QUOTE_VOLUME and abs(chg) > MIN_ABS_CHANGE_PERCENT:
            candidates.append((qv, symbol))
    if not candidates:
        log.info("Symbol scanner: nothing passed the filters; keeping the current list")
        return None
    candidates.sort(reverse=True)
    return [s for _, s in candidates[:TOP_COUNT]]
