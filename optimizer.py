import config
import asyncio
from backtest import run_backtest

async def run_auto_tune(db, market, symbol="BTCUSDT", strategy="trend"):
    df = await market.fetch_history(symbol, "1h", "futures", 1000)
    if df.empty: return {"success": False, "error": "No data"}

    best_result = None
    best_params = {}
    
    rsi_values = [10, 14, 21, 28]
    ema_values = [7, 9, 13, 21]

    original_rsi = config.RSI_PERIOD
    original_ema = config.EMA_FAST

    try:
        for rsi in rsi_values:
            for ema in ema_values:
                config.RSI_PERIOD = rsi
                config.EMA_FAST = ema
                try:
                    # استخدام asyncio.to_thread لتشغيل الباكتيست المتزامن دون تعليق السيرفر
                    report = await asyncio.to_thread(run_backtest, df, [strategy], "futures")
                    ret = report["return_pct"]
                    if best_result is None or ret > best_result["return_pct"]:
                        best_result = report
                        best_params = {"RSI": rsi, "EMA": ema}
                except Exception:
                    pass
    finally:
        if not best_params:
            config.RSI_PERIOD = original_rsi
            config.EMA_FAST = original_ema
            return {"success": False, "error": "No profitable combination found"}

        config.RSI_PERIOD = best_params["RSI"]
        config.EMA_FAST = best_params["EMA"]
        
        db.set_state("auto_rsi", best_params["RSI"])
        db.set_state("auto_ema", best_params["EMA"])
        
        return {"success": True, "best_params": best_params, "return_pct": best_result["return_pct"]}
