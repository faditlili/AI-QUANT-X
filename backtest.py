"""Backtest engine: same strategies, risk sizing, Scale-Out and stop logic as the live bot."""
import numpy as np
import pandas as pd
import config
from indicators import compute_frame, snapshot, direction
from strategies import select_signal
from trade_management import next_stop

BARS_PER_YEAR = {3600000: 8760, 900000: 35040, 14400000: 2190}

def _htf_directions(ind, ts, base_ms, htf_ms=4 * 3600000):
    n = len(ind)
    neutral = ["NEUTRAL"] * n
    if htf_ms <= base_ms:
        return neutral
    idx = pd.to_datetime(ts, unit="ms")
    o = ind.set_index(idx)[["open", "high", "low", "close", "volume"]]
    htf = o.resample(f"{htf_ms // 3600000}h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    if len(htf) < config.MIN_CANDLES_REQUIRED:
        return neutral
    htf = htf.copy()
    htf["timestamp"] = htf.index.values.astype("datetime64[ms]").astype("int64")
    hind = compute_frame(htf.reset_index(drop=True))
    hts = hind["timestamp"].values.astype("int64")
    bull = ((hind.ema9 > hind.ema21) & (hind.ema21 > hind.ema50) & (hind.plus_di >= hind.minus_di)).values
    bear = ((hind.ema9 < hind.ema21) & (hind.ema21 < hind.ema50) & (hind.minus_di > hind.plus_di)).values
    labels = np.where(bull, "BULLISH", np.where(bear, "BEARISH", "NEUTRAL"))
    pos = np.searchsorted(hts, ts + base_ms - htf_ms, side="right") - 1
    return [labels[p] if p >= 0 else "NEUTRAL" for p in pos]

def run_backtest(df, strategies=None, source="futures", initial_balance=None, warmup=120,
                 fee=None, slippage_bps=None, trailing=None, risk_pct=None, alloc_pct=None):
    initial = float(initial_balance or config.INITIAL_BALANCE)
    fee = config.FEE_RATE if fee is None else fee
    slip = (config.SLIPPAGE_BPS if slippage_bps is None else slippage_bps) / 10000
    trailing = config.TRAILING_ENABLED if trailing is None else trailing
    risk_pct = config.RISK_PER_TRADE_PCT if risk_pct is None else risk_pct
    alloc_pct = config.MAX_ALLOCATION_PCT if alloc_pct is None else alloc_pct

    df = df.copy()
    if "timestamp" not in df.columns:
        df["timestamp"] = np.arange(len(df)) * 3600000
    ind = compute_frame(df)
    n = len(ind)
    if n < warmup + 50:
        raise ValueError(f"Not enough history: {n} candles")
    ts = ind["timestamp"].values.astype("int64")
    base_ms = int(np.median(np.diff(ts)))
    htf = _htf_directions(ind, ts, base_ms)
    op, hi, lo, cl = (ind[c].values for c in ("open", "high", "low", "close"))
    pause_bars = max(1, int(config.LOSS_STREAK_PAUSE_SECONDS * 1000 // base_ms))
    dd_pause_bars = max(1, int(config.DRAWDOWN_PAUSE_SECONDS * 1000 // base_ms))

    equity, peak = initial, initial
    pos, pending = None, None
    trades, curve = [], []
    loss_streak, blocked_until, dd_until = 0, -1, -1
    bars_in_trade = 0

    def close_pos(i, exit_price, reason):
        nonlocal equity, pos, loss_streak, blocked_until
        sign = 1 if pos["side"] == "LONG" else -1
        gross = (exit_price - pos["entry"]) * pos["qty"] * sign
        exit_fee = exit_price * pos["qty"] * fee
        equity += gross - exit_fee
        
        # احتساب الربح الجزئي + المتبقي
        net_total = gross - exit_fee - pos["entry_fee"] + pos.get("partial_pnl", 0.0)
        
        risk_amt = pos["qty"] * abs(pos["entry"] - pos["initial_stop"])
        trades.append({"entry_idx": pos["entry_idx"], "exit_idx": i, "side": pos["side"],
                       "strategy": pos["strategy"], "regime": pos["regime"], "entry": pos["entry"],
                       "exit": exit_price, "qty": pos["qty"], "net": net_total,
                       "r": net_total / risk_amt if risk_amt > 0 else 0.0,
                       "ret": net_total / pos["equity_at_entry"], "reason": reason,
                       "bars": i - pos["entry_idx"]})
        if net_total < 0:
            loss_streak += 1
            if loss_streak >= config.MAX_CONSECUTIVE_LOSSES:
                blocked_until = i + pause_bars
                loss_streak = 0
        else:
            loss_streak = 0
        pos = None

    for i in range(warmup, n):
        # 1) fill a pending signal at this candle's open
        if pending and pos is None:
            sign = 1 if pending["side"] == "LONG" else -1
            entry = op[i] * (1 + sign * slip)
            stop_dist = pending["atr"] * pending["stop_mult"]
            stop = pending["price"] - sign * stop_dist
            target = pending["price"] + sign * stop_dist * pending["rr"]
            dist = abs(entry - stop)
            if dist > 0:
                qty = min(equity * risk_pct / 100 / dist, equity * alloc_pct / 100 / entry)
                notional = qty * entry
                if qty > 0 and notional * (1 + fee) <= equity:
                    entry_fee = notional * fee
                    equity -= entry_fee
                    pos = {"side": pending["side"], "entry": entry, "qty": qty, "stop": stop,
                           "initial_stop": stop, "target": target, "entry_idx": i,
                           "entry_fee": entry_fee, "strategy": pending["strategy"],
                           "regime": pending["regime"], "equity_at_entry": equity + entry_fee,
                           "partial_pnl": 0.0, "partial_done": False}
        pending = None

        # 2) manage the open position inside this candle
        if pos:
            bars_in_trade += 1
            
            # --- محاكاة البيع الجزئي (Scale-Out) مطابقة للبوت الحي ---
            if config.SCALE_OUT_ENABLED and not pos["partial_done"]:
                sign = 1 if pos["side"] == "LONG" else -1
                initial_risk = abs(pos["entry"] - pos["initial_stop"])
                if initial_risk > 0:
                    gain_r_high = (hi[i] - pos["entry"]) * sign / initial_risk
                    gain_r_low = (lo[i] - pos["entry"]) * sign / initial_risk
                    if gain_r_high >= config.SCALE_OUT_R:
                        close_qty = pos["qty"] * config.SCALE_OUT_PCT
                        exit_price = pos["entry"] + sign * initial_risk * config.SCALE_OUT_R
                        gross = (exit_price - pos["entry"]) * close_qty * sign
                        exit_fee = exit_price * close_qty * fee
                        entry_fee_part = pos["entry_fee"] * config.SCALE_OUT_PCT
                        
                        equity += gross - exit_fee
                        pos["partial_pnl"] += (gross - exit_fee - entry_fee_part)
                        pos["qty"] -= close_qty
                        pos["entry_fee"] -= entry_fee_part
                        pos["stop"] = pos["entry"] # نقل الوقف للدخول
                        pos["partial_done"] = True

            # فحص ضرب الهدف أو الوقف
            if pos["side"] == "LONG":
                if op[i] <= pos["stop"]:
                    close_pos(i, op[i] * (1 - slip), "STOP_LOSS" if pos["stop"] == pos["initial_stop"] else "TRAILING_STOP")
                elif lo[i] <= pos["stop"]:
                    close_pos(i, pos["stop"] * (1 - slip), "STOP_LOSS" if pos["stop"] == pos["initial_stop"] else "TRAILING_STOP")
                elif op[i] >= pos["target"]:
                    close_pos(i, op[i], "TAKE_PROFIT")
                elif hi[i] >= pos["target"]:
                    close_pos(i, pos["target"], "TAKE_PROFIT")
            else:
                if op[i] >= pos["stop"]:
                    close_pos(i, op[i] * (1 + slip), "STOP_LOSS" if pos["stop"] == pos["initial_stop"] else "TRAILING_STOP")
                elif hi[i] >= pos["stop"]:
                    close_pos(i, pos["stop"] * (1 + slip), "STOP_LOSS" if pos["stop"] == pos["initial_stop"] else "TRAILING_STOP")
                elif op[i] <= pos["target"]:
                    close_pos(i, op[i], "TAKE_PROFIT")
                elif lo[i] <= pos["target"]:
                    close_pos(i, pos["target"], "TAKE_PROFIT")
                    
            if pos:
                pos["stop"] = next_stop(pos["side"], pos["entry"], pos["initial_stop"],
                                        pos["stop"], cl[i], trailing)
            if pos and i == n - 1:
                close_pos(i, cl[i], "END_OF_DATA")

        # 3) mark to market, update protections
        unreal = 0.0
        if pos:
            sign = 1 if pos["side"] == "LONG" else -1
            unreal = (cl[i] - pos["entry"]) * pos["qty"] * sign
        mtm = equity + unreal
        curve.append(mtm)
        peak = max(peak, mtm)
        if dd_until < 0 and pos is None and (peak - mtm) / peak * 100 >= config.MAX_DRAWDOWN_PCT:
            dd_until = i + dd_pause_bars
        if dd_until >= 0 and i >= dd_until:
            peak, dd_until = mtm, -1

        # 4) look for a new signal on the closed candle (filled next open)
        if pos is None and i < n - 1 and i >= blocked_until and dd_until < 0:
            if not np.isfinite(ind["atr"].values[i]) or ind["atr"].values[i] <= 0:
                continue
            snap = snapshot(ind, i)
            d = direction(snap)
            
            # تمرير وقت الشمعة للباكتيست
            ctx = {"source": source, "primary": snap, "dirs": [d, htf[i]], "news_risk": 0.0,
                   "hour_utc": int((ts[i] // 3600000) % 24),
                   "fear_greed": 50, "breadth": 50.0, "funding_rate": 0.0}
                   
            sig = select_signal(ctx, strategies)
            if sig["action"] != "HOLD":
                pending = {"side": sig["side"], "strategy": sig["strategy"], "regime": sig["regime"],
                           "stop_mult": sig["stop_mult"], "rr": sig["rr"],
                           "atr": snap["atr"], "price": snap["price"]}

    return build_report(trades, np.array(curve), initial, ind, warmup, base_ms, bars_in_trade, strategies)

# ... (باقي الدوال كما هي: _profit_factor, _max_drawdown, _monte_carlo, build_report, compare_strategies, fetch_history, format_report)
# ملاحظة: تأكد من أن دالة fetch_history تحتوي على سطر taker_buy_volume الذي أضفناه سابقاً.
