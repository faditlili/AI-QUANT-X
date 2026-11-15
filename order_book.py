import aiohttp

BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/depth"
DEPTH_LIMIT = 50
WALL_RANGE_PCT = 0.01
STRONG_THRESHOLD = 0.60
WEAK_THRESHOLD = 0.40
REQUEST_TIMEOUT_SECONDS = 10


async def fetch_order_book(symbol, limit=DEPTH_LIMIT, session=None):
    """Fetch the order book from Binance Futures. Returns a dict or None."""
    params = {"symbol": symbol.upper(), "limit": limit}
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(timeout=timeout)
    try:
        async with session.get(BINANCE_FUTURES_URL, params=params, timeout=timeout) as response:
            if response.status != 200:
                return None
            return await response.json()
    except Exception:
        return None
    finally:
        if own_session:
            await session.close()


def _strength_label(ratio):
    """Convert a 0..1 pressure ratio into STRONG / NEUTRAL / WEAK."""
    if ratio >= STRONG_THRESHOLD:
        return "STRONG"
    if ratio <= WEAK_THRESHOLD:
        return "WEAK"
    return "NEUTRAL"


def calculate_liquidity_walls(order_book):
    """Compute bid/ask volume within 1% of the current price and the imbalance ratio."""
    bids = [(float(price), float(qty)) for price, qty in order_book.get("bids", [])]
    asks = [(float(price), float(qty)) for price, qty in order_book.get("asks", [])]

    if not bids or not asks:
        return None

    best_bid = max(price for price, _ in bids)
    best_ask = min(price for price, _ in asks)
    mid_price = (best_bid + best_ask) / 2.0

    lower_bound = mid_price * (1.0 - WALL_RANGE_PCT)
    upper_bound = mid_price * (1.0 + WALL_RANGE_PCT)

    bid_volume = sum(qty for price, qty in bids if price >= lower_bound)
    ask_volume = sum(qty for price, qty in asks if price <= upper_bound)

    total = bid_volume + ask_volume
    if total <= 0:
        return None

    imbalance_ratio = bid_volume / total
    return {
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "imbalance_ratio": imbalance_ratio,
    }


async def get_order_book_imbalance(symbol, session=None):
    """Main entry point.

    Returns:
        {"imbalance_ratio": 0.65, "support_strength": "STRONG", "resistance_strength": "WEAK"}
    On any failure it returns a neutral result (ratio 0.5, NEUTRAL / NEUTRAL).
    """
    neutral = {
        "imbalance_ratio": 0.5,
        "support_strength": "NEUTRAL",
        "resistance_strength": "NEUTRAL",
    }

    order_book = await fetch_order_book(symbol, DEPTH_LIMIT, session)
    if not order_book:
        return neutral

    try:
        walls = calculate_liquidity_walls(order_book)
    except (ValueError, TypeError):
        return neutral

    if walls is None:
        return neutral

    ratio = walls["imbalance_ratio"]
    support_strength = _strength_label(ratio)
    resistance_strength = _strength_label(1.0 - ratio)

    return {
        "imbalance_ratio": round(ratio, 4),
        "support_strength": support_strength,
        "resistance_strength": resistance_strength,
    }
