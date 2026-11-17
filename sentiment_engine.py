# sentiment_engine.py
#
# Add this line to requirements.txt (aiohttp should already be there):
#     nltk
#
# The VADER lexicon (a small text file) is downloaded automatically on first use.

import asyncio
import logging
import time
import xml.etree.ElementTree as ElementTree

import aiohttp

try:
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]
MAX_HEADLINES_PER_FEED = 20
TOP_NEWS_COUNT = 5
REQUEST_TIMEOUT_SECONDS = 10
CACHE_SECONDS = 300
BULLISH_THRESHOLD = 0.15
BEARISH_THRESHOLD = -0.15
log = logging.getLogger(__name__)
USER_AGENT = "Mozilla/5.0 (compatible; AIQuantX/1.0)"

_analyzer = None
_cache = {"time": None, "result": None}


def _neutral_result():
    """A genuinely computed neutral reading is not the same as 'unavailable' (which is None)."""
    return {"score": 0.0, "state": "NEUTRAL", "top_news": []}


def _get_analyzer():
    """Create the VADER analyzer once, downloading the lexicon if it is missing."""
    global _analyzer
    if _analyzer is not None:
        return _analyzer
    if not NLTK_AVAILABLE:
        return None
    try:
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        _analyzer = SentimentIntensityAnalyzer()
        return _analyzer
    except Exception as error:
        log.warning("VADER unavailable: %s", error)
        return None


async def _fetch_headlines(session, url):
    """Download one RSS feed and return a list of headline strings."""
    try:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            content = await response.read()
        root = ElementTree.fromstring(content)
        headlines = []
        for item in root.iter("item"):
            title_element = item.find("title")
            if title_element is not None and title_element.text:
                title = title_element.text.strip()
                if title:
                    headlines.append(title)
            if len(headlines) >= MAX_HEADLINES_PER_FEED:
                break
        return headlines
    except Exception as error:
        log.warning("Sentiment feed failed %s: %s", url, error)
        return []


def _analyze(analyzer, headlines):
    """Score every headline and build the final result dictionary."""
    scored = []
    for headline in headlines:
        compound = analyzer.polarity_scores(headline)["compound"]
        scored.append((compound, headline))

    if not scored:
        return None          # no headlines = no opinion, never a fabricated neutral score

    average = sum(score for score, _ in scored) / len(scored)

    if average >= BULLISH_THRESHOLD:
        state = "BULLISH"
    elif average <= BEARISH_THRESHOLD:
        state = "BEARISH"
    else:
        state = "NEUTRAL"

    # Most emotionally charged headlines first.
    scored.sort(key=lambda pair: abs(pair[0]), reverse=True)
    top_news = [headline for _, headline in scored[:TOP_NEWS_COUNT]]

    return {"score": round(average, 4), "state": state, "top_news": top_news}


async def get_market_sentiment():
    """Return the overall crypto news sentiment.

    Result: {"score": 0.25, "state": "BULLISH", "top_news": ["headline 1", "headline 2"]}
    Returns None when sentiment cannot be computed (no VADER, feeds down, no headlines):
    callers must treat None as "no opinion", never as a neutral score.
    Results are cached for 5 minutes to avoid hammering the feeds.
    """
    try:
        now = time.monotonic()
        if _cache["result"] is not None and _cache["time"] is not None:
            if now - _cache["time"] < CACHE_SECONDS:
                return _cache["result"]

        loop = asyncio.get_running_loop()
        analyzer = await loop.run_in_executor(None, _get_analyzer)
        if analyzer is None:
            return None

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            results = await asyncio.gather(
                *[_fetch_headlines(session, url) for url in RSS_FEEDS]
            )

        headlines = []
        seen = set()
        for feed_headlines in results:
            for headline in feed_headlines:
                if headline not in seen:
                    seen.add(headline)
                    headlines.append(headline)

        if not headlines:
            return None

        result = _analyze(analyzer, headlines)
        _cache["time"] = now
        _cache["result"] = result
        return result
    except Exception as error:
        log.warning("Sentiment failed: %s", error)
        return None
