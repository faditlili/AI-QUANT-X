"""Asynchronous paper-simulation engine (public market data in, virtual fills out).

Safety rules implemented here:
* a trade is only opened from COMPLETE data: closed candles on all timeframes, a live price,
  a funding rate (futures) and the exchange trading rules; anything missing -> HOLD, never a guess;
* when market data stops arriving, new entries are blocked (RiskManager data-outage guard);
* open positions are persisted and re-evaluated against the live price after a restart.
"""
import asyncio
import datetime
import logging
import time

import config
from correlation import is_highly_correlated
from indicators import calculate_indicators, compute_frame, direction
from market_data import MarketData
from ml_filter import get_ml_probability, model_age_seconds, train_model
from news_engine import NewsEngine
from order_book import get_order_book_imbalance
from paper_trading import PaperTrader
from risk_manager import RiskManager
from sentiment_engine import get_market_sentiment
from strategies import select_signal
from symbol_scanner import get_top_symbols
from volume_anomaly import detect_volume_anomaly
from websocket_streamer import get_live_price, start_price_stream, stream_state

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, database, market=None, news=None):
        self.db = database
        self.market = market or MarketData()
        self.risk = RiskManager(database)
        self.trader = PaperTrader(database, self.risk)
        self.news = news or NewsEngine()
        self.running = False
        self.task = self.monitor_task = self.ws_task = self.ml_task = None
        self.last_scan = None
        self.last_error = None
        self.paused = self.db.get_state("paused", "0") == "1"
        self.notifier = None
        self.compass = {}
        self.last_symbol_update = 0
        self.last_whale_check = 0
        self.last_funding_check = 0
        self._scan_offset = {}
        self._started_at = time.monotonic()
        self._price_fail_since = None
        self._alerted_outage = False

    # ------------------------------------------------------------------ lifecycle
    async def start(self):
        await self.market.start()
        await self.news.start()
        log.info("Starting WebSocket price stream...")
        self.ws_task = asyncio.create_task(start_price_stream())
        saved_rsi, saved_ema = self.db.get_state("auto_rsi"), self.db.get_state("auto_ema")
        saved_strategy = self.db.get_state("auto_strategy")
        if saved_rsi:
            config.RSI_PERIOD = int(saved_rsi)
        if saved_ema:
            config.EMA_FAST = int(saved_ema)
        if saved_strategy:
            config.STRATEGIES = (saved_strategy,)
            log.info("Auto-Tune active: strategy '%s' RSI %s EMA %s", saved_strategy, saved_rsi, saved_ema)
        self.running = True
        if getattr(config, "USE_ML_FILTER", False):
            self.ml_task = asyncio.create_task(self._ml_maintenance())
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run())
        if self.monitor_task is None or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        self.running = False
        for task in (self.task, self.monitor_task, self.ws_task, self.ml_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        try:
            self.db.snapshot()
        except Exception:
            log.exception("Final snapshot failed")
        await self.market.close()
        await self.news.close()

    # ------------------------------------------------------------------ ML
    async def _train_ml(self):
        frames = []
        for sym in config.ML_TRAIN_SYMBOLS:
            try:
                df = await self.market.fetch_history(sym, "1h", "futures", 2000)
                if df is not None and not df.empty:
                    frames.append(compute_frame(df))
            except Exception as exc:
                log.warning("ML training data unavailable for %s: %s", sym, exc)
        if not frames:
            return False
        return (await asyncio.to_thread(train_model, frames)) is not None

    async def _ml_maintenance(self):
        while self.running:
            delay = 6 * 3600
            try:
                age = model_age_seconds()
                if age is None or age > config.ML_RETRAIN_DAYS * 86400:
                    log.info("ML model missing or old: training on %d symbols...", len(config.ML_TRAIN_SYMBOLS))
                    if not await self._train_ml():
                        delay = 1800
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("ML maintenance error: %s", exc)
                delay = 1800
            await asyncio.sleep(delay)

    async def _run(self):
        while self.running:
            started = time.monotonic()
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
                log.exception("Scan failed")
            await asyncio.sleep(max(5, config.SCAN_INTERVAL_SECONDS - (time.monotonic() - started)))

    # ------------------------------------------------------------------ data health
    def data_age(self):
        """Seconds since the last successful market-data response (None = never since start)."""
        status = self.market.get_status() if hasattr(self.market, "get_status") else {}
        return status.get("last_success_age_s")

    def update_data_health(self):
        age = self.data_age()
        ok = age is not None and age <= config.DATA_STALE_SECONDS
        startup_grace = age is None and (time.monotonic() - self._started_at) < 60
        reason = "" if ok else ("waiting for first market data" if startup_grace or age is None
                                else f"no market data for {age:.0f}s")
        self.risk.set_data_status(ok, reason)
        return ok

    async def _live_price(self, symbol, source, cache=None):
        """Latest price: fresh WebSocket tick (futures) else REST of the SAME market. None if unavailable."""
        if source == "futures":
            price = get_live_price(symbol)
            if price:
                return float(price)
        cache = cache if cache is not None else {}
        try:
            if source not in cache:
                cache[source] = await self.market.get_last_prices(source)
            item = cache[source].get(symbol)
            if item and item.get("last_price"):
                return float(item["last_price"])
        except Exception as exc:
            log.debug("Live price unavailable %s/%s: %s", source, symbol, exc)
        return None

    # ------------------------------------------------------------------ analysis
    async def _indicators(self, symbol, source, tf):
        return calculate_indicators(await self.market.get_klines(symbol, tf, config.KLINE_LIMIT, source))

    async def _compute_compass(self, source):
        if not getattr(config, "USE_BTC_COMPASS", False):
            return None
        dirs = []
        for sym in config.DIRECTION_SYMBOLS:
            try:
                dirs.append(direction(await self._indicators(sym, source, config.PRIMARY_TIMEFRAME)))
            except Exception as exc:
                log.warning("Compass unavailable (%s/%s): %s", source, sym, exc)
                return None
        if dirs and all(d == "BULLISH" for d in dirs):
            return "BULLISH"
        if dirs and all(d == "BEARISH" for d in dirs):
            return "BEARISH"
        return "NEUTRAL"

    def _hold(self, symbol, source, score, reason):
        self.db.add_decision(symbol, source, "HOLD", score, reason)

    async def _analyze(self, symbol, source, macro_ctx):
        raws = {}
        for tf in config.TIMEFRAMES:
            raws[tf] = await self.market.get_klines(symbol, tf, config.KLINE_LIMIT, source)   # raises on bad data
        frames = {tf: calculate_indicators(raws[tf]) for tf in config.TIMEFRAMES}
        dirs = [direction(frames[x]) for x in config.TIMEFRAMES]
        primary = frames[config.PRIMARY_TIMEFRAME]
        news = await self.news.get_news_risk(symbol)
        ob = await get_order_book_imbalance(symbol, self.market, source)
        ml_prob = get_ml_probability(primary) if getattr(config, "USE_ML_FILTER", False) else None
        sentiment = await get_market_sentiment()

        ctx = {"source": source, "symbol": symbol, "compass": macro_ctx.get("compass"), "primary": primary,
               "htf": frames[config.TIMEFRAMES[-1]], "dirs": dirs, "news_risk": news.get("risk", 0),
               "fear_greed": macro_ctx.get("fng"), "breadth": macro_ctx.get("breadth"),
               "hour_utc": datetime.datetime.now(datetime.timezone.utc).hour, "order_book": ob,
               "ml_prob": ml_prob, "sentiment": sentiment, "vol_anomaly": detect_volume_anomaly(raws[config.PRIMARY_TIMEFRAME])}
        if source == "futures":
            ctx["funding_rate"] = await self.market.get_funding_rate(symbol, source)   # None => entry blocked

        result = select_signal(ctx)
        if self.paused or result["action"] == "HOLD":
            self.db.add_decision(symbol, source, result["action"], result["score"], result["reason"])
            return
        if time.time() - float(self.db.get_state(f"cooldown:{source}:{symbol}", "0")) < config.SIGNAL_COOLDOWN_SECONDS:
            return
        if time.time() < float(self.db.get_state(f"lock:{symbol}", "0")):
            return
        if getattr(config, "USE_BTC_COMPASS", False) and ctx["compass"] is None and symbol not in config.DIRECTION_SYMBOLS:
            return self._hold(symbol, source, result["score"], "BTC/ETH compass unavailable")
        if not self.update_data_health():
            return self._hold(symbol, source, result["score"], f"Market data outage: {self.risk.data_reason}")

        open_positions = self.db.get_open_positions()
        if any(p["symbol"] == symbol for p in open_positions):
            return
        open_symbols = [p["symbol"] for p in open_positions if p["source"] == source]
        if open_symbols:
            blocked, why = await is_highly_correlated(symbol, open_symbols, self.market,
                                                      threshold=config.CORRELATION_MAX, source=source)
            if blocked:
                return self._hold(symbol, source, result["score"], f"Blocked by Correlation: {why}")

        # Enter at the live price, never at the (possibly 59 minutes old) close of the last candle.
        candle_price = primary["price"]
        entry_price = await self._live_price(symbol, source)
        if entry_price is None:
            return self._hold(symbol, source, result["score"], "No live price available")
        drift_atr = abs(entry_price - candle_price) / primary["atr"] if primary["atr"] > 0 else 0.0
        if drift_atr > config.ENTRY_MAX_DRIFT_ATR:
            return self._hold(symbol, source, result["score"], f"Stale setup: price moved {drift_atr:.1f} ATR since the candle closed")

        try:
            rules = await self.market.get_symbol_rules(symbol, source)
        except Exception as exc:
            log.warning("Symbol rules unavailable %s/%s: %s", source, symbol, exc)
            rules = None

        opened = self.trader.open_position(
            symbol, entry_price, primary["atr"], result["side"], source,
            {"score": result["score"], "timeframes": dirs, "regime": result["regime"], "atr": primary["atr"], "ml_prob": ml_prob},
            stop_mult=result["stop_mult"], rr=result["rr"], strategy=result["strategy"], rules=rules)
        if not opened.get("success"):
            if opened.get("reason") != "Duplicate open position":
                self._hold(symbol, source, result["score"], f"Not opened: {opened.get('reason')}")
            return
        self.db.add_decision(symbol, source, result["action"], result["score"], result["reason"])
        self.db.set_state(f"cooldown:{source}:{symbol}", time.time())
        await self._notify("notify_trade_opened", opened["position"])

    async def _notify(self, method, *args):
        """Notifications must never be able to break trading."""
        if not self.notifier:
            return
        try:
            await getattr(self.notifier, method)(*args)
        except Exception as exc:
            log.warning("Notification %s failed: %s", method, exc)

    async def _flush_events(self, closed):
        for row in closed or []:
            if row:
                await self._notify("notify_trade_closed", row)
        for ev in self.trader.drain_events():
            await self._notify("notify_event", ev)

    # ------------------------------------------------------------------ position monitoring
    async def check_whale_emergency_exit(self):
        now = time.time()
        if now - self.last_whale_check < 60:
            return
        self.last_whale_check = now
        cache = {}
        for p in self.db.get_open_positions():
            try:
                raw_df = await self.market.get_klines(p["symbol"], config.PRIMARY_TIMEFRAME, config.KLINE_LIMIT, p["source"])
                anomaly = detect_volume_anomaly(raw_df)
                if not (anomaly.get("anomaly") and anomaly.get("intensity") in ("HIGH", "EXTREME")):
                    continue
                against = ((p["side"] == "LONG" and anomaly.get("direction") == "SELLING_WHALE") or
                           (p["side"] == "SHORT" and anomaly.get("direction") == "BUYING_WHALE"))
                if not against:
                    continue
                price = await self._live_price(p["symbol"], p["source"], cache)
                if price:
                    log.warning("EMERGENCY EXIT: opposing whale on %s %s", p["symbol"], p["side"])
                    await self._flush_events([self.trader.close_position(p["id"], price, "WHALE_EXIT")])
            except Exception as e:
                log.error("Whale check failed for %s: %s", p["symbol"], e)

    async def settle_funding(self):
        """Apply settled Binance funding events to open futures positions (every ~5 minutes)."""
        if not config.FUNDING_ENABLED or time.time() - self.last_funding_check < 300:
            return
        self.last_funding_check = time.time()
        for p in self.db.get_open_positions():
            if p["source"] != "futures":
                continue
            try:
                last = float(self.db.get_state(f"funding_last:{p['id']}", "0"))
                opened_ms = int(datetime.datetime.fromisoformat(p["opened_at"]).timestamp() * 1000)
                events = await self.market.get_funding_history(p["symbol"], start_ms=max(last, opened_ms) + 1)
                for ev in events:
                    self.trader.apply_funding(p["id"], ev["fundingRate"], ev["fundingTime"])
            except Exception as exc:
                log.warning("Funding settlement failed for %s: %s", p["symbol"], exc)

    async def monitor_positions(self):
        await self.check_whale_emergency_exit()
        await self.settle_funding()
        open_positions = self.db.get_open_positions()
        if not open_positions:
            self._price_fail_since, self._alerted_outage = None, False
            return
        cache, by_source, missing = {}, {}, 0
        for p in open_positions:
            price = await self._live_price(p["symbol"], p["source"], cache)
            if price:
                by_source.setdefault(p["source"], {})[p["symbol"]] = {"last_price": price}
            else:
                missing += 1
        if missing == len(open_positions):
            # Stops cannot be evaluated without prices: say so loudly and keep new entries blocked.
            self._price_fail_since = self._price_fail_since or time.monotonic()
            if time.monotonic() - self._price_fail_since > config.DATA_STALE_SECONDS and not self._alerted_outage:
                self._alerted_outage = True
                log.error("No prices for open positions for %ds: stops are NOT being monitored", config.DATA_STALE_SECONDS)
                await self._notify("send", "⚠️ No market prices for open positions: stop-losses are not being monitored.")
        else:
            self._price_fail_since, self._alerted_outage = None, False
        for source, prices in by_source.items():
            await self._flush_events(self.trader.update_market_prices(prices, source))

    async def _monitor_loop(self):
        while self.running:
            try:
                await self.monitor_positions()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Position monitor error: %s", exc)
            await asyncio.sleep(config.POSITION_CHECK_SECONDS)

    # ------------------------------------------------------------------ scanning
    async def _refresh_symbols(self):
        if not config.USE_SYMBOL_SCANNER or time.time() - self.last_symbol_update < config.SYMBOL_SCAN_REFRESH_SECONDS:
            return
        self.last_symbol_update = time.time()
        try:
            new_symbols = await get_top_symbols()
            if new_symbols:
                config.SYMBOLS = tuple(dict.fromkeys(new_symbols))
                log.info("Dynamic Scanner: watch-list updated to %d symbols.", len(config.SYMBOLS))
        except Exception as e:
            log.error("Failed to update symbols: %s", e)

    def _rotate(self, source, symbols):
        if not symbols:
            return symbols
        offset = self._scan_offset.get(source, 0) % len(symbols)
        return symbols[offset:] + symbols[:offset]

    async def scan_once(self):
        scan_start = time.monotonic()
        self.last_scan = time.time()
        await self._refresh_symbols()
        fng = await self.market.get_fear_and_greed()
        sources = config.MARKET_SOURCES
        for idx, source in enumerate(sources):
            deadline = scan_start + config.MAX_SCAN_DURATION_SECONDS * (idx + 1) / len(sources)
            try:
                breadth = await self.market.get_market_breadth(source)
                compass = await self._compute_compass(source)
                if compass != self.compass.get(source):
                    log.info("BTC/ETH compass (%s): %s", source, compass)
                    self.compass[source] = compass
                macro_ctx = {"fng": fng, "breadth": breadth, "compass": compass}
                tickers = await self.market.get_tickers_24h(source)
                await self._flush_events(self.trader.update_market_prices(tickers, source))
                if self.paused:
                    continue
                ordered = self._rotate(source, await self.market.liquid_symbols(source))
                done = 0
                for symbol in ordered:
                    if time.monotonic() > deadline:
                        log.info("Scan time budget reached (%s): %d/%d symbols analyzed", source, done, len(ordered))
                        break
                    try:
                        await self._analyze(symbol, source, macro_ctx)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        log.warning("Analysis skipped %s/%s: %s", source, symbol, exc)
                    done += 1
                if ordered:
                    self._scan_offset[source] = (self._scan_offset.get(source, 0) + done) % len(ordered)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{source}: {exc}"
                log.warning("Source scan failed (%s): %s", source, exc)
        self.update_data_health()
        self.db.snapshot()
        self.db.prune()

    def set_paused(self, value):
        self.paused = bool(value)
        self.db.set_state("paused", "1" if value else "0")

    def get_status(self):
        return {"running": self.running, "paused": self.paused, "last_scan": self.last_scan,
                "last_error": self.last_error, "mode": "PAPER SIMULATION", "compass": self.compass,
                "data_ok": self.risk.data_ok, "data_reason": self.risk.data_reason,
                "ws_connected": stream_state.get("connected", False)}
