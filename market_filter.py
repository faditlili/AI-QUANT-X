"""Market regime and liquidity filters using source-specific public data."""
import config
from indicators import calculate_indicators, direction

async def is_market_bullish(market_data,source="spot"):
    for symbol in config.DIRECTION_SYMBOLS:
        try:
            frame=await market_data.get_klines(symbol,"4h",100,source)
            if direction(calculate_indicators(frame))!="BULLISH":
                return False
        except Exception:
            return False
    return True

async def is_symbol_liquid(market_data,symbol,source="futures"):
    try:
        ticker=await market_data.get_ticker_24h(symbol,source)
        return bool(ticker and ticker["quote_volume"]>=config.MIN_24H_VOLUME_USDT)
    except Exception:
        return False
