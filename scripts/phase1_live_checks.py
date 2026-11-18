#!/usr/bin/env python3
"""Read-only connectivity probe for PUBLIC Binance endpoints (stdlib only; no keys, no orders).
Run on a machine with internet:  python scripts/phase1_live_checks.py
Prints a pass/fail table and exits non-zero on failure. Existing endpoints = used by the Legacy Core today;
'new' endpoints = candidates for Phase 2 (their availability from your host/region is verified here first)."""
import json, sys, time, urllib.error, urllib.request

S, F = "https://api.binance.com", "https://fapi.binance.com"
CHECKS = [
    ("legacy", "spot ping", S + "/api/v3/ping"),
    ("legacy", "spot klines", S + "/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5"),
    ("legacy", "futures klines", F + "/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=5"),
    ("legacy", "futures exchangeInfo", F + "/fapi/v1/exchangeInfo"),
    ("legacy", "funding history", F + "/fapi/v1/fundingRate?symbol=BTCUSDT&limit=3"),
    ("legacy", "futures depth", F + "/fapi/v1/depth?symbol=BTCUSDT&limit=20"),
    ("new", "open interest (now)", F + "/fapi/v1/openInterest?symbol=BTCUSDT"),
    ("new", "open interest hist", F + "/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=5"),
    ("new", "global long/short", F + "/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=5"),
    ("new", "top trader long/short", F + "/futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=1h&limit=5"),
    ("new", "taker buy/sell vol", F + "/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1h&limit=5"),
    ("new", "mark price/basis", F + "/fapi/v1/premiumIndex?symbol=BTCUSDT"),
    ("new", "aggTrades", F + "/fapi/v1/aggTrades?symbol=BTCUSDT&limit=5"),
]

def probe(url):
    t = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-QUANT-X-probe/1"})
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read()
            json.loads(body or b"{}")
            return r.status, int((time.time() - t) * 1000), ""
    except urllib.error.HTTPError as e:
        return e.code, int((time.time() - t) * 1000), "HTTP %s (451/403 = region/IP blocked)" % e.code
    except Exception as e:
        return 0, int((time.time() - t) * 1000), str(e)[:80]

def ws_probe():
    try:
        import asyncio, websockets
    except ImportError:
        return "SKIP (websockets not installed)"
    async def go():
        for url in ("wss://fstream.binance.com/ws/!ticker@arr", "wss://fstream.binance.com/ws/!forceOrder@arr"):
            try:
                async with websockets.connect(url, open_timeout=10) as c:
                    await asyncio.wait_for(c.recv(), 20)
                print("  ws OK   ", url)
            except Exception as e:
                print("  ws FAIL ", url, str(e)[:80]); return False
        return True
    return "OK" if asyncio.run(go()) else "FAIL"

if __name__ == "__main__":
    bad = 0
    for grp, name, url in CHECKS:
        code, ms, note = probe(url)
        ok = code == 200
        bad += (not ok) and grp == "legacy"
        print("%-6s %-24s %s %4s %5dms %s" % (grp, name, "OK  " if ok else "FAIL", code, ms, note))
    print("websocket:", ws_probe())
    sys.exit(1 if bad else 0)
