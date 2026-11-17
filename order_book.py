"""Order-book imbalance from the SAME market (spot/futures) as the trade being analysed."""
import logging

log = logging.getLogger(__name__)

DEPTH_LIMIT = 50
WALL_RANGE_PCT = 0.01
STRONG_THRESHOLD = 0.60
WEAK_THRESHOLD = 0.40


def _strength_label(ratio):
    if ratio >= STRONG_THRESHOLD:
        return "STRONG"
    if ratio <= WEAK_THRESHOLD:
        return "WEAK"
    return "NEUTRAL"


def calculate_liquidity_walls(order_book):
    """Bid/ask volume within 1% of mid price and the imbalance ratio. None if the book is unusable."""
    bids = [(float(p), float(q)) for p, q in order_book.get("bids", [])]
    asks = [(float(p), float(q)) for p, q in order_book.get("asks", [])]
    if not bids or not asks:
        return None
    best_bid = max(p for p, _ in bids)
    best_ask = min(p for p, _ in asks)
    if best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:      # crossed/invalid book
        return None
    mid = (best_bid + best_ask) / 2.0
    bid_volume = sum(q for p, q in bids if p >= mid * (1.0 - WALL_RANGE_PCT))
    ask_volume = sum(q for p, q in asks if p <= mid * (1.0 + WALL_RANGE_PCT))
    total = bid_volume + ask_volume
    if total <= 0:
        return None
    return {"bid_volume": bid_volume, "ask_volume": ask_volume, "imbalance_ratio": bid_volume / total}


async def get_order_book_imbalance(symbol, market, source="futures"):
    """Return {"imbalance_ratio","support_strength","resistance_strength"} or None when unavailable.

    None means "no opinion": it is NOT converted into a neutral 0.5 reading.
    """
    try:
        book = await market.get_depth(symbol, source, DEPTH_LIMIT)
        walls = calculate_liquidity_walls(book)
    except Exception as exc:
        log.debug("Order book unavailable %s/%s: %s", source, symbol, exc)
        return None
    if walls is None:
        return None
    ratio = walls["imbalance_ratio"]
    return {"imbalance_ratio": round(ratio, 4), "support_strength": _strength_label(ratio),
            "resistance_strength": _strength_label(1.0 - ratio)}
