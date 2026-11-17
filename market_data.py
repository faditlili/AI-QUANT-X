"""Public Binance market data only (no keys, no orders).

Rules followed by every method here:
* spot and futures are strictly separated: every call takes `source` and uses that market's URLs;
* a failed or incomplete request raises MarketDataError or returns None. It NEVER returns a made-up
  number (no fake 0.0 funding, no fake 50 fear&greed, no fake 50% breadth);
* only CLOSED candles are returned;
* results are cached briefly so one scan does not hammer the API.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import aiohttp
import pandas as pd

import config

log = logging.getLogger(__name__)

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,20}$")
_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d")


class MarketDataError(RuntimeError):
    pass


def _check_symbol(symbol):
    s = str(symbol or "").upper()
    if not _SYMBOL_RE.match(s):
        raise ValueError(f"Invalid symbol {symbol!r}")
    return s


class MarketData:
    def __init__(self):
        self.session = None
        self.sem = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        self._metadata = {}            # source -> (monotonic, exchangeInfo)
        self._fng = {"value": None, "timestamp": 0.0}
        self._ticker_cache = {}
        self._kline_cache = {}
        self._cooldown_until = 0.0
        self.last_success = 0.0        # monotonic time of the last successful API response

    async def start(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT_SECONDS)
            connector = aiohttp.TCPConnector(limit=8, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector,
                                                 headers={"User-Agent": config.USER_AGENT})

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    # ------------------------------------------------------------------ plumbing
    def _base(self, source):
        if source == "spot":
            return config.BINANCE_SPOT_BASE_URL
        if source == "futures":
            return config.BINANCE_FUTURES_BASE_URL
        raise ValueError("source must be spot or futures")

    def _path(self, source, kind):
        paths = {
            "spot": {"klines": config.SPOT_KLINES_PATH, "ticker": config.SPOT_TICKER_24H_PATH,
                     "info": config.SPOT_EXCHANGE_INFO_PATH, "price": config.SPOT_PRICE_PATH,
                     "depth": "/api/v3/depth"},
            "futures": {"klines": config.FUTURES_KLINES_PATH, "ticker": config.FUTURES_TICKER_24H_PATH,
                        "info": config.FUTURES_EXCHANGE_INFO_PATH, "price": config.FUTURES_PRICE_PATH,
                        "depth": "/fapi/v1/depth"},
        }
        return paths[source][kind]

    async def _get(self, source, path, params=None):
        await self.start()
        wait = self._cooldown_until - time.monotonic()
        if wait > 0:
            raise MarketDataError(f"API cooldown, retry in {wait:.0f}s")
        url = self._base(source) + path
        async with self.sem:
            for attempt in range(config.HTTP_RETRY_ATTEMPTS + 1):
                try:
                    async with self.session.get(url, params=params) as response:
                        if response.status in (418, 429):
                            try:
                                retry = float(response.headers.get("Retry-After", 30))
                            except (TypeError, ValueError):
                                retry = 30.0
                            self._cooldown_until = time.monotonic() + min(max(retry, 10.0), 600.0)
                            raise MarketDataError(f"Rate limited ({response.status})")
                        if response.status >= 500 and attempt < config.HTTP_RETRY_ATTEMPTS:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        if response.status != 200:
                            body = (await response.text())[:200]
                            raise MarketDataError(f"HTTP {response.status}: {body}")
                        data = await response.json()
                        self.last_success = time.monotonic()
                        return data
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                    if attempt >= config.HTTP_RETRY_ATTEMPTS:
                        raise MarketDataError(f"{type(exc).__name__}: {exc}") from exc
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise MarketDataError("Request failed")

    # ------------------------------------------------------------------ context data (None = unavailable)
    async def get_fear_and_greed(self):
        """Fear & Greed index 0..100, or None when it cannot be obtained (a value older than 24h is dropped)."""
        now = time.time()
        if self._fng["value"] is not None and now - self._fng["timestamp"] < 3600:
            return self._fng["value"]
        try:
            await self.start()
            async with self.session.get("https://api.alternative.me/fng/?limit=1") as r:
                if r.status == 200:
                    val = int((await r.json())["data"][0]["value"])
                    if 0 <= val <= 100:
                        self._fng = {"value": val, "timestamp": now}
                        return val
        except Exception as e:
            log.warning("Fear&Greed unavailable: %s", e)
        if self._fng["value"] is not None and now - self._fng["timestamp"] < 86400:
            return self._fng["value"]
        return None

    async def get_market_breadth(self, source="futures"):
        """% of the 20 most liquid symbols that are up over 24h, or None when tickers are unavailable."""
        try:
            tickers = await self.get_tickers_24h(source)
            top = sorted(tickers.values(), key=lambda t: t["quote_volume"], reverse=True)[:20]
            if len(top) < 5:
                return None
            return sum(1 for t in top if t["change_percent"] > 0) / len(top) * 100
        except Exception as e:
            log.warning("Breadth unavailable (%s): %s", source, e)
            return None

    # ------------------------------------------------------------------ exchange info / rules
    async def exchange_info(self, source):
        cached = self._metadata.get(source)
        if cached and time.monotonic() - cached[0] < config.SYMBOL_INFO_TTL_SECONDS:
            return cached[1]
        data = await self._get(source, self._path(source, "info"))
        if not isinstance(data, dict) or not data.get("symbols"):
            raise MarketDataError("exchangeInfo returned no symbols")
        self._metadata[source] = (time.monotonic(), data)
        return data

    async def eligible_symbols(self, source="futures"):
        info = await self.exchange_info(source)
        output = []
        for item in info.get("symbols", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT") or item.get("status") != "TRADING":
                continue
            if symbol in config.EXCLUDED_SYMBOLS or any(k in symbol for k in config.EXCLUDED_KEYWORDS):
                continue
            if source == "futures" and item.get("contractType") not in (None, "PERPETUAL"):
                continue
            if source == "spot" and item.get("isSpotTradingAllowed") is False:
                continue
            output.append(symbol)
        return output

    @staticmethod
    def parse_symbol_rules(item):
        """Extract {step, min_qty, min_notional, tick} from one exchangeInfo symbol entry (None if incomplete)."""
        rules = {"step": None, "min_qty": None, "min_notional": None, "tick": None}
        for f in item.get("filters", []):
            t = f.get("filterType")
            try:
                if t == "LOT_SIZE":
                    rules["step"], rules["min_qty"] = float(f["stepSize"]), float(f["minQty"])
                elif t == "PRICE_FILTER":
                    rules["tick"] = float(f["tickSize"])
                elif t in ("NOTIONAL", "MIN_NOTIONAL"):
                    rules["min_notional"] = float(f.get("minNotional", f.get("notional", 0)))
            except (KeyError, TypeError, ValueError):
                return None
        if not rules["step"] or rules["step"] <= 0 or rules["tick"] is None:
            return None
        rules["min_qty"] = rules["min_qty"] or 0.0
        rules["min_notional"] = rules["min_notional"] or 0.0
        return rules

    async def get_symbol_rules(self, symbol, source):
        symbol = _check_symbol(symbol)
        info = await self.exchange_info(source)
        for item in info.get("symbols", []):
            if item.get("symbol") == symbol:
                return self.parse_symbol_rules(item)
        return None

    # ------------------------------------------------------------------ candles
    @staticmethod
    def parse_klines(raw, now_ms=None):
        """Raw Binance klines -> DataFrame of CLOSED candles. Raises on malformed rows."""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000) if now_ms is None else now_ms
        rows = []
        for c in raw:
            try:
                if int(c[6]) >= now_ms:       # still forming
                    continue
                rows.append({"timestamp": int(c[0]), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                             "close": float(c[4]), "volume": float(c[5]), "quote_volume": float(c[7]),
                             "taker_buy_volume": float(c[9]), "close_time": int(c[6])})
            except (IndexError, TypeError, ValueError) as exc:
                raise MarketDataError(f"Malformed kline row: {exc}") from exc
        return pd.DataFrame(rows)

    async def get_klines(self, symbol, interval="1h", limit=None, source="futures"):
        symbol = _check_symbol(symbol)
        if interval not in _INTERVALS:
            raise ValueError("Unsupported interval")
        limit = min(int(limit or config.KLINE_LIMIT), 1000)
        key = (source, symbol, interval, limit)
        cached = self._kline_cache.get(key)
        if cached and time.monotonic() - cached[0] < config.KLINE_CACHE_SECONDS:
            return cached[1].copy()
        raw = await self._get(source, self._path(source, "klines"), {"symbol": symbol, "interval": interval, "limit": limit})
        if not isinstance(raw, list) or len(raw) < config.MIN_CANDLES_REQUIRED:
            raise MarketDataError(f"Insufficient candles for {symbol} {source}")
        frame = self.parse_klines(raw)
        if len(frame) < config.MIN_CANDLES_REQUIRED:
            raise MarketDataError("Not enough completed candles")
        if len(self._kline_cache) > 600:
            self._kline_cache.clear()
        self._kline_cache[key] = (time.monotonic(), frame)
        return frame.copy()

    async def fetch_history(self, symbol, interval="1h", source="futures", candles=None):
        symbol = _check_symbol(symbol)
        candles = candles or config.BACKTEST_CANDLES
        rows, end = [], None
        while len(rows) < candles:
            limit = min(1000, candles - len(rows))
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            if end:
                params["endTime"] = end
            raw = await self._get(source, self._path(source, "klines"), params)
            if not raw:
                break
            rows = raw + rows
            end = int(raw[0][0]) - 1
            if len(raw) < limit:
                break
        frame = self.parse_klines(rows)
        if frame.empty:
            return frame
        return frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)

    async def get_funding_history(self, symbol, start_ms=None, limit=100):
        """Settled futures funding events [{fundingTime, fundingRate}], oldest first."""
        symbol = _check_symbol(symbol)
        params = {"symbol": symbol, "limit": limit}
        if start_ms:
            params["startTime"] = int(start_ms)
        raw = await self._get("futures", "/fapi/v1/fundingRate", params)
        if not isinstance(raw, list):
            raise MarketDataError("Unexpected fundingRate response")
        out = []
        for x in raw:
            try:
                out.append({"fundingTime": int(x["fundingTime"]), "fundingRate": float(x["fundingRate"])})
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(out, key=lambda e: e["fundingTime"])

    async def fetch_funding_range(self, symbol, start_ms, end_ms):
        """All settled funding events in [start_ms, end_ms] (paged, 100 per request)."""
        out, cursor = [], int(start_ms)
        for _ in range(60):
            page = await self.get_funding_history(symbol, cursor, 100)
            page = [e for e in page if e["fundingTime"] <= end_ms]
            if not page:
                break
            out.extend(page)
            nxt = page[-1]["fundingTime"] + 1
            if nxt <= cursor or len(page) < 100:
                break
            cursor = nxt
        return out

    # ------------------------------------------------------------------ prices / tickers
    async def get_last_prices(self, source="futures"):
        raw = await self._get(source, self._path(source, "price"))
        if isinstance(raw, dict):
            raw = [raw]
        out = {}
        for x in raw:
            try:
                price = float(x["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if x.get("symbol") and price > 0:
                out[x["symbol"]] = {"last_price": price}
        if not out:
            raise MarketDataError("No valid prices returned")
        return out

    async def get_tickers_24h(self, source="futures"):
        cached = self._ticker_cache.get(source)
        if cached and time.monotonic() - cached[0] < 15:
            return cached[1]
        raw = await self._get(source, self._path(source, "ticker"))
        if isinstance(raw, dict):
            raw = [raw]
        data = {}
        for x in raw:
            try:
                last = float(x["lastPrice"])
                data[x["symbol"]] = {"last_price": last, "quote_volume": float(x["quoteVolume"]),
                                     "change_percent": float(x["priceChangePercent"])}
            except (KeyError, TypeError, ValueError):
                continue
            if last <= 0:
                data.pop(x["symbol"], None)
        if not data:
            raise MarketDataError("No valid tickers returned")
        self._ticker_cache[source] = (time.monotonic(), data)
        return data

    async def get_ticker_24h(self, symbol, source="futures"):
        return (await self.get_tickers_24h(source)).get(_check_symbol(symbol))

    async def get_funding_rate(self, symbol, source="futures"):
        """Last funding rate, or None when unavailable. Spot has no funding: None (never 0.0)."""
        if source != "futures":
            return None
        try:
            raw = await self._get(source, "/fapi/v1/premiumIndex", {"symbol": _check_symbol(symbol)})
            if raw.get("lastFundingRate") in (None, ""):
                return None
            return float(raw["lastFundingRate"])
        except Exception as e:
            log.debug("Funding rate unavailable for %s: %s", symbol, e)
            return None

    async def get_depth(self, symbol, source="futures", limit=50):
        return await self._get(source, self._path(source, "depth"), {"symbol": _check_symbol(symbol), "limit": limit})

    async def liquid_symbols(self, source="futures"):
        tickers = await self.get_tickers_24h(source)
        eligible = set(await self.eligible_symbols(source))
        configured = [s for s in config.SYMBOLS if s in eligible]
        liquid = [s for s in configured if tickers.get(s, {}).get("quote_volume", 0) >= config.MIN_24H_VOLUME_USDT]
        return liquid[:config.MAX_SYMBOLS_TO_SCAN]

    def get_status(self):
        age = (time.monotonic() - self.last_success) if self.last_success else None
        return {"connected": bool(self.session and not self.session.closed), "sources": ["spot", "futures"],
                "mode": "public-data-only", "last_success_age_s": age}
