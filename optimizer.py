"""Auto-Tune: grid search on the first part of the history, validated on the unseen last part.

Everything heavy runs in one worker thread. Experimental RSI/EMA values are applied through a
thread-local override, so the live engine never sees them and config is only changed once a
combination has passed validation.
"""
import asyncio
import logging

import config
from backtest import run_backtest
from indicators import param_override

log = logging.getLogger(__name__)

STRATEGIES_TO_TEST = ("trend", "mean_reversion", "breakout", "dip_buyer")
RSI_VALUES = (10, 14, 21, 28)
EMA_VALUES = (7, 9, 13, 21)
MIN_HISTORY = 700
VALIDATE_TOP = 3

_running = False


def _pf(report):
    value = report.get("profit_factor")
    return 5.0 if value is None else min(float(value), 5.0)


def _run(df, strat, rsi, ema):
    with param_override(rsi=rsi, ema_fast=ema):
        return run_backtest(df, [strat], "futures")


def _sweep(train_df, test_df):
    stats = {"tested": 0, "errors": 0, "no_trades": 0, "too_few_trades": 0, "poor_quality": 0,
             "failed_validation": 0}
    candidates = []
    last_error = ""
    for strat in STRATEGIES_TO_TEST:
        for rsi in RSI_VALUES:
            for ema in EMA_VALUES:
                stats["tested"] += 1
                try:
                    report = _run(train_df, strat, rsi, ema)
                except Exception as exc:
                    stats["errors"] += 1
                    last_error = "%s: %s" % (type(exc).__name__, exc)
                    log.warning("Auto-Tune backtest failed (%s RSI=%s EMA=%s): %s", strat, rsi, ema, last_error)
                    continue
                trades = report.get("trades", 0)
                ret = report.get("return_pct", 0)
                dd = report.get("max_drawdown_pct", 0)
                pf = _pf(report)
                if trades < 1:
                    stats["no_trades"] += 1
                    continue
                if trades < config.AUTOTUNE_MIN_TRADES:
                    stats["too_few_trades"] += 1
                    continue
                if pf < config.AUTOTUNE_MIN_PROFIT_FACTOR or ret <= 0 or dd > config.AUTOTUNE_MAX_DRAWDOWN_PCT:
                    stats["poor_quality"] += 1
                    continue
                score = ret + pf * 10 + report.get("win_rate", 0) / 2 - dd * 0.5
                candidates.append((score, {"strategy": strat, "RSI": rsi, "EMA": ema}, report))

    candidates.sort(key=lambda item: item[0], reverse=True)
    for score, params, train_report in candidates[:VALIDATE_TOP]:
        try:
            test_report = _run(test_df, params["strategy"], params["RSI"], params["EMA"])
        except Exception as exc:
            stats["errors"] += 1
            last_error = "%s: %s" % (type(exc).__name__, exc)
            continue
        if (test_report.get("trades", 0) >= config.AUTOTUNE_TEST_MIN_TRADES
                and test_report.get("return_pct", 0) > 0
                and _pf(test_report) >= config.AUTOTUNE_TEST_MIN_PROFIT_FACTOR):
            return {"params": params, "train": train_report, "test": test_report, "stats": stats}
        stats["failed_validation"] += 1
    return {"params": None, "stats": stats, "last_error": last_error, "candidates": len(candidates)}


async def run_auto_tune(db, market, symbol="BTCUSDT"):
    global _running
    if _running:
        return {"success": False, "error": "Auto-Tune is already running, please wait"}
    _running = True
    try:
        df = await market.fetch_history(symbol, "1h", "futures", config.BACKTEST_CANDLES)
        if df is None or df.empty:
            return {"success": False, "error": "No data"}
        if len(df) < MIN_HISTORY:
            return {"success": False, "error": "Not enough history (%d candles, need %d)" % (len(df), MIN_HISTORY)}

        cut = int(len(df) * (1.0 - config.AUTOTUNE_TEST_FRACTION))
        train_df = df.iloc[:cut].reset_index(drop=True)
        test_df = df.iloc[cut:].reset_index(drop=True)
        result = await asyncio.to_thread(_sweep, train_df, test_df)
    except Exception as exc:
        log.exception("Auto-Tune failed")
        return {"success": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        _running = False

    stats = result["stats"]
    if not result["params"]:
        detail = ("tested %d: %d had no trades, %d had under %d trades, %d failed quality, "
                  "%d failed out-of-sample validation, %d errors") % (
            stats["tested"], stats["no_trades"], stats["too_few_trades"], config.AUTOTUNE_MIN_TRADES,
            stats["poor_quality"], stats["failed_validation"], stats["errors"])
        if result.get("last_error"):
            detail += " (last error: %s)" % result["last_error"][:80]
        log.warning("Auto-Tune found nothing: %s", detail)
        return {"success": False, "error": "No reliable combination found - " + detail, "diagnostics": stats}

    best = result["params"]
    test = result["test"]
    train = result["train"]
    config.RSI_PERIOD = best["RSI"]
    config.EMA_FAST = best["EMA"]
    config.STRATEGIES = (best["strategy"],)
    db.set_state("auto_rsi", best["RSI"])
    db.set_state("auto_ema", best["EMA"])
    db.set_state("auto_strategy", best["strategy"])
    log.info("Auto-Tune applied: %s", best)
    return {
        "success": True,
        "best_params": best,
        "return_pct": test.get("return_pct", 0),
        "win_rate": test.get("win_rate", 0),
        "trades": test.get("trades", 0),
        "train_return_pct": train.get("return_pct", 0),
        "train_trades": train.get("trades", 0),
        "note": "Numbers are out-of-sample (unseen data).",
    }
