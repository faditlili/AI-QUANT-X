"""Asynchronous paper-simulation engine with Macro Filters and Correlation."""
import asyncio, logging, time
import datetime
import config
from market_data import MarketData
from indicators import calculate_indicators, direction
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
        self.running=False; self.task=None; self.monitor_task=None; self.last_scan=None; self.last_error=None
        self.paused=self.db.get_state("paused","0")=="1"
        self.notifier=None

    async def start(self):
        await self.market.start()
        await self.news.start()
        self.running=True
        if self.task is None or self.task.done():
            self.task=asyncio.create_task(self._run())
        if self.monitor_task is None or self.monitor_task.done():
            self.monitor_task=asyncio.create_task(self._monitor_loop())

    async def stop(self):
        self.running=False
        for task in (self.task,self.monitor_task):
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

    async def _analyze(self,symbol,source, macro_ctx):
        frames={}
        for tf in config.TIMEFRAMES:
            frames[tf]=await self._indicators(symbol,source,tf)
        dirs=[direction(frames[x]) for x in config.TIMEFRAMES]
        primary=frames[config.PRIMARY_TIMEFRAME]
        news=await self.news.get_news_risk(symbol)
        
        funding_rate = await self.market.get_funding_rate(symbol, source) if source == "futures" else 0.0
        current_hour = datetime.datetime.now(datetime.timezone.utc).hour
        
        # دمج كل المؤشرات الكلية في الـ Context
        ctx={"source":source,"primary":primary,"htf":frames[config.TIMEFRAMES[-1]],
             "dirs":dirs,"news_risk":news.get("risk",0), "funding_rate": funding_rate,
             "fear_greed": macro_ctx["fng"], "breadth": macro_ctx["breadth"], "hour_utc": current_hour}
             
        result=select_signal(ctx)
        
        # 1. فحص الإشارة الأساسية
        if self.paused or result["action"]=="HOLD":
            self.db.add_decision(symbol,source,result["action"],result["score"],result["reason"])
            return
            
        # 2. فحص الكولداون
        if time.time()-float(self.db.get_state(f"cooldown:{source}:{symbol}","0")) < config.SIGNAL_COOLDOWN_SECONDS:
            return

        # 3. فحص مصفوفة الارتباط
        open_positions = self.db.get_open_positions()
        open_symbols = [p["symbol"] for p in open_positions if p["source"] == source]
        
        if open_symbols:
            # كلود أشار إلى أن 0.8 صارم جداً، جعلناها 0.92 لتسمح ببعض التنوع
            is_corr, corr_reason = await is_highly_correlated(symbol, open_symbols, self.market, threshold=0.98)
            if is_corr:
                self.db.add_decision(symbol, source, "HOLD", result["score"], f"Blocked by Correlation: {corr_reason}")
                log.info(f"Trade blocked by correlation: {symbol} - {corr_reason}")
                return
        
        # إذا اجتاز كل الفحوصات، نضيف القرار للفتح
        self.db.add_decision(symbol,source,result["action"],result["score"],result["reason"])
        
        # 4. فتح الصفقة
        opened=self.trader.open_position(symbol,primary["price"],primary["atr"],result["side"],source,
                 {"score":result["score"],"timeframes":dirs,"regime":result["regime"],"atr":primary["atr"]},
                 stop_mult=result["stop_mult"],rr=result["rr"],strategy=result["strategy"])
                 
        if opened.get("success"):
            self.db.set_state(f"cooldown:{source}:{symbol}",time.time())
            log.info("Paper position opened: %s %s %s (%s)",source,symbol,result["side"],result["strategy"])
            if self.notifier:
                await self.notifier.notify_trade_opened(opened["position"])

    async def monitor_positions(self):
        sources={p["source"] for p in self.db.get_open_positions()}
        for source in sources:
            prices=await self.market.get_last_prices(source)
            for closed in self.trader.update_market_prices(prices,source):
                if closed and self.notifier:
                    await self.notifier.notify_trade_closed(closed)

    async def _monitor_loop(self):
        while self.running:
            try: await self.monitor_positions()
            except asyncio.CancelledError: raise
            except Exception as exc:
                log.warning("Position monitor error: %s",exc)
            await asyncio.sleep(config.POSITION_CHECK_SECONDS)

    async def scan_once(self):
        self.last_scan=time.time()
        
        # جلب المؤشرات الكلية مرة واحدة لكل مسح
        fng = await self.market.get_fear_and_greed()
        
        for source in config.MARKET_SOURCES:
            try:
                breadth = await self.market.get_market_breadth(source)
                macro_ctx = {"fng": fng, "breadth": breadth}
                
                tickers=await self.market.get_tickers_24h(source)
                closed_positions=self.trader.update_market_prices(tickers,source)
                if self.notifier:
                    for closed in closed_positions:
                        if closed:
                            await self.notifier.notify_trade_closed(closed)
                if self.paused:
                    continue
                symbols=await self.market.liquid_symbols(source)
                for symbol in symbols:
                    try: await self._analyze(symbol,source, macro_ctx)
                    except Exception as exc:
                        log.warning("Analysis skipped %s/%s: %s",source,symbol,exc)
            except Exception as exc:
                log.warning("Source scan failed (%s): %s",source,exc)
        
        # --- إصلاح كلود: حفظ الحالة وتنظيف الجداول القديمة لمنع تضخم قاعدة البيانات ---
        self.db.snapshot()
        self.db.prune()

    def set_paused(self,value):
        self.paused=bool(value); self.db.set_state("paused","1" if value else "0")

    def get_status(self):
        return {"running":self.running,"paused":self.paused,"last_scan":self.last_scan,
                "last_error":self.last_error,"mode":"PAPER SIMULATION"}
