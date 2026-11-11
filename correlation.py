"""Correlation Matrix to prevent over-exposure to the same market trend."""
import pandas as pd
import numpy as np
import config

async def is_highly_correlated(new_symbol, open_symbols, market_data, threshold=0.8):
    if not open_symbols:
        return False, None

    try:
        # جلب بيانات العملة الجديدة (آخر 50 شمعة على إطار الساعة)
        new_df = await market_data.get_klines(new_symbol, "1h", 50, "futures")
        new_returns = new_df["close"].pct_change().dropna()
    except Exception:
        return False, None # إذا فشل الجلب، نسمح بالمرور لتجنب تفويت الفرص

    for symbol in open_symbols:
        if symbol == new_symbol:
            continue
        try:
            # جلب بيانات العملة المفتوحة بالفعل
            sym_df = await market_data.get_klines(symbol, "1h", 50, "futures")
            sym_returns = sym_df["close"].pct_change().dropna()

            # توحيد الطول لضمان المقارنة الصحيحة
            min_len = min(len(new_returns), len(sym_returns))
            if min_len < 20:
                continue

            # حساب معامل ارتباط بيرسون (Pearson Correlation)
            corr = np.corrcoef(new_returns.iloc[-min_len:], sym_returns.iloc[-min_len:])[0, 1]
            
            if corr >= threshold:
                return True, f"Highly correlated with {symbol} ({corr*100:.0f}%)"
        except Exception:
            continue

    return False, None
