"""Asynchronous paper-simulation engine with AI, ML, WebSockets, Sentiment, and Dynamic Symbols."""
import asyncio, logging, time, os
import datetime
import config
from order_book import get_order_book_imbalance
from ml_filter import train_model, get_ml_probability
from websocket_streamer import start_price_stream, get_live_price
from sentiment_engine import get_market_sentiment
from symbol_scanner import get_top_symbols
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
        self.running=False; self.task=None; self.monitor_task=None; self.ws_task=None; self.last_scan=None; self.last_error=None
        self.paused=self.db.get_state("paused","0")=="1"
        self.notifier=None
        self.compass={}
        self.last_symbol_update = 0 # <--- تتبع وقت تحديث العملات

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
            
        if getattr(config, "USE_ML_FILTER", False):
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl")
            if not os.path.exists(model_path):
                log.info("ML Model not found. Fetching history to train...")
                try:
                    df = await self.market.fetch_history("BTCUSDT", "1h", "futures", 2000)
                    if not df.empty:
                        df_ind = compute_frame(df)
                        await asyncio.to_thread(train_model, df_ind)
                except Exception as e:
                    log.error(f"Failed to train ML model on startup: {e}")

        self.running=True
        if self.task is None or self.task.done(): self.task=asyncio.create_task(self._run())
        if self.monitor_task is None or self.monitor_task.done(): self.monitor_task=asyncio.create_task(self._monitor_loop())

    async def stop(self):
        self.running=False
        for task in (self.task, self.monitor_task, self.ws_task):
            if task:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
        await self.market.close(); await self.news.close()

    async def _run(self):
        while self.running:
            started=time.monotonic()
            try: await self.scan_once()
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

    async def _analyze(self,symbol,source, macro_ctx):
        frames={}
        for tf in config.TIMEFRAMES:
            frames[tf]=await self._indicators(symbol,source,tf)
        dirs=[direction(frames[x]) for x in config.TIMEFRAMES]
        primary=frames[config.PRIMARY_TIMEFRAME]
        news=await self.news.get_news_risk(symbol)
        
        funding_rate = await self.market.get_funding_rate(symbol, source) if source == "futures" else 0.0
        current_hour = datetime.datetime.now(datetime.timezone.utc).hour
        
        ob_data = await get_order_book_imbalance(symbol, session=self.market.session)
        
        ml_prob = 0.5
        if getattr(config, "USE_ML_FILTER", False):
            ml_prob = get_ml_probability(primary)
            
        sentiment = await get_market_sentiment()
        
        ctx={"source":source,"symbol":symbol,"compass":macro_ctx.get("compass"),"primary":primary,"htf":frames[config.TIMEFRAMES[-1]],
             "dirs":dirs,"news_risk":news.get("risk",0), "funding_rate": funding_rate,
             "fear_greed": macro_ctx["fng"], "breadth": macro_ctx["breadth"], "hour_utc": current_hour,
             "order_book": ob_data, "ml_prob": ml_prob, "sentiment": sentiment}
             
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
        
        opened=self.trader.open_position(symbol,primary["price"],primary["atr"],result["side"],source,
                 {"score":result["score"],"timeframes":dirs,"regime":result["regime"],"atr":primary["atr"], "ml_prob": ml_prob},
                 stop_mult=result["stop_mult"],rr=result["rr"],strategy=result["strategy"])
                 
        if not opened.get("success") and opened.get("reason")!="Duplicate open position":
            self.db.add_decision(symbol,source,"HOLD",result["score"],f"Not opened: {opened.get('reason')}")
        if opened.get("success"):
            self.db.add_decision(symbol,source,result["action"],result["score"],result["reason"])
            self.db.set_state(f"cooldown:{source}:{symbol}",time.time())
            if self.notifier: await self.notifier.notify_trade_opened(opened["position"])

    async def monitor_positions(self):
        open_positions = self.db.get_open_positions()
        if not open_positions: return
        
        prices_by_source = {}
        for p in open_positions:
            symbol = p["symbol"]
            source = p["source"]
            
            live_price = get_live_price(symbol)
            if not live_price:
                try:
                    res = await self.market.get_last_prices(source)
                    live_price = res.get(symbol, {}).get("last_price")
                except Exception:
                    pass
                    
            if live_price:
                if source not in prices_by_source:
                    prices_by_source[source] = {}
                prices_by_source[source][symbol] = {"last_price": live_price}

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

    async def scan_once(self):
        self.last_scan=time.time()
        
        # --- تحديث قائمة العملات ديناميكياً كل 12 ساعة ---
        if time.time() - self.last_symbol_update > 43200: # 12 ساعة
            try:
                new_symbols = await get_top_symbols()
                if new_symbols:
                    config.SYMBOLS = tuple(new_symbols)
                    self.last_symbol_update = time.time()
                    log.info(f"Dynamic Scanner: Updated watchlist to {len(config.SYMBOLS)} top movers.")
            except Exception as e:
                log.error(f"Failed to update symbols: {e}")
        # -------------------------------------------------

        fng = await self.market.get_fear_and_greed()
        
        for source in config.MARKET_SOURCES:
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
                for symbol in symbols:
                    try: await self._analyze(symbol,source, macro_ctx)
                    except Exception as exc: log.warning("Analysis skipped %s/%s: %s",source,symbol,exc)
            except Exception as exc: log.warning("Source scan failed (%s): %s",source,exc)
        
        self.db.snapshot()
        self.db.prune()

    def set_paused(self,value):
        self.paused=bool(value); self.db.set_state("paused","1" if value else "0")

    def get_status(self):
        return {"running":self.running,"paused":self.paused,"last_scan":self.last_scan,
                "last_error":self.last_error,"mode":"PAPER SIMULATION","compass":self.compass}
