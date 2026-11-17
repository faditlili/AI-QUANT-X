"""Optional public RSS headline risk filter. Disabled by default."""
import aiohttp, asyncio, xml.etree.ElementTree as ET, time
import config

FEEDS=("https://www.coindesk.com/arc/outboundfeeds/rss/","https://cointelegraph.com/rss")
RISK_WORDS=("hack","exploit","lawsuit","bankruptcy","ban","fraud","scam","اختراق","حظر","إفلاس")

class NewsEngine:
    def __init__(self):
        self.session=None; self.updated=0; self.items=[]

    async def start(self):
        if config.NEWS_ENABLED and self.session is None:
            self.session=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.NEWS_TIMEOUT_SECONDS))

    async def refresh(self):
        if not config.NEWS_ENABLED:
            return
        await self.start()
        collected=[]
        for url in FEEDS:
            try:
                async with self.session.get(url) as r:
                    if r.status==200:
                        root=ET.fromstring(await r.text())
                        for item in root.findall(".//item"):
                            title=(item.findtext("title") or "")[:300]
                            collected.append(title)
            except Exception:
                continue
        self.items=collected[:40]; self.updated=time.time()

    async def get_news_risk(self,symbol=None):
        if config.NEWS_ENABLED and time.time()-self.updated>config.NEWS_REFRESH_SECONDS:
            await self.refresh()
        relevant=[x for x in self.items if not symbol or symbol[:3].lower() in x.lower()]
        hits=sum(any(word in x.lower() for word in RISK_WORDS) for x in relevant)
        risk=min(1.0,hits/max(1,len(relevant))) if relevant else 0.0
        return {"available":bool(config.NEWS_ENABLED and self.updated),"risk":risk,"summary":" | ".join(relevant[:3])}

    def get_status(self):
        return {"enabled":config.NEWS_ENABLED,"items":len(self.items),"updated":self.updated}

    async def close(self):
        if self.session:
            await self.session.close(); self.session=None
