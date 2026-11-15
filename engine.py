"""Asynchronous paper-simulation engine with AI, ML, WebSockets, Sentiment, and Whale Detection."""
import asyncio, logging, time
import datetime
import config
from order_book import get_order_book_imbalance
from ml_filter import train_model, get_ml_probability, model_age_seconds
from websocket_streamer import start_price_stream, get_live_price
from sentiment_engine import get_market_sentiment
from symbol_scanner import get_top_symbols
from volume_anomaly import detect_volume_anomaly
from market_data import MarketData
from indicators import calculate_indicators, direction, compute_frame
from strategies import select_signal
from risk_manager import RiskManager
from paper_trading import PaperTrader
from news_engine import NewsEngine
from correlation import is_highly_correlated

log=logging.getLogger(__name__)

class Engine:
    def __init__(self,database,market=None,news=None):
        self.db=database; self.market=market or MarketData()
        self.risk=RiskManager(database); self.trader=PaperTrader(database,self.risk)
        self.news=news or NewsEngine()
        self.running=False; self.task=None; self.monitor_task=None; self.ws_task=None; self.ml_task=None
        self.last_scan=None; self.last_error=None
        self.paused=self.db.get_state("paused","0")=="1"
        self.notifier=None
        self.compass={}
        self.last_symbol_update = 0
        self.last_whale_check = 0
        self._scan_offset = {}

    async def start(self):
        await self.market.start()
        await self.news.start()

        log.info("Starting WebSocket Price Stream...")
        self.ws_task = asyncio.create_task(start_price_stream())

        saved_rsi = self.db.get_state("auto_rsi")
        saved_ema = self.db.get_state("auto_ema")
        saved_strategy = self.db.get_state("auto_strategy")

        if saved_rsi: config.RSI_PERIOD = int(saved_rsi)
        if saved_ema: config.EMA_FAST = int(saved_ema)

        if saved_strategy:
            config.STRATEGIES = (saved_strategy,)
            log.info(f"Auto-Tune Active: Using strategy '{saved_strategy}' with RSI {saved_rsi} & EMA {saved_ema}")

        self.running=True
        if getattr(config, "USE_ML_FILTER", False):
            self.ml_task=asyncio.create_task(self._ml_maintenance())
        if self.task is None or self.task.done(): self.task=asyncio.create_task(self._run())
        if self.monitor_task is None or self.monitor_task.done(): self.monitor_task=asyncio.create_task(self._monitor_loop())

    async def stop(self):
        self.running=False
        for task in (self.task, self.monitor_task, self.ws_task, self.ml_task):
            if task:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
        await self.market.close(); await self.news.close()

    async def _train_ml(self):
        frames=[]
        for sym in config.ML_TRAIN_SYMBOLS:
            try:
                df=await self.market.fetch_history(sym,"1h","futures",2000)
                if df is not None and not df.empty:
                    frames.append(compute_frame(df))
            except Exception as exc:
                log.warning("ML training data unavailable for %s: %s",sym,exc)
        if not frames:
            return False
        summary=await asyncio.to_thread(train_model,frames)
        return summary is not None

    async def _ml_maintenance(self):
        """Train in the background (never blocks startup) and retrain when the model gets old."""
        while self.running:
            delay=6*3600
            try:
                age=model_age_seconds()
                if age is None or age>config.ML_RETRAIN_DAYS*86400:
                    log.info("ML model missing or old: training on %d symbols...",len(config.ML_TRAIN_SYMBOLS))
                    if not await self._train_ml():
                        delay=1800
            except asyncio.CancelledError: raise
            except Exception as exc:
                log.warning("ML maintenance error: %s",exc); delay=1800
            await asyncio.sleep(delay)

    async def _run(self):
        while self.running:
            started=time.monotonic()
            try: await self.scan_once()
            except asyncio.CancelledError: raise
            except Exception as exc:
                self.last_error=str(exc); log.exception("Scan failed")
            delay=max(5,config.SCAN_INTERVAL_SECONDS-(time.monotonic()-started))
            await asyncio.sleep(delay)

    async def _indicators(self,symbol,source,tf):
        frame=await self.market.get_klines(symbol,tf,config.KLINE_LIMIT,source)
        return calculate_indicators(frame)

    async def _compute_compass(self,source):
        if not getattr(config,"USE_BTC_COMPASS",False): return None
        dirs=[]
        for sym in config.DIRECTION_SYMBOLS:
            try: dirs.append(direction(await self._indicators(sym,source,config.PRIMARY_TIMEFRAME)))
            except Exception as exc:
                log.warning("Compass unavailable (%s/%s): %s",source,sym,exc); return None
        if dirs and all(d=="BULLISH" for d in dirs): return "BULLISH"
        if dirs and all(d=="BEARISH" for d in dirs): return "BEARISH"
        return "NEUTRAL"

    async def _live_price(self,symbol,source,cache=None):
        """Latest price: WebSocket for futures, REST otherwise (REST also backs up the WebSocket)."""
        if source=="futures":
            price=get_live_price(symbol)
            if price: return float(price)
        cache=cache if cache is not None else {}
        try:
            if source not in cache: cache[source]=await self.market.get_last_prices(source)
            item=cache[source].get(symbol)
            if item and item.get("last_price"): return float(item["last_price"])
        except Exception as exc:
            log.debug("Live price unavailable %s/%s: %s",source,symbol,exc)
        return None

    async def _analyze(self,symbol,source, macro_ctx):
        raws={}
        for tf in config.TIMEFRAMES:
            raws[tf]=await self.market.get_klines(symbol,tf,config.KLINE_LIMIT,source)
        frames={tf:calculate_indicators(raws[tf]) for tf in config.TIMEFRAMES}
        dirs=[direction(frames[x]) for x in config.TIMEFRAMES]

        raw_df=raws[config.PRIMARY_TIMEFRAME]
        primary=frames[config.PRIMARY_TIMEFRAME]
        vol_anomaly = detect_volume_anomaly(raw_df)

        news=await self.news.get_news_risk(symbol)

        funding_rate = await self.market.get_funding_rate(symbol, source) if source == "futures" else 0.0
        current_hour = datetime.datetime.now(datetime.timezone.utc).hour

        ob_data = await get_order_book_imbalance(symbol, session=self.market.session)

        ml_prob = None
        if getattr(config, "USE_ML_FILTER", False):
            ml_prob = get_ml_probability(primary)

        sentiment = await get_market_sentiment()

        ctx={"source":source,"symbol":symbol,"compass":macro_ctx.get("compass"),"primary":primary,"htf":frames[config.TIMEFRAMES[-1]],
             "dirs":dirs,"news_risk":news.get("risk",0), "funding_rate": funding_rate,
             "fear_greed": macro_ctx["fng"], "breadth": macro_ctx["breadth"], "hour_utc": current_hour,
             "order_book": ob_data, "ml_prob": ml_prob, "sentiment": sentiment, "vol_anomaly": vol_anomaly}

        result=select_signal(ctx)

        if self.paused or result["action"]=="HOLD":
            self.db.add_decision(symbol,source,result["action"],result["score"],result["reason"])
            return

        if time.time()-float(self.db.get_state(f"cooldown:{source}:{symbol}","0")) < config.SIGNAL_COOLDOWN_SECONDS:
            return

        if time.time() < float(self.db.get_state(f"lock:{symbol}","0")):
            return

        open_positions = self.db.get_open_positions()
        if any(p["symbol"] == symbol for p in open_positions): return

        open_symbols = [p["symbol"] for p in open_positions if p["source"] == source]
        if open_symbols:
            is_corr, corr_reason = await is_highly_correlated(symbol, open_symbols, self.market, threshold=config.CORRELATION_MAX)
            if is_corr:
                self.db.add_decision(symbol, source, "HOLD", result["score"], f"Blocked by Correlation: {corr_reason}")
                return

        # Enter at the live price, not at the (possibly 59 minutes old) close of the last candle.
        candle_price=primary["price"]
        entry_price=await self._live_price(symbol,source) or candle_price
        drift_atr=abs(entry_price-candle_price)/primary["atr"] if primary["atr"]>0 else 0.0
        if drift_atr>config.ENTRY_MAX_DRIFT_ATR:
            self.db.add_decision(symbol,source,"HOLD",result["score"],f"Stale setup: price moved {drift_atr:.1f} ATR since the candle closed")
            return

        opened=self.trader.open_position(symbol,entry_price,primary["atr"],result["side"],source,
                 {"score":result["score"],"timeframes":dirs,"regime":result["regime"],"atr":primary["atr"], "ml_prob": ml_prob},
                 stop_mult=result["stop_mult"],rr=result["rr"],strategy=result["strategy"])

        if not opened.get("success") and opened.get("reason")!="Duplicate open position":
            self.db.add_decision(symbol,source,"HOLD",result["score"],f"Not opened: {opened.get('reason')}")
        if opened.get("success"):
            self.db.add_decision(symbol,source,result["action"],result["score"],result["reason"])
            self.db.set_state(f"cooldown:{source}:{symbol}",time.time())
            if self.notifier: await self.notifier.notify_trade_opened(opened["position"])

    async def check_whale_emergency_exit(self):
        """If a whale moves against an open trade, close it immediately to protect capital."""
        now = time.time()
        if now - self.last_whale_check < 60: return
        self.last_whale_check = now

        open_positions = self.db.get_open_positions()
        if not open_positions: return

        cache={}
        for p in open_positions:
            try:
                raw_df = await self.market.get_klines(p["symbol"], config.PRIMARY_TIMEFRAME, config.KLINE_LIMIT, p["source"])
                anomaly = detect_volume_anomaly(raw_df)
                if not (anomaly.get("anomaly") and anomaly.get("intensity") in ("HIGH", "EXTREME")):
                    continue
                against = ((p["side"] == "LONG" and anomaly.get("direction") == "SELLING_WHALE") or
                           (p["side"] == "SHORT" and anomaly.get("direction") == "BUYING_WHALE"))
                if not against: continue
                log.warning(f"EMERGENCY EXIT: opposing whale on {p['symbol']} {p['side']} position")
                price = await self._live_price(p["symbol"], p["source"], cache)
                if price:
                    closed = self.trader.close_position(p["id"], price, "WHALE_EXIT")
                    if closed and self.notifier: await self.notifier.notify_trade_closed(closed)
            except Exception as e:
                log.error(f"Whale check failed for {p['symbol']}: {e}")

    async def monitor_positions(self):
        await self.check_whale_emergency_exit()

        open_positions = self.db.get_open_positions()
        if not open_positions: return

        cache={}
        prices_by_source = {}
        for p in open_positions:
            price = await self._live_price(p["symbol"], p["source"], cache)
            if price:
                prices_by_source.setdefault(p["source"], {})[p["symbol"]] = {"last_price": price}

        for source, prices in prices_by_source.items():
            for closed in self.trader.update_market_prices(prices, source):
                if closed and self.notifier:
                    await self.notifier.notify_trade_closed(closed)

    async def _monitor_loop(self):
        while self.running:
            try: await self.monitor_positions()
            except asyncio.CancelledError: raise
            except Exception as exc: log.warning("Position monitor error: %s",exc)
            await asyncio.sleep(config.POSITION_CHECK_SECONDS)

    async def _refresh_symbols(self):
        if not config.USE_SYMBOL_SCANNER: return
        if time.time() - self.last_symbol_update < config.SYMBOL_SCAN_REFRESH_SECONDS: return
        self.last_symbol_update = time.time()
        try:
            new_symbols = await get_top_symbols()
            if new_symbols:
                config.SYMBOLS = tuple(dict.fromkeys(new_symbols))
                log.info(f"Dynamic Scanner: Updated watchlist to {len(config.SYMBOLS)} symbols.")
        except Exception as e:
            log.error(f"Failed to update symbols: {e}")

    def _rotate(self,source,symbols):
        """Start each scan where the previous one stopped, so a time-limited scan still covers every symbol."""
        if not symbols: return symbols
        offset=self._scan_offset.get(source,0)%len(symbols)
        return symbols[offset:]+symbols[:offset]

    async def scan_once(self):
        scan_start=time.monotonic()
        self.last_scan=time.time()
        await self._refresh_symbols()

        fng = await self.market.get_fear_and_greed()
        sources=config.MARKET_SOURCES

        for idx,source in enumerate(sources):
            deadline=scan_start+config.MAX_SCAN_DURATION_SECONDS*(idx+1)/len(sources)
            try:
                breadth = await self.market.get_market_breadth(source)
                compass = await self._compute_compass(source)
                if compass != self.compass.get(source):
                    log.info("BTC/ETH compass (%s): %s",source,compass)
                    self.compass[source] = compass
                macro_ctx = {"fng": fng, "breadth": breadth, "compass": compass}

                tickers=await self.market.get_tickers_24h(source)
                closed_positions=self.trader.update_market_prices(tickers,source)
                if self.notifier:
                    for closed in closed_positions:
                        if closed: await self.notifier.notify_trade_closed(closed)
                if self.paused: continue
                symbols=await self.market.liquid_symbols(source)
                ordered=self._rotate(source,symbols)
                done=0
                for symbol in ordered:
                    if time.monotonic()>deadline:
                        log.info("Scan time budget reached (%s): %d/%d symbols analyzed, the rest next scan",source,done,len(ordered))
                        break
                    try: await self._analyze(symbol,source, macro_ctx)
                    except asyncio.CancelledError: raise
                    except Exception as exc: log.warning("Analysis skipped %s/%s: %s",source,symbol,exc)
                    done+=1
                if ordered:
                    self._scan_offset[source]=(self._scan_offset.get(source,0)+done)%len(ordered)
            except asyncio.CancelledError: raise
            except Exception as exc: log.warning("Source scan failed (%s): %s",source,exc)

        self.db.snapshot()
        self.db.prune()

    def set_paused(self,value):
        self.paused=bool(value); self.db.set_state("paused","1" if value else "0")

    def get_status(self):
        return {"running":self.running,"paused":self.paused,"last_scan":self.last_scan,
                "last_error":self.last_error,"mode":"PAPER SIMULATION","compass":self.compass}
