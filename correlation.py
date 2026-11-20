"""Correlation filter: avoid stacking several positions that are really the same bet."""
import logging

import numpy as np

import config

log = logging.getLogger(__name__)

# Correlation is measured over the last 50 hourly candles. The request itself must use KLINE_LIMIT:
# MarketData.get_klines() rejects anything below MIN_CANDLES_REQUIRED (60), so asking for 50 made every
# entry fail closed as soon as ONE position was open. KLINE_LIMIT also hits the cache filled by the analysis.
WINDOW = 50


async def is_highly_correlated(new_symbol, open_symbols, market_data, threshold=0.8, source="futures"):
    """Return (blocked, reason).

    Uses the SAME market (`source`) as the new trade. If the new symbol's data cannot be loaded the
    entry is BLOCKED (fail closed); an open symbol whose data fails is skipped with a warning.
    """
    if not open_symbols:
        return False, None
    try:
        new_df = await market_data.get_klines(new_symbol, "1h", config.KLINE_LIMIT, source)
        new_returns = new_df["close"].tail(WINDOW).pct_change().dropna()
    except Exception as exc:
        return True, f"Correlation data unavailable for {new_symbol}: {exc}"
    for symbol in open_symbols:
        if symbol == new_symbol:
            continue
        try:
            sym_df = await market_data.get_klines(symbol, "1h", config.KLINE_LIMIT, source)
            sym_returns = sym_df["close"].tail(WINDOW).pct_change().dropna()
            n = min(len(new_returns), len(sym_returns))
            if n < 20:
                continue
            corr = np.corrcoef(new_returns.iloc[-n:], sym_returns.iloc[-n:])[0, 1]
            if np.isfinite(corr) and corr >= threshold:
                return True, f"Highly correlated with {symbol} ({corr*100:.0f}%)"
        except Exception as exc:
            log.warning("Correlation check skipped for %s: %s", symbol, exc)
    return False, None
