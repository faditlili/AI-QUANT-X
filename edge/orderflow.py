"""Pure, deterministic order-flow metrics (no I/O). Every function is explainable and unit-tested.

Sign convention (Binance aggTrades field `m` = buyer is the maker): m=True means the TAKER SOLD, so that
trade is aggressive SELLING; m=False means aggressive BUYING. CVD = cumulative(buy volume - sell volume).
"""


def cvd_bars(trades, bucket_ms):
    """Aggregate trades (client.agg_trades()["trades"]) into fixed buckets. Duplicate ids are ignored.
    Returns bars oldest-first: bucket_start, bucket_end, buy, sell, delta, trades."""
    if bucket_ms <= 0:
        raise ValueError("bucket_ms must be positive")
    bars, seen = {}, set()
    for t in trades:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        start = (t["ts"] // bucket_ms) * bucket_ms
        b = bars.setdefault(start, {"bucket_start": start, "bucket_end": start + bucket_ms,
                                    "buy": 0.0, "sell": 0.0, "trades": 0})
        b["sell" if t["buyer_is_maker"] else "buy"] += t["qty"]
        b["trades"] += 1
    out = []
    for start in sorted(bars):
        b = bars[start]
        b["delta"] = b["buy"] - b["sell"]
        out.append(b)
    return out


def closed_bars(bars, as_of_ms):
    """Only buckets that had already ENDED at as_of_ms (an open bucket is incomplete -> would leak/mislead)."""
    return [b for b in bars if b["bucket_end"] <= as_of_ms]


def cumulative(bars):
    total, out = 0.0, []
    for b in bars:
        total += b["delta"]
        out.append(total)
    return out


def taker_imbalance(buy_vol, sell_vol):
    """(buy - sell) / (buy + sell) in [-1, 1]; None if there was no volume."""
    total = buy_vol + sell_vol
    return None if total <= 0 else (buy_vol - sell_vol) / total


def pct_change(new, old):
    return None if old is None or new is None or old == 0 else (new - old) / abs(old) * 100.0


def oi_change_pct(series, bars_back):
    """Percent change of open interest between the latest point and `bars_back` points earlier.
    `series`: oldest-first dicts with key "oi". None if there is not enough history."""
    if bars_back < 1 or len(series) <= bars_back:
        return None
    return pct_change(series[-1]["oi"], series[-1 - bars_back]["oi"])


def oi_price_quadrant(price_change_pct, oi_change_pct_value, dead_band_pct=0.1):
    """Classic positioning read from the sign of price change vs open-interest change.
      price up   + OI up   -> LONG_BUILDUP     (new longs: trend fuel, but crowding risk)
      price up   + OI down -> SHORT_COVERING   (weak rally: shorts closing, no new buyers)
      price down + OI up   -> SHORT_BUILDUP    (new shorts: trend fuel / squeeze risk)
      price down + OI down -> LONG_LIQUIDATION (longs capitulating)
    Moves inside +-dead_band_pct are NEUTRAL; None if either input is missing."""
    if price_change_pct is None or oi_change_pct_value is None:
        return None
    if abs(price_change_pct) < dead_band_pct or abs(oi_change_pct_value) < dead_band_pct:
        return "NEUTRAL"
    if price_change_pct > 0:
        return "LONG_BUILDUP" if oi_change_pct_value > 0 else "SHORT_COVERING"
    return "SHORT_BUILDUP" if oi_change_pct_value > 0 else "LONG_LIQUIDATION"
