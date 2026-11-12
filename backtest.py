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
    fee = config.fee_rate(source) if fee is None else fee
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

        if pos:
            bars_in_trade += 1
            
            if config.SCALE_OUT_ENABLED and not pos["partial_done"]:
                sign = 1 if pos["side"] == "LONG" else -1
                initial_risk = abs(pos["entry"] - pos["initial_stop"])
                if initial_risk > 0:
                    gain_r_high = (hi[i] - pos["entry"]) * sign / initial_risk
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
                        pos["stop"] = pos["entry"]
                        pos["partial_done"] = True

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
                # --- تم تمرير fee هنا ---
                pos["stop"] = next_stop(pos["side"], pos["entry"], pos["initial_stop"], pos["stop"], cl[i], trailing, fee)
            if pos and i == n - 1:
                close_pos(i, cl[i], "END_OF_DATA")

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

        if pos is None and i < n - 1 and i >= blocked_until and dd_until < 0:
            if not np.isfinite(ind["atr"].values[i]) or ind["atr"].values[i] <= 0:
                continue
            snap = snapshot(ind, i)
            d = direction(snap)
            
            ctx = {"source": source, "primary": snap, "dirs": [d, htf[i]], "news_risk": 0.0,
                   "hour_utc": int((ts[i] // 3600000) % 24),
                   "fear_greed": 50, "breadth": 50.0, "funding_rate": 0.0}
                   
            sig = select_signal(ctx, strategies)
            if sig["action"] != "HOLD":
                pending = {"side": sig["side"], "strategy": sig["strategy"], "regime": sig["regime"],
                           "stop_mult": sig["stop_mult"], "rr": sig["rr"],
                           "atr": snap["atr"], "price": snap["price"]}

    return build_report(trades, np.array(curve), initial, ind, warmup, base_ms, bars_in_trade, strategies)

def _profit_factor(vals):
    gp = sum(x for x in vals if x > 0)
    gl = abs(sum(x for x in vals if x < 0))
    return (gp / gl) if gl > 0 else (None if gp > 0 else 0.0)

def _max_drawdown(curve):
    if len(curve) == 0: return 0.0
    peaks = np.maximum.accumulate(curve)
    return float(((peaks - curve) / peaks).max() * 100)

def _monte_carlo(trades, initial, sims=1000, seed=7):
    if len(trades) < 10: return None
    rets = np.array([t["ret"] for t in trades])
    rng = np.random.default_rng(seed)
    finals, dds = [], []
    for _ in range(sims):
        seq = rng.choice(rets, size=len(rets), replace=True)
        eq = initial * np.cumprod(1 + seq)
        eq = np.concatenate([[initial], eq])
        finals.append((eq[-1] / initial - 1) * 100)
        dds.append(_max_drawdown(eq))
    return {"return_p5": float(np.percentile(finals, 5)), "return_median": float(np.percentile(finals, 50)),
            "return_p95": float(np.percentile(finals, 95)), "max_dd_p95": float(np.percentile(dds, 95)),
            "prob_loss": float(np.mean(np.array(finals) < 0) * 100)}

def build_report(trades, curve, initial, ind, warmup, base_ms, bars_in_trade, strategies):
    nets = [t["net"] for t in trades]
    rs = [t["r"] for t in trades]
    wins = [x for x in nets if x > 0]
    final = float(curve[-1]) if len(curve) else initial
    rets = np.diff(curve) / curve[:-1] if len(curve) > 2 else np.array([0.0])
    per_year = BARS_PER_YEAR.get(base_ms, 8760)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(per_year)) if rets.std() > 0 else 0.0
    by_strategy = {}
    for name in sorted({t["strategy"] for t in trades}):
        v = [t for t in trades if t["strategy"] == name]
        vn = [t["net"] for t in v]
        by_strategy[name] = {"trades": len(v), "win_rate": sum(1 for x in vn if x > 0) / len(v) * 100,
                             "profit_factor": _profit_factor(vn), "net": sum(vn),
                             "avg_r": float(np.mean([t["r"] for t in v]))}
    n_total = len(curve)
    seg_size = max(1, (len(ind) - warmup) // 4)
    segments = []
    for k in range(4):
        a, b = warmup + k * seg_size, warmup + (k + 1) * seg_size if k < 3 else len(ind) + 1
        v = [t["net"] for t in trades if a <= t["entry_idx"] < b]
        segments.append({"trades": len(v), "net": sum(v), "profit_factor": _profit_factor(v)})
    streak = best = 0
    for x in nets:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    mc = _monte_carlo(trades, initial)
    report = {
        "candles": len(ind) - warmup, "trades": len(trades), "initial": initial, "final": final,
        "return_pct": (final / initial - 1) * 100, "net_pnl": final - initial,
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
        "profit_factor": _profit_factor(nets), "expectancy_r": float(np.mean(rs)) if rs else 0.0,
        "avg_win": float(np.mean(wins)) if wins else 0.0,
        "avg_loss": float(np.mean([x for x in nets if x < 0])) if any(x < 0 for x in nets) else 0.0,
        "max_drawdown_pct": _max_drawdown(curve), "sharpe": sharpe,
        "longest_losing_streak": best, "exposure_pct": bars_in_trade / n_total * 100 if n_total else 0.0,
        "buy_hold_pct": float((ind.close.iloc[-1] / ind.close.iloc[warmup] - 1) * 100),
        "by_strategy": by_strategy, "segments": segments, "monte_carlo": mc,
        "strategies": list(strategies or config.STRATEGIES),
    }
    pf = report["profit_factor"]
    seg_ok = sum(1 for s in segments if s["trades"] > 0 and s["net"] > 0)
    report["checks"] = {
        "at_least_30_trades": len(trades) >= 30,
        "profit_factor_above_1.3": (pf is None and len(wins) > 0) or (pf is not None and pf >= 1.3),
        "positive_expectancy": report["expectancy_r"] > 0.1,
        "drawdown_below_20pct": report["max_drawdown_pct"] < 20,
        "profitable_in_3_of_4_periods": seg_ok >= 3,
        "monte_carlo_5th_pct_positive": bool(mc and mc["return_p5"] > 0),
    }
    report["trade_list"] = trades
    return report

def compare_strategies(df, source="futures", **kw):
    out = {}
    for name in config.STRATEGIES:
        out[name] = run_backtest(df, [name], source, **kw)
    out["all"] = run_backtest(df, list(config.STRATEGIES), source, **kw)
    return out

def format_report(symbol, r, interval="1h"):
    pf = r["profit_factor"]
    pf_txt = "inf" if pf is None else f"{pf:.2f}"
    lines = [f"BACKTEST {symbol} {interval} | {r['candles']} candles | strategies: {', '.join(r['strategies'])}",
             f"Trades: {r['trades']} | Win rate: {r['win_rate']:.1f}% | PF: {pf_txt}",
             f"Return: {r['return_pct']:+.1f}% (buy&hold {r['buy_hold_pct']:+.1f}%)",
             f"Expectancy: {r['expectancy_r']:+.2f}R | Max DD: {r['max_drawdown_pct']:.1f}% | Sharpe: {r['sharpe']:.2f}",
             f"Losing streak: {r['longest_losing_streak']} | Time in market: {r['exposure_pct']:.0f}%"]
    for name, s in r["by_strategy"].items():
        spf = "inf" if s["profit_factor"] is None else f"{s['profit_factor']:.2f}"
        lines.append(f"- {name}: {s['trades']} trades, WR {s['win_rate']:.0f}%, PF {spf}, {s['net']:+.2f} USDT")
    seg = " | ".join(f"{s['net']:+.1f}" for s in r["segments"])
    lines.append(f"Net by period (4 parts): {seg}")
    mc = r["monte_carlo"]
    if mc:
        lines.append(f"Monte Carlo: median {mc['return_median']:+.1f}%, worst-5% {mc['return_p5']:+.1f}%, "
                     f"95% max DD {mc['max_dd_p95']:.1f}%, loss probability {mc['prob_loss']:.0f}%")
    else:
        lines.append("Monte Carlo: need at least 10 trades")
    passed = sum(r["checks"].values())
    lines.append(f"Quality checks passed: {passed}/{len(r['checks'])}")
    for k, v in r["checks"].items():
        lines.append(f"{'OK ' if v else 'NO '} {k}")
    lines.append("Past results do not guarantee future performance.")
    return "\n".join(lines)
