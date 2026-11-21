"""Pro dashboard: serves the single-page app and a few aggregate JSON endpoints."""
import asyncio, json, os
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import config

router = APIRouter()
_DIR = os.path.dirname(os.path.abspath(__file__))
_NOCACHE = {"Cache-Control": "no-cache"}
_ASSETS = {
    "pro.css": "text/css; charset=utf-8",
    "pro_i18n.js": "application/javascript; charset=utf-8",
    "pro_core.js": "application/javascript; charset=utf-8",
    "pro_charts.js": "application/javascript; charset=utf-8",
    "pro_overview.js": "application/javascript; charset=utf-8",
    "pro_trades.js": "application/javascript; charset=utf-8",
    "pro_signals.js": "application/javascript; charset=utf-8",
    "pro_markets.js": "application/javascript; charset=utf-8",
    "pro_more.js": "application/javascript; charset=utf-8",
    "pro_tools.js": "application/javascript; charset=utf-8",
}


def _read(name):
    with open(os.path.join(_DIR, name), "rb") as handle:
        return handle.read()


def _f(value, default=0.0):
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _epoch(iso):
    try:
        moment = datetime.fromisoformat(iso)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return int(moment.timestamp())
    except Exception:
        return 0


def _meta(row):
    raw = row.get("metadata")
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


@router.get("/", response_class=HTMLResponse)
@router.get("/pro", response_class=HTMLResponse)
async def pro_page():
    try:
        return HTMLResponse(_read("pro.html").decode("utf-8"), headers=_NOCACHE)
    except OSError:
        return HTMLResponse("pro.html is missing from the repository", status_code=500)


@router.get("/pro/{name}")
async def pro_asset(name: str):
    mime = _ASSETS.get(name)
    if not mime:
        return Response(status_code=404)
    try:
        return Response(_read(name), media_type=mime, headers=_NOCACHE)
    except OSError:
        return Response(status_code=404)


async def _prices(engine, positions):
    """Latest price per symbol: WebSocket first (futures), REST as backup."""
    out = {}
    if not positions:
        return out
    try:
        from websocket_streamer import get_live_price
    except Exception:
        get_live_price = lambda symbol: None
    rest = {}
    for pos in positions:
        price = get_live_price(pos["symbol"]) if pos["source"] == "futures" else None
        if not price:
            try:
                if pos["source"] not in rest:
                    rest[pos["source"]] = await asyncio.wait_for(engine.market.get_last_prices(pos["source"]), 6)
                price = (rest[pos["source"]].get(pos["symbol"]) or {}).get("last_price")
            except Exception:
                price = None
        # never fall back to the ENTRY price (it would show a fake 0 P&L): use the last stored mark
        out[pos["id"]] = _f(price, _f(pos.get("mark_price"), _f(pos["entry_price"])))
    return out


def _position(pos, price):
    sign = 1 if pos["side"] == "LONG" else -1
    entry, qty = _f(pos["entry_price"]), _f(pos["quantity"])
    pnl = (price - entry) * qty * sign
    first_stop = _f(pos.get("initial_stop")) or _f(pos["stop_price"])
    unit_risk = abs(entry - first_stop)
    meta = _meta(pos)
    margin = _f(pos["margin_used"])
    return {
        "id": pos["id"], "symbol": pos["symbol"], "source": pos["source"], "side": pos["side"],
        "entry": entry, "price": price, "stop": _f(pos["stop_price"]), "target": _f(pos["target_price"]),
        "qty": qty, "margin": margin, "risk": _f(pos["risk_amount"]), "risk_initial": _f(pos.get("initial_risk")),
        "initial_stop": first_stop, "pnl": pnl, "realized_partial": _f(pos.get("partial_pnl")), "funding": _f(pos.get("funding_paid")),
        "leverage": _f(pos.get("leverage"), 1.0), "liquidation": pos.get("liquidation_price"),
        "scaled_out": bool(pos.get("scale_out_done")),
        "pnl_pct": (pnl / margin * 100) if margin else 0.0,
        "r": ((price - entry) * sign / unit_risk) if unit_risk else 0.0,
        "opened": _epoch(pos["opened_at"]), "strategy": pos.get("strategy") or meta.get("strategy"),
        "score": meta.get("score"), "regime": meta.get("regime"),
    }


