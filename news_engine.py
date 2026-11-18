"""Optional public RSS headline risk filter. Disabled by default."""
import aiohttp, asyncio, re, xml.etree.ElementTree as ET, time
import config

FEEDS=("https://www.coindesk.com/arc/outboundfeeds/rss/","https://cointelegraph.com/rss")
RISK_WORDS=("hack","exploit","lawsuit","bankruptcy","ban","fraud","scam","اختراق","حظر","إفلاس")  # kept: public name

# English risk words are matched as WHOLE WORDS (with common inflections). The old substring test flagged
# "Bank of America" / "Urban" (ban), "Exploitation", "Hackathon", etc. Arabic terms keep substring matching
# because Arabic attaches prefixes (ال، و، ب) directly to the word.
_RISK_EN=re.compile(
    r"\b(?:hack(?:s|ed|er|ers|ing)?|exploit(?:s|ed|ing)?|lawsuits?|bankrupt(?:cy|cies)?|"
    r"ban(?:s|ned|ning)?|fraud(?:s)?|fraudulent|scam(?:s|med|mer|mers)?)\b", re.IGNORECASE)
_RISK_AR=tuple(w for w in RISK_WORDS if not w.isascii())

# Ticker -> names used in headlines. A headline about "Bitcoin" never contains "BTC" literally.
COIN_ALIASES={
    "BTC":("bitcoin",),"ETH":("ethereum","ether"),"BNB":("bnb chain","binance coin"),"SOL":("solana",),
    "XRP":("ripple",),"ADA":("cardano",),"AVAX":("avalanche",),"DOGE":("dogecoin",),"DOT":("polkadot",),
    "LINK":("chainlink",),"POL":("polygon",),"TON":("toncoin","the open network"),"SHIB":("shiba inu",),
    "LTC":("litecoin",),"BCH":("bitcoin cash",),"UNI":("uniswap",),"NEAR":("near protocol",),
    "APT":("aptos",),"ICP":("internet computer",),"SUI":("sui network",),"ARB":("arbitrum",),
    "OP":("optimism",),"INJ":("injective",),"ATOM":("cosmos",),"FIL":("filecoin",),"STX":("stacks",),
    "IMX":("immutable",),"RENDER":("render network",),"FET":("fetch.ai",),"WLD":("worldcoin",),
    "TRX":("tron",),"ETC":("ethereum classic",),"XLM":("stellar",),"HBAR":("hedera",),"AAVE":("aave",),
    "ALGO":("algorand",),"VET":("vechain",),"CRV":("curve finance",),"LDO":("lido",),"SEI":("sei network",),
    "TIA":("celestia",),"RUNE":("thorchain",),"GALA":("gala games",),"SAND":("the sandbox",),
    "MANA":("decentraland",),"AXS":("axie infinity",),"ENA":("ethena",),"ONDO":("ondo finance",),
    "PEPE":("pepe coin",),
}
_QUOTES=("USDT","USDC","BUSD","FDUSD")

def _base_ticker(symbol):
    base=str(symbol or "").upper()
    for q in _QUOTES:
        if base.endswith(q) and len(base)>len(q):
            base=base[:-len(q)]; break
    return re.sub(r"^(?:1000000|1000|1M)(?=[A-Z])","",base)   # 1000PEPEUSDT -> PEPE

def _symbol_matchers(symbol):
    """(ticker_regex, alias_regex) for one symbol. Tickers match UPPERCASE whole words only (so 'near' or
    'link' in ordinary prose never matches); aliases match case-insensitively as whole phrases."""
    base=_base_ticker(symbol)
    if len(base)<2: return None,None
    t=re.compile(r"(?<![A-Za-z0-9])\$?"+re.escape(base)+r"(?![A-Za-z0-9])")
    names=COIN_ALIASES.get(base,())
    a=re.compile(r"\b(?:"+"|".join(re.escape(n) for n in names)+r")\b",re.IGNORECASE) if names else None
    return t,a

def mentions_symbol(title,symbol):
    """True only if the headline really refers to this coin (whole-word ticker or known name)."""
    t,a=_symbol_matchers(symbol)
    if t is None: return False
    return bool(t.search(title) or (a and a.search(title)))

def is_risk_headline(title):
    low=title.lower()
    return bool(_RISK_EN.search(title) or any(w in low for w in _RISK_AR))

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
        relevant=[x for x in self.items if not symbol or mentions_symbol(x,symbol)]
        hits=sum(is_risk_headline(x) for x in relevant)
        risk=min(1.0,hits/max(1,len(relevant))) if relevant else 0.0
        return {"available":bool(config.NEWS_ENABLED and self.updated),"risk":risk,"summary":" | ".join(relevant[:3])}

    def get_status(self):
        return {"enabled":config.NEWS_ENABLED,"items":len(self.items),"updated":self.updated}

    async def close(self):
        if self.session:
            await self.session.close(); self.session=None
