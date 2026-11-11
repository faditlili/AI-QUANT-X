"""Public Binance market data only."""
import asyncio, logging
from datetime import datetime, timezone
import aiohttp
import pandas as pd
import config

log = logging.getLogger(__name__)

class MarketDataError(RuntimeError):
    pass

class MarketData:
    def __init__(self):
        self.session = None
        self.sem = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        self._metadata = {}
        self._fng_cache = {"value": 50, "timestamp": 0}

    async def start(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT_SECONDS)
            connector = aiohttp.TCPConnector(limit=8, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector, headers={"User-Agent": config.USER_AGENT})

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    def _base(self, source):
        if source == "spot": return config.BINANCE_SPOT_BASE_URL
        if source == "futures": return config.BINANCE_FUTURES_BASE_URL
        raise ValueError("source must be spot or futures")

    def _path(self, source, kind):
        paths = {
            "spot": {"klines": config.SPOT_KLINES_PATH, "ticker": config.SPOT_TICKER_24H_PATH, "info": config.SPOT_EXCHANGE_INFO_PATH, "price": config.SPOT_PRICE_PATH},
            "futures": {"klines": config.FUTURES_KLINES_PATH, "ticker": config.FUTURES_TICKER_24H_PATH, "info": config.FUTURES_EXCHANGE_INFO_PATH, "price": config.FUTURES_PRICE_PATH}
        }
        return paths[source][kind]

    async def _get(self, source, path, params=None):
        await self.start()
        url = self._base(source) + path
        async with self.sem:
            for attempt in range(config.HTTP_RETRY_ATTEMPTS + 1):
                try:
                    async with self.session.get(url, params=params) as response:
                        if response.status in (418, 429): raise MarketDataError(f"Rate limited ({response.status})")
                        if response.status >= 500 and attempt < config.HTTP_RETRY_ATTEMPTS:
                            await asyncio.sleep(1.5 * (attempt + 1)); continue
                        if response.status != 200:
                            body = (await response.text())[:200]
                            raise MarketDataError(f"HTTP {response.status}: {body}")
                        return await response.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if attempt >= config.HTTP_RETRY_ATTEMPTS: raise MarketDataError(str(exc)) from exc
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise MarketDataError("Request failed")

    async def get_fear_and_greed(self):
        if datetime.now(timezone.utc).timestamp() - self._fng_cache["timestamp"] < 3600:
            return self._fng_cache["value"]
        try:
            await self.start()
            url = "https://api.alternative.me/fng/?limit=1"
            async with self.session.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    val = int(data["data"][0]["value"])
                    self._fng_cache = {"value": val, "timestamp": datetime.now(timezone.utc).timestamp()}
                    return val
        except Exception as e:
            log.warning(f"F&G API error: {e}")
        return self._fng_cache["value"]

    async def get_market_breadth(self, source="futures"):
        try:
            tickers = await self.get_tickers_24h(source)
            sorted_t = sorted(tickers.items(), key=lambda x: x[1]["quote_volume"], reverse=True)[:20]
            up_count = sum(1 for s, t in sorted_t if t["change_percent"] > 0)
            return (up_count / len(sorted_t)) * 100
        except Exception:
            return 50.0

    async def exchange_info(self, source):
        if source not in self._metadata:
            self._metadata[source] = await self._get(source, self._path(source, "info"))
        return self._metadata[source]

    async def eligible_symbols(self, source="futures"):
        info = await self.exchange_info(source)
        output = []
        for item in info.get("symbols", []):
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT") or item.get("status") != "TRADING": continue
            if symbol in config.EXCLUDED_SYMBOLS or any(k in symbol for k in config.EXCLUDED_KEYWORDS): continue
            if source == "futures" and item.get("contractType") not in (None, "PERPETUAL"): continue
            if source == "spot" and item.get("isSpotTradingAllowed") is False: continue
            output.append(symbol)
        return output

    async def get_klines(self, symbol, interval="1h", limit=None, source="futures"):
        if interval not in ("1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"):
            raise ValueError("Unsupported interval")
        raw = await self._get(source, self._path(source, "klines"), {"symbol": symbol.upper(), "interval": interval, "limit": min(int(limit or config.KLINE_LIMIT), 1000)})
        if not isinstance(raw, list) or len(raw) < config.MIN_CANDLES_REQUIRED:
            raise MarketDataError(f"Insufficient candles for {symbol} {source}")
        rows = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        for candle in raw:
            if int(candle[6]) >= now_ms: continue
            rows.append({
                "timestamp": int(candle[0]), "open": float(candle[1]), "high": float(candle[2]), "low": float(candle[3]),
                "close": float(candle[4]), "volume": float(candle[5]), "quote_volume": float(candle[7]) if len(candle) > 7 else 0.0,
                "taker_buy_volume": float(candle[9]) if len(candle) > 9 else 0.0, "close_time": int(candle[6])
            })
        frame = pd.DataFrame(rows)
        if len(frame) < config.MIN_CANDLES_REQUIRED: raise MarketDataError("Not enough completed candles")
        return frame
        
    async def get_last_prices(self, source="futures"):
        raw = await self._get(source, self._path(source, "price"))
        if isinstance(raw, dict): raw = [raw]
        return {x["symbol"]: {"last_price": float(x["price"])} for x in raw if x.get("symbol") and x.get("price")}
        
    async def get_tickers_24h(self, source="futures"):
        raw = await self._get(source, self._path(source, "ticker"))
        if isinstance(raw, dict): raw = [raw]
        return {x["symbol"]: {"last_price": float(x.get("lastPrice", x.get("last_price", 0))), "quote_volume": float(x.get("quoteVolume", x.get("quote_volume", 0))), "change_percent": float(x.get("priceChangePercent", 0))} for x in raw if x.get("symbol")}

    async def get_funding_rate(self, symbol, source="futures"):
        if source != "futures": return 0.0
        try:
            raw = await self._get(source, "/fapi/v1/premiumIndex", {"symbol": symbol.upper()})
            return float(raw.get("lastFundingRate", 0.0))
        except Exception: return 0.0

    async def liquid_symbols(self, source="futures"):
        tickers = await self.get_tickers_24h(source)
        eligible = set(await self.eligible_symbols(source))
        configured = [s for s in config.SYMBOLS if s in eligible]
        liquid = [s for s in configured if tickers.get(s, {}).get("quote_volume", 0) >= config.MIN_24H_VOLUME_USDT]
        return liquid[:config.MAX_SYMBOLS_TO_SCAN]

    # --- الدالة الجديدة التي تم نقلها هنا لحل المشكلة ---
    async def fetch_history(self, symbol, interval="1h", source="futures", candles=None):
        import time as _t
        import pandas as pd
        candles = candles or config.BACKTEST_CANDLES
        rows, end = [], None
        while len(rows) < candles:
            limit = min(1000, candles - len(rows))
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            if end:
                params["endTime"] = end
            raw = await self._get(source, self._path(source, "klines"), params)
            if not raw:
                break
            rows = raw + rows
            end = int(raw[0][0]) - 1
            if len(raw) < limit:
                break
        now_ms = int(_t.time() * 1000)
        data = [{"timestamp": int(c[0]), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                 "close": float(c[4]), "volume": float(c[5]), 
                 "taker_buy_volume": float(c[9]) if len(c) > 9 else float(c[5]) * 0.5} 
                 for c in rows if int(c[6]) < now_ms]
        frame = pd.DataFrame(data).drop_duplicates("timestamp").sort_values("timestamp")
        return frame.reset_index(drop=True)

    def get_status(self):
        return {"connected": bool(self.session and not self.session.closed), "sources": ["spot", "futures"], "mode": "public-data-only"}
