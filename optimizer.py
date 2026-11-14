import asyncio
import logging
import config
from backtest import run_backtest

log = logging.getLogger(__name__)

async def run_auto_tune(db, market, symbol="BTCUSDT"):
    df = await market.fetch_history(symbol, "1h", "futures", config.BACKTEST_CANDLES)
    if df.empty: return {"success": False, "error": "No data"}

    best_result = None
    best_params = {}
    best_score = -9999.0

    strategies_to_test = ["trend", "mean_reversion", "breakout", "dip_buyer"]
    rsi_values = [10, 14, 21, 28]
    ema_values = [7, 9, 13, 21]

    stats = {"tested": 0, "errors": 0, "no_trades": 0, "too_few_trades": 0, "poor_quality": 0}
    last_error = ""
    best_seen = None

    original_rsi = config.RSI_PERIOD
    original_ema = config.EMA_FAST

    try:
        for strat in strategies_to_test:
            for rsi in rsi_values:
                for ema in ema_values:
                    config.RSI_PERIOD = rsi
                    config.EMA_FAST = ema
                    stats["tested"] += 1
                    try:
                        report = await asyncio.to_thread(run_backtest, df, [strat], "futures")
                    except Exception as exc:
                        stats["errors"] += 1
                        last_error = f"{type(exc).__name__}: {exc}"
                        log.warning("Auto-Tune backtest failed (%s RSI=%s EMA=%s): %s", strat, rsi, ema, last_error)
                        continue

                    ret = report.get("return_pct", 0)
                    pf = report.get("profit_factor")
                    pf = 5.0 if pf is None else min(float(pf), 5.0)
                    win_rate = report.get("win_rate", 0)
                    trades = report.get("trades", 0)
                    dd = report.get("max_drawdown_pct", 0)

                    if trades < 1:
                        stats["no_trades"] += 1
                        continue
                    if best_seen is None or trades > best_seen["trades"]:
                        best_seen = {"strategy": strat, "RSI": rsi, "EMA": ema, "trades": trades, "pf": round(pf, 2)}
                    if trades < config.AUTOTUNE_MIN_TRADES:
                        stats["too_few_trades"] += 1
                        continue
                    if pf < config.AUTOTUNE_MIN_PROFIT_FACTOR or ret <= 0 or dd > config.AUTOTUNE_MAX_DRAWDOWN_PCT:
                        stats["poor_quality"] += 1
                        continue

                    score = ret + (pf * 10) + (win_rate / 2) - (dd * 0.5)
                    if score > best_score:
                        best_score = score
                        best_result = report
                        best_params = {"RSI": rsi, "EMA": ema, "strategy": strat}
    finally:
        config.RSI_PERIOD = original_rsi
        config.EMA_FAST = original_ema

    if not best_params:
        detail = (f"tested {stats['tested']}: {stats['no_trades']} had no trades, "
                  f"{stats['too_few_trades']} had under {config.AUTOTUNE_MIN_TRADES} trades, "
                  f"{stats['poor_quality']} failed quality, {stats['errors']} errors")
        if last_error: detail += f" (last error: {last_error[:80]})"
        log.warning("Auto-Tune found nothing: %s | most active: %s", detail, best_seen)
        return {"success": False, "error": f"No reliable combination found - {detail}", "diagnostics": stats}

    config.RSI_PERIOD = best_params["RSI"]
    config.EMA_FAST = best_params["EMA"]

    db.set_state("auto_rsi", best_params["RSI"])
    db.set_state("auto_ema", best_params["EMA"])
    db.set_state("auto_strategy", best_params["strategy"])

    return {
        "success": True,
        "best_params": best_params,
        "return_pct": best_result.get("return_pct", 0),
        "win_rate": best_result.get("win_rate", 0),
        "trades": best_result.get("trades", 0)
    }
