"""Asynchronous paper-simulation engine."""
import asyncio, logging, time
import config
from market_data import MarketData
from indicators import calculate_indicators, direction
from decision_engine import calculate_technical_score, evaluate_setup
from risk_manager import RiskManager
from paper_trading import PaperTrader
from news_engine import NewsEngine

log=logging.getLogger(__name__)

class Engine:
    def __init__(self,database,market=None,news=None):
        self.db=database; self.market=market or MarketData()
        self.risk=RiskManager(database); self.trader=PaperTrader(database,self.risk)
        self.news=news or NewsEngine()
        self.running=False; self.task=None; self.last_scan=None; self.last_error=None
        self.paused=self.db.get_state("paused","0")=="1"
        self.notifier=None

    async def start(self):
        await self.market.start()
        await self.news.start()
        self.running=True
        if self.task is None or self.task.done():
            self.task=asyncio.create_task(self._run())

    async def stop(self):
        self.running=False
        if self.task:
            self.task.cancel()
            try: await self.task
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

    async def _analyze(self,symbol,source):
        frames={}
        for tf in config.TIMEFRAMES:
            frames[tf]=await self._indicators(symbol,source,tf)
        dirs=[direction(frames[x]) for x in config.TIMEFRAMES]
        primary=frames[config.PRIMARY_TIMEFRAME]
        technical=calculate_technical_score(primary)
        side=technical["side"]
        confirmed=(len(set(dirs))==1 and dirs[0] in ("BULLISH","BEARISH") and
                   (side=="LONG" if dirs[0]=="BULLISH" else side=="SHORT"))
        news=await self.news.get_news_risk(symbol)
        result=evaluate_setup(technical,source,confirmed,news.get("risk",0))
        self.db.add_decision(symbol,source,result["action"],technical["score"],result["reason"])
        if self.paused or result["action"]=="HOLD":
            return
        if time.time()-float(self.db.get_state(f"cooldown:{source}:{symbol}","0")) < config.SIGNAL_COOLDOWN_SECONDS:
            return
        opened=self.trader.open_position(symbol,primary["price"],primary["atr"],
                 result["side"],source,{"score":technical["score"],"timeframes":dirs})
        if opened.get("success"):
            self.db.set_state(f"cooldown:{source}:{symbol}",time.time())
            log.info("Paper position opened: %s %s %s",source,symbol,result["side"])
            if self.notifier:
                await self.notifier.notify_trade_opened(opened["position"])

    async def scan_once(self):
        self.last_scan=time.time()
        for source in config.MARKET_SOURCES:
            try:
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
                    try: await self._analyze(symbol,source)
                    except Exception as exc:
                        log.warning("Analysis skipped %s/%s: %s",source,symbol,exc)
            except Exception as exc:
                log.warning("Source scan failed (%s): %s",source,exc)
        self.db.snapshot()

    def set_paused(self,value):
        self.paused=bool(value); self.db.set_state("paused","1" if value else "0")

    def get_status(self):
        return {"running":self.running,"paused":self.paused,"last_scan":self.last_scan,
                "last_error":self.last_error,"mode":"PAPER SIMULATION"}