@router.get("/api/pro/overview")
async def pro_overview(request: Request):
    state = request.app.state
    db, engine = state.db, state.engine
    portfolio = db.get_portfolio()
    risk = engine.risk.get_risk_status()
    positions = db.get_open_positions()
    prices = await _prices(engine, positions)
    breadth = None
    try:
        breadth = await asyncio.wait_for(engine.market.get_market_breadth("futures"), 4)
    except Exception:
        pass
    return {
        "now": int(datetime.now(timezone.utc).timestamp()),
        "portfolio": portfolio,
        "initial": _f(db.get_state("initial_balance", config.INITIAL_BALANCE)),
        "risk": risk,
        "perf": db.get_performance(),
        "status": engine.get_status(),
        "breadth": breadth,
        "positions": [_position(p, prices.get(p["id"], _f(p.get("mark_price"), _f(p["entry_price"])))) for p in positions],
    }


@router.get("/api/pro/equity")
async def pro_equity(request: Request):
    db = request.app.state.db
    points = [{"t": _epoch(r["created_at"]), "v": _f(r["equity"])} for r in db.equity_history(2000)]
    if len(points) > 400:
        step = len(points) / 400.0
        points = [points[int(i * step)] for i in range(400)] + [points[-1]]
    return points


@router.get("/api/pro/history")
async def pro_history(request: Request):
    db = request.app.state.db
    out = []
    for t in db.get_recent_trades(300):
        if t["status"] != "CLOSED":
            continue
        meta = _meta(t)
        risk = _f(t.get("initial_risk")) or _f(t["risk_amount"])   # the ORIGINAL risk, not what is left after a scale-out
        net = _f(t["net_pnl"])
        out.append({
            "id": t["id"], "symbol": t["symbol"], "source": t["source"], "side": t["side"],
            "entry": _f(t["entry_price"]), "exit": _f(t["exit_price"]), "pnl": net,
            "gross": _f(t.get("gross_pnl")), "fees": _f(t.get("fees_total")), "funding": _f(t.get("funding_paid")),
            "r": (net / risk) if risk else 0.0, "reason": t["exit_reason"] or "",
            "opened": _epoch(t["opened_at"]), "closed": _epoch(t["closed_at"]),
            "strategy": t.get("strategy") or meta.get("strategy") or "-",
        })
    return out


@router.get("/api/pro/signals")
async def pro_signals(request: Request):
    rows = request.app.state.db.get_recent_decisions(500)
    return [{"symbol": r["symbol"], "source": r["source"], "action": r["action"], "score": _f(r["score"]),
             "reason": r["reason"] or "", "t": _epoch(r["created_at"])} for r in rows]


@router.get("/api/pro/system")
async def pro_system(request: Request):
    state = request.app.state
    db, engine = state.db, state.engine
    ml = {"present": False}
    try:
        import ml_filter
        bundle = ml_filter._load_bundle()
        if bundle:
            age = ml_filter.model_age_seconds()
            ml = {"present": True, "valid": bool(bundle.get("valid")), "accuracy": _f(bundle.get("accuracy")),
                  "baseline": _f(bundle.get("baseline")), "rows": int(bundle.get("rows") or 0),
                  "age_hours": (age / 3600.0) if age is not None else None}
    except Exception:
        pass
    blocked, why = False, ""
    try:
        blocked, why = engine.risk.protection_status()
    except Exception:
        pass
    health = {}
    for name in config.STRATEGIES:
        try:
            health[name] = bool(engine.risk.brain.is_strategy_healthy(name))
        except Exception:
            health[name] = True
    return {
        "version": config.APP_VERSION, "status": engine.get_status(), "ml": ml,
        "protection": {"blocked": bool(blocked), "reason": why}, "strategies": health,
        "symbols": len(config.SYMBOLS), "scan_every": config.SCAN_INTERVAL_SECONDS,
        "storage": db.storage_info(), "integrity": db.integrity_report(),
        "telegram": bool(config.TELEGRAM_TOKEN and config.TELEGRAM_ADMIN_ID),   # configured only: no token is ever sent to the browser
        "risk": {"per_trade": config.RISK_PER_TRADE_PCT, "portfolio": config.MAX_PORTFOLIO_RISK_PCT,
                 "daily_limit": config.DAILY_LOSS_LIMIT_PCT, "max_drawdown": config.MAX_DRAWDOWN_PCT,
                 "max_positions": config.MAX_OPEN_POSITIONS},
        "auto": {"strategy": db.get_state("auto_strategy"), "rsi": db.get_state("auto_rsi"), "ema": db.get_state("auto_ema")},
    }
