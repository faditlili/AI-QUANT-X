"""Validated readers for PUBLIC Binance USD-M futures endpoints used by the edge engine.

`fetch(path, params)` is any async callable returning decoded JSON. In production it is the Legacy
`MarketData._get` (so rate-limit cooldown / retries are shared); in tests it is a fake.
Strictness: a malformed payload or non-finite number raises EdgeDataError. Nothing is defaulted.
"""
import math
import re

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,20}$")
PERIOD_MS = {"5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
             "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000, "1d": 86_400_000}
LS_ENDPOINTS = {"global_account": "/futures/data/globalLongShortAccountRatio",
                "top_account": "/futures/data/topLongShortAccountRatio",
                "top_position": "/futures/data/topLongShortPositionRatio"}
AGG_PAGE = 1000


class EdgeDataError(RuntimeError):
    pass


def check_symbol(symbol):
    s = str(symbol or "").upper()
    if not _SYMBOL_RE.match(s):
        raise ValueError("Invalid symbol %r" % (symbol,))
    return s


def check_period(period):
    if period not in PERIOD_MS:
        raise ValueError("Invalid period %r" % (period,))
    return period


def num(value, what, minimum=None):
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise EdgeDataError("%s is not a number: %r" % (what, value))
    if not math.isfinite(x) or (minimum is not None and x < minimum):
        raise EdgeDataError("%s out of range: %r" % (what, value))
    return x


def ts_ms(value, what="timestamp"):
    x = int(num(value, what, minimum=1))
    return x


def _rows(data, what):
    if not isinstance(data, list):
        raise EdgeDataError("%s: expected a list, got %s" % (what, type(data).__name__))
    return data


class EdgeDataClient:
    def __init__(self, fetch):
        self._fetch = fetch

    @classmethod
    def from_market_data(cls, market_data):
        async def fetch(path, params=None):
            return await market_data._get("futures", path, params)
        return cls(fetch)

    async def open_interest_now(self, symbol):
        s = check_symbol(symbol)
        d = await self._fetch("/fapi/v1/openInterest", {"symbol": s})
        if not isinstance(d, dict):
            raise EdgeDataError("openInterest: bad payload")
        return {"symbol": s, "oi": num(d.get("openInterest"), "openInterest", 0), "ts": ts_ms(d.get("time"), "time")}

    async def open_interest_hist(self, symbol, period="1h", limit=100, start=None, end=None):
        s, p = check_symbol(symbol), check_period(period)
        d = _rows(await self._fetch("/futures/data/openInterestHist", _hist_params(s, p, limit, start, end)), "openInterestHist")
        out = [{"symbol": s, "period": p, "ts": ts_ms(r.get("timestamp")),
                "oi": num(r.get("sumOpenInterest"), "sumOpenInterest", 0),
                "oi_value": num(r.get("sumOpenInterestValue"), "sumOpenInterestValue", 0)} for r in d]
        return sorted(out, key=lambda r: r["ts"])

    async def long_short_ratio(self, symbol, kind="global_account", period="1h", limit=100, start=None, end=None):
        s, p = check_symbol(symbol), check_period(period)
        if kind not in LS_ENDPOINTS:
            raise ValueError("Invalid long/short kind %r" % (kind,))
        d = _rows(await self._fetch(LS_ENDPOINTS[kind], _hist_params(s, p, limit, start, end)), kind)
        out = [{"symbol": s, "period": p, "kind": kind, "ts": ts_ms(r.get("timestamp")),
                "ratio": num(r.get("longShortRatio"), "longShortRatio", 0),
                "long": num(r.get("longAccount"), "longAccount", 0),
                "short": num(r.get("shortAccount"), "shortAccount", 0)} for r in d]
        return sorted(out, key=lambda r: r["ts"])

    async def taker_ratio(self, symbol, period="1h", limit=100, start=None, end=None):
        s, p = check_symbol(symbol), check_period(period)
        d = _rows(await self._fetch("/futures/data/takerlongshortRatio", _hist_params(s, p, limit, start, end)), "takerlongshortRatio")
        out = [{"symbol": s, "period": p, "ts": ts_ms(r.get("timestamp")),
                "ratio": num(r.get("buySellRatio"), "buySellRatio", 0),
                "buy_vol": num(r.get("buyVol"), "buyVol", 0),
                "sell_vol": num(r.get("sellVol"), "sellVol", 0)} for r in d]
        return sorted(out, key=lambda r: r["ts"])

    async def premium_index(self, symbol):
        """Mark price, index price, last funding rate and the perpetual's premium over index (percent)."""
        s = check_symbol(symbol)
        d = await self._fetch("/fapi/v1/premiumIndex", {"symbol": s})
        if not isinstance(d, dict):
            raise EdgeDataError("premiumIndex: bad payload")
        mark, index = num(d.get("markPrice"), "markPrice", 1e-12), num(d.get("indexPrice"), "indexPrice", 1e-12)
        return {"symbol": s, "ts": ts_ms(d.get("time"), "time"), "mark": mark, "index": index,
                "funding": num(d.get("lastFundingRate"), "lastFundingRate"),
                "next_funding_ts": ts_ms(d.get("nextFundingTime"), "nextFundingTime"),
                "premium_pct": (mark - index) / index * 100.0}

    async def funding_history(self, symbol, limit=100, start=None, end=None):
        s = check_symbol(symbol)
        params = {"symbol": s, "limit": int(min(max(limit, 1), 1000))}
        if start is not None:
            params["startTime"] = int(start)
        if end is not None:
            params["endTime"] = int(end)
        d = _rows(await self._fetch("/fapi/v1/fundingRate", params), "fundingRate")
        out = [{"symbol": s, "ts": ts_ms(r.get("fundingTime"), "fundingTime"), "funding": num(r.get("fundingRate"), "fundingRate"),
                "mark": num(r["markPrice"], "markPrice") if r.get("markPrice") not in (None, "") else None} for r in d]
        return sorted(out, key=lambda r: r["ts"])

    async def agg_trades(self, symbol, start_ms, end_ms, max_pages=10):
        """All aggregated trades in [start_ms, end_ms] (deduplicated by id, oldest first).

        Returns {"trades": [...], "complete": bool}. complete=False means max_pages was hit before the
        window was exhausted: callers must NOT treat the window as fully covered then.
        Each trade: id, ts, price, qty, buyer_is_maker (True => the TAKER sold).
        """
        s = check_symbol(symbol)
        if int(end_ms) <= int(start_ms):
            raise ValueError("end_ms must be after start_ms")
        trades, seen = [], set()
        params = {"symbol": s, "startTime": int(start_ms), "endTime": int(end_ms), "limit": AGG_PAGE}
        complete = False
        for _ in range(int(max_pages)):
            page = _rows(await self._fetch("/fapi/v1/aggTrades", params), "aggTrades")
            for r in page:
                tid = int(num(r.get("a"), "a", 0))
                if tid in seen:
                    continue
                seen.add(tid)
                t = ts_ms(r.get("T"), "T")
                if int(start_ms) <= t <= int(end_ms):
                    trades.append({"id": tid, "ts": t, "price": num(r.get("p"), "p", 1e-12),
                                   "qty": num(r.get("q"), "q", 0), "buyer_is_maker": bool(r.get("m"))})
            if len(page) < AGG_PAGE:
                complete = True
                break
            last_id = int(num(page[-1].get("a"), "a", 0))
            if ts_ms(page[-1].get("T"), "T") > int(end_ms):
                complete = True
                break
            params = {"symbol": s, "fromId": last_id + 1, "limit": AGG_PAGE}   # fromId excludes start/endTime
        trades.sort(key=lambda t: (t["ts"], t["id"]))
        return {"trades": trades, "complete": complete}


def _hist_params(symbol, period, limit, start, end):
    params = {"symbol": symbol, "period": period, "limit": int(min(max(limit, 1), 500))}
    if start is not None:
        params["startTime"] = int(start)
    if end is not None:
        params["endTime"] = int(end)
    return params
