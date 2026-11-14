import config
import asyncio
from backtest import run_backtest

async def run_auto_tune(db, market, symbol="BTCUSDT"):
    df = await market.fetch_history(symbol, "1h", "futures", 1000)
    if df.empty: return {"success": False, "error": "No data"}

    best_result = None
    best_params = {}
    best_score = -9999
    
    strategies_to_test = ["trend", "mean_reversion", "breakout", "dip_buyer"]
    rsi_values = [10, 14, 21, 28]
    ema_values = [7, 9, 13, 21]

    original_rsi = config.RSI_PERIOD
    original_ema = config.EMA_FAST

    try:
        for strat in strategies_to_test:
            for rsi in rsi_values:
                for ema in ema_values:
                    config.RSI_PERIOD = rsi
                    config.EMA_FAST = ema
                    try:
                        report = await asyncio.to_thread(run_backtest, df, [strat], "futures")
                        
                        ret = report.get("return_pct", 0)
                        pf = report.get("profit_factor", 0) or 0
                        win_rate = report.get("win_rate", 0)
                        trades = report.get("trades", 0)
                        
                        if trades < 1:
                            continue
                            
                        score = ret + (pf * 10) + (win_rate / 2)
                        
                        if score > best_score:
                            best_score = score
                            best_result = report
                            best_params = {"RSI": rsi, "EMA": ema, "strategy": strat}
                    except Exception:
                        pass
    finally:
        if not best_params:
            config.RSI_PERIOD = original_rsi
            config.EMA_FAST = original_ema
            return {"success": False, "error": "No reliable combination found"}

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
