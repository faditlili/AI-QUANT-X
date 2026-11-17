"""Backtest engine that runs the SAME rules as the live bot.

Shared with the live engine (not re-implemented): strategies.select_signal, accounting.size_position,
accounting.check_portfolio_limits (10% aggregate risk cap, max positions, MAX_SAME_SIDE, duplicate
symbol, cash), accounting fees/slippage/liquidation/funding maths, trade_management.next_stop,
brain.kelly_risk_pct, drawdown / loss-streak / strategy / pair-lock / cooldown protections.

Execution model (documented assumptions - see FINAL_AUDIT.md):
* signal on the CLOSE of bar i, entry at the OPEN of bar i+1 with adverse slippage (no look-ahead);
* stops, targets and scale-outs are checked on bar highs/lows; when one bar touches both the stop and
  the target/scale-out level the STOP is assumed to be hit first (conservative, fixed, declared);
* a gap through the stop fills at the open, not at the stop; every exit pays slippage and fees;
* stop changes (break-even after a scale-out, trailing) take effect from the NEXT bar;
* futures funding is applied only when a funding history is supplied (otherwise reported as NOT included);
* NOT modelled (live-only data with no history): ML probability, news sentiment, order-book walls,
  fear & greed, market breadth, funding filter, exchange lot/tick rounding.
"""
import numpy as np
import pandas as pd

import accounting
import config
from brain import kelly_risk_pct
from indicators import compute_frame, snapshot, direction
from strategies import select_signal
from trade_management import next_stop, breakeven_stop
from volume_anomaly import volume_anomaly_series

INTRABAR_POLICY = "stop-first when a bar touches both stop and target (conservative)"
LIMITATIONS = [
    "ML filter, news sentiment, order-book walls, fear&greed, breadth and the funding filter have no "
    "historical data here and are NOT applied, so results can be optimistic versus the live bot.",
    "Exchange lot-size / tick-size rounding is not simulated.",
    "Intrabar order is unknown: when stop and target are both inside one candle the stop is assumed first.",
    "Single historical path: past results do not guarantee future performance.",
]


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



def _directions(ind):
    bull = ((ind.ema9 > ind.ema21) & (ind.ema21 > ind.ema50) & (ind.plus_di >= ind.minus_di)).values
    bear = ((ind.ema9 < ind.ema21) & (ind.ema21 < ind.ema50) & (ind.minus_di > ind.plus_di)).values
    return np.where(bull, "BULLISH", np.where(bear, "BEARISH", "NEUTRAL"))


def _prepare(frames, warmup):
    """Compute indicators per symbol and align every symbol on the common timestamps."""
    inds = {}
    for sym, df in frames.items():
        df = df.copy()
        if "timestamp" not in df.columns:
            df["timestamp"] = np.arange(len(df)) * 3600000
        inds[sym] = compute_frame(df)
    common = None
    for ind in inds.values():
        s = set(ind["timestamp"].astype("int64"))
        common = s if common is None else common & s
    common = sorted(common)
    if len(common) < warmup + 50:
        raise ValueError(f"Not enough history: {len(common)} aligned candles")
    for sym in inds:
        ind = inds[sym]
        inds[sym] = ind[ind["timestamp"].isin(common)].reset_index(drop=True)
    return inds


def run_portfolio_backtest(frames, strategies=None, source="futures", initial_balance=None, warmup=120,
                           fee=None, slippage_bps=None, trailing=None, risk_pct=None, alloc_pct=None,
                           funding=None, leverage=None):
    """frames: {symbol: OHLCV DataFrame}. funding: optional {symbol: [{fundingTime, fundingRate}, ...]}."""
    initial = float(initial_balance or config.INITIAL_BALANCE)
    fee_r = accounting.fee_rate(source, fee)
    slip_bps = config.SLIPPAGE_BPS if slippage_bps is None else slippage_bps
    trailing = config.TRAILING_ENABLED if trailing is None else trailing
    alloc_pct = config.MAX_ALLOCATION_PCT if alloc_pct is None else alloc_pct
    lev = (config.FUTURES_LEVERAGE if leverage is None else leverage) if source == "futures" else 1.0

    inds = _prepare(frames, warmup)
    symbols = list(inds)
    first = inds[symbols[0]]
    n = len(first)
    ts = first["timestamp"].values.astype("int64")
    base_ms = int(np.median(np.diff(ts)))
    A = {}
    for s, ind in inds.items():
        A[s] = {"op": ind["open"].values, "hi": ind["high"].values, "lo": ind["low"].values, "cl": ind["close"].values,
                "atr": ind["atr"].values, "htf": _htf_directions(ind, ts, base_ms),
                "va": volume_anomaly_series(ind), "ind": ind}
    compass = None
    if config.USE_BTC_COMPASS and all(d in inds for d in config.DIRECTION_SYMBOLS):
        dd = [_directions(inds[d]) for d in config.DIRECTION_SYMBOLS]
        compass = np.where(np.all([x == "BULLISH" for x in dd], axis=0), "BULLISH",
                           np.where(np.all([x == "BEARISH" for x in dd], axis=0), "BEARISH", "NEUTRAL"))
    fund = {}
    if funding and source == "futures" and config.FUNDING_ENABLED:
        for s, evs in funding.items():
            fund[s] = sorted((int(e["fundingTime"]), float(e["fundingRate"])) for e in evs)

    cash = initial
    positions, trades, curve = [], [], []
    pending = []
    bars_in_trade = 0
    max_risk_pct, max_conc = 0.0, 0
    loss_streak, blocked_until = 0, -1
    strat_losses, strat_block = {}, {}
    peak, dd_until = initial, -1
    pair_lock, cooldown = {}, {}
    day_key, day_base = None, initial
    pause_bars = max(1, int(config.LOSS_STREAK_PAUSE_SECONDS * 1000 // base_ms))
    dd_bars = max(1, int(config.DRAWDOWN_PAUSE_SECONDS * 1000 // base_ms))
    strat_bars = max(1, int(config.STRATEGY_PAUSE_SECONDS * 1000 // base_ms))
    lock_bars = max(0, int(config.PAIR_LOCK_AFTER_STOPLOSS_MIN * 60000 // base_ms))
    cool_bars = max(0, int(config.SIGNAL_COOLDOWN_SECONDS * 1000 // base_ms))

    def equity_at(idx, price_of):
        margin = sum(p["margin_used"] for p in positions)
        unreal = sum(accounting.gross_pnl(p["side"], p["entry_price"], price_of(p), p["quantity"]) for p in positions)
        return cash + margin + unreal

    def finish(p, i, raw_exit, reason, raw=False):
        nonlocal cash, loss_streak, blocked_until
        exit_price = raw_exit if raw else accounting.exit_fill(raw_exit, p["side"], slip_bps)
        gross = accounting.gross_pnl(p["side"], p["entry_price"], exit_price, p["quantity"])
        exit_fee = exit_price * p["quantity"] * fee_r
        cash += p["margin_used"] + gross - exit_fee
        gross_total = gross + p["partial_gross"]
        fees_total = p["partial_fees"] + p["opening_fee"] + exit_fee
        net = gross_total - fees_total - p["funding"]
        trades.append({"symbol": p["symbol"], "entry_idx": p["entry_idx"], "exit_idx": i, "side": p["side"],
                       "strategy": p["strategy"], "regime": p["regime"], "entry": p["entry_price"], "exit": exit_price,
                       "qty": p["initial_quantity"], "gross": gross_total, "fees": fees_total, "funding": p["funding"],
                       "net": net, "r": net / p["initial_risk"] if p["initial_risk"] > 0 else 0.0,
                       "ret": net / p["equity_at_entry"], "reason": reason, "bars": i - p["entry_idx"]})
        positions.remove(p)
        if net < 0:
            loss_streak += 1
            if loss_streak >= config.MAX_CONSECUTIVE_LOSSES:
                blocked_until, loss_streak = i + pause_bars, 0
            strat_losses[p["strategy"]] = strat_losses.get(p["strategy"], 0) + 1
            if strat_losses[p["strategy"]] >= config.MAX_CONSECUTIVE_LOSSES:
                strat_block[p["strategy"]] = i + strat_bars
                strat_losses[p["strategy"]] = 0
        else:
            loss_streak = 0
            strat_losses[p["strategy"]] = 0
        if reason == "STOP_LOSS" and lock_bars:
            pair_lock[p["symbol"]] = i + lock_bars

    def partial(p, level):
        nonlocal cash
        qty = p["quantity"] * config.SCALE_OUT_PCT
        if qty <= 0 or qty >= p["quantity"]:
            return
        exit_price = accounting.exit_fill(level, p["side"], slip_bps)
        frac = qty / p["quantity"]
        gross = accounting.gross_pnl(p["side"], p["entry_price"], exit_price, qty)
        fee_leg = exit_price * qty * fee_r
        open_part, margin_part = p["opening_fee"] * frac, p["margin_used"] * frac
        cash += margin_part + gross - fee_leg
        p["partial_gross"] += gross
        p["partial_fees"] += fee_leg + open_part
        p["quantity"] -= qty
        p["opening_fee"] -= open_part
        p["margin_used"] -= margin_part
        p["scale_out_done"] = True
        p["pending_stop"] = breakeven_stop(p["side"], p["entry_price"], fee_r, slip_bps)

    for i in range(warmup, n):
        # --- 1. enter pending signals at this bar's OPEN ------------------------------------------
        if pending:
            eq = equity_at(i, lambda p: A[p["symbol"]]["cl"][i - 1])
            risk_budget_pct = (kelly_risk_pct([t["net"] for t in reversed(trades)]) if risk_pct is None else risk_pct)
            for sig in sorted(pending, key=lambda s: -s["score"]):
                s = sig["symbol"]
                if any(p["symbol"] == s for p in positions):
                    continue
                if i < blocked_until or i < dd_until or i < pair_lock.get(s, -1) or i < strat_block.get(sig["strategy"], -1):
                    continue
                side = sig["side"]
                entry = accounting.entry_fill(A[s]["op"][i], side, slip_bps)
                stop_dist = sig["atr"] * sig["stop_mult"]
                sign = accounting.side_sign(side)
                stop, target = entry - sign * stop_dist, entry + sign * stop_dist * sig["rr"]
                if stop <= 0 or stop_dist * sig["rr"] / entry * 100 < config.MIN_TARGET_PCT:
                    continue
                cap_left = max(0.0, accounting.portfolio_risk_cap(eq) - accounting.total_open_risk(positions, fee_r, slip_bps))
                sized, why = accounting.size_position(
                    equity=eq, cash=cash, entry=entry, stop=stop, side=side, source=source,
                    risk_budget=min(eq * risk_budget_pct / 100, cap_left), leverage=lev, alloc_pct=alloc_pct,
                    fee=fee_r, slippage_bps=slip_bps)
                if not sized:
                    continue
                liq = sized["liquidation_price"]
                if liq is not None and sign * (stop - liq) <= 0:
                    continue
                cand = {"symbol": s, "source": source, "side": side, "margin_used": sized["margin_used"],
                        "opening_fee": sized["opening_fee"], "risk_amount": sized["risk_amount"]}
                ok, why = accounting.check_portfolio_limits(
                    equity=eq, cash=cash, positions=positions, cand=cand, daily_change=eq - day_base,
                    daily_limit=day_base * config.DAILY_LOSS_LIMIT_PCT / 100.0)
                if not ok:
                    continue
                cash -= sized["margin_used"] + sized["opening_fee"]
                positions.append({
                    "symbol": s, "source": source, "side": side, "quantity": sized["quantity"],
                    "initial_quantity": sized["quantity"], "entry_price": entry, "stop_price": stop, "initial_stop": stop,
                    "target_price": target, "margin_used": sized["margin_used"], "opening_fee": sized["opening_fee"],
                    "initial_risk": sized["initial_risk"], "liq": liq, "entry_idx": i, "strategy": sig["strategy"],
                    "regime": sig["regime"], "equity_at_entry": eq, "partial_gross": 0.0, "partial_fees": 0.0,
                    "funding": 0.0, "scale_out_done": False, "pending_stop": None})
                cooldown[(s)] = i + cool_bars
                eq = equity_at(i, lambda p: A[p["symbol"]]["cl"][i - 1])
            pending = []
            if positions and eq > 0:
                max_risk_pct = max(max_risk_pct, accounting.total_open_risk(positions, fee_r, slip_bps) / eq * 100)
                max_conc = max(max_conc, len(positions))

        # --- 2. manage open positions on this bar -------------------------------------------------
        for p in list(positions):
            a = A[p["symbol"]]
            op, hi, lo, cl = a["op"][i], a["hi"][i], a["lo"][i], a["cl"][i]
            long_ = p["side"] == "LONG"
            sign = 1 if long_ else -1
            bars_in_trade += 1
            moved = abs(p["stop_price"] - p["initial_stop"]) > 1e-12
            stop_reason = "TRAILING_STOP" if moved else "STOP_LOSS"
            # (a) stop first (conservative); gap -> fills at the open
            stop_touched = (op <= p["stop_price"]) if long_ else (op >= p["stop_price"])
            level = None
            if stop_touched:
                level = op
            elif (lo <= p["stop_price"]) if long_ else (hi >= p["stop_price"]):
                level = p["stop_price"]
            if level is not None:
                if p["liq"] is not None:     # a liquidation can never lose more than the posted margin
                    level = max(level, p["liq"]) if long_ else min(level, p["liq"])
                finish(p, i, level, stop_reason)
                continue
            if p["liq"] is not None and ((long_ and lo <= p["liq"]) or (not long_ and hi >= p["liq"])):
                finish(p, i, p["liq"], "LIQUIDATION", raw=True)
                continue
            # (b) scale-out at +SCALE_OUT_R (stop was not hit in this bar)
            if config.SCALE_OUT_ENABLED and not p["scale_out_done"]:
                unit = abs(p["entry_price"] - p["initial_stop"])
                lvl = p["entry_price"] + sign * unit * config.SCALE_OUT_R
                if unit > 0 and ((hi >= lvl) if long_ else (lo <= lvl)):
                    partial(p, lvl)
            # (c) target for what is left
            if (op >= p["target_price"]) if long_ else (op <= p["target_price"]):
                finish(p, i, op, "TAKE_PROFIT")
                continue
            if (hi >= p["target_price"]) if long_ else (lo <= p["target_price"]):
                finish(p, i, p["target_price"], "TAKE_PROFIT")
                continue
            # (d) funding settled during this bar
            for t_ms, rate in fund.get(p["symbol"], ()):
                if ts[i] < t_ms <= ts[i] + base_ms:
                    amt = accounting.funding_payment(p["side"], p["quantity"] * cl, rate)
                    cash -= amt
                    p["funding"] += amt
            # (e) stop changes apply from the next bar
            if p["pending_stop"] is not None:
                p["stop_price"] = max(p["stop_price"], p["pending_stop"]) if long_ else min(p["stop_price"], p["pending_stop"])
                p["pending_stop"] = None
            p["stop_price"] = next_stop(p["side"], p["entry_price"], p["initial_stop"], p["stop_price"], cl, trailing, fee_r)
            if i == n - 1:
                finish(p, i, cl, "END_OF_DATA")
        if i == n - 1:
            for p in list(positions):
                finish(p, i, A[p["symbol"]]["cl"][i], "END_OF_DATA")

        # --- 3. mark to market, protections --------------------------------------------------------
        mtm = equity_at(i, lambda p: A[p["symbol"]]["cl"][i])
        curve.append(mtm)
        if positions and mtm > 0:
            max_risk_pct = max(max_risk_pct, accounting.total_open_risk(positions, fee_r, slip_bps) / mtm * 100)
            max_conc = max(max_conc, len(positions))
        k = int(ts[i] // 86400000)
        if k != day_key:
            day_key, day_base = k, mtm
        peak = max(peak, mtm)
        if dd_until < 0 and (peak - mtm) / peak * 100 >= config.MAX_DRAWDOWN_PCT:
            dd_until = i + dd_bars
        if dd_until >= 0 and i >= dd_until:
            peak, dd_until = mtm, -1

        # --- 4. signals on this bar's CLOSE -> executed at the next open --------------------------
        if i < n - 1 and i >= blocked_until and dd_until < 0:
            for s in symbols:
                a = A[s]
                if any(p["symbol"] == s for p in positions) or i < cooldown.get(s, -1) or i < pair_lock.get(s, -1):
                    continue
                if not np.isfinite(a["atr"][i]) or a["atr"][i] <= 0:
                    continue
                snap = snapshot(a["ind"], i)
                ctx = {"source": source, "symbol": s, "primary": snap, "dirs": [direction(snap), a["htf"][i]],
                       "news_risk": 0.0, "hour_utc": int((ts[i] // 3600000) % 24), "vol_anomaly": a["va"][i],
                       "compass": (compass[i] if compass is not None else None)}
                sig = select_signal(ctx, strategies)
                if sig["action"] != "HOLD":
                    pending.append({"symbol": s, "side": sig["side"], "strategy": sig["strategy"], "regime": sig["regime"],
                                    "stop_mult": sig["stop_mult"], "rr": sig["rr"], "atr": snap["atr"], "score": sig["score"]})

    report = build_report(trades, np.array(curve), initial, first, warmup, base_ms, bars_in_trade, strategies)
    report["symbols"] = symbols
    report["source"] = source
    report["assumptions"] = {"intrabar": INTRABAR_POLICY, "fee_rate": fee_r, "slippage_bps": slip_bps,
                             "leverage": lev, "funding_included": bool(fund),
                             "max_portfolio_risk_pct": min(config.MAX_PORTFOLIO_RISK_PCT, accounting.HARD_MAX_PORTFOLIO_RISK_PCT),
                             "max_open_positions": config.MAX_OPEN_POSITIONS}
    report["limitations"] = LIMITATIONS + ([] if fund else ["Futures funding fees are NOT included (no funding history supplied)."]
                                           if source == "futures" else [])
    report["cash_final"] = cash
    report["max_open_risk_pct"] = max_risk_pct
    report["max_concurrent"] = max_conc
    report["intrabar_policy"] = INTRABAR_POLICY
    report["funding_included"] = bool(fund)
    return report


def run_backtest(df, strategies=None, source="futures", initial_balance=None, warmup=120,
                 fee=None, slippage_bps=None, trailing=None, risk_pct=None, alloc_pct=None,
                 symbol="BACKTEST", funding=None, leverage=None):
    """Single-symbol backtest (same engine as the portfolio one)."""
    return run_portfolio_backtest({symbol: df}, strategies, source, initial_balance, warmup, fee, slippage_bps,
                                  trailing, risk_pct, alloc_pct, {symbol: funding} if funding else None, leverage)


def run_walk_forward(df, strategies=None, source="futures", folds=4, warmup=120, **kw):
    """Out-of-sample evaluation: the history after the first block is split into `folds` consecutive
    test windows; each window is backtested on its own (indicators warmed up on the preceding bars,
    no parameter is fitted on any of them). Returns per-fold results and the pooled trade statistics."""
    n = len(df)
    first_test = int(n * 0.4)
    size = (n - first_test) // folds
    if size < 100 or first_test < warmup + 50:
        raise ValueError("Not enough history for walk-forward analysis")
    out = []
    for k in range(folds):
        a = first_test + k * size
        b = n if k == folds - 1 else a + size
        part = df.iloc[a - warmup:b].reset_index(drop=True)
        r = run_backtest(part, strategies, source, warmup=warmup, **kw)
        out.append({"fold": k + 1, "trades": r["trades"], "return_pct": r["return_pct"],
                    "profit_factor": r["profit_factor"], "max_drawdown_pct": r["max_drawdown_pct"],
                    "expectancy_r": r["expectancy_r"]})
    profitable = sum(1 for f in out if f["trades"] > 0 and f["return_pct"] > 0)
    return {"folds": out, "profitable_folds": profitable, "total_trades": sum(f["trades"] for f in out)}


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
        "total_fees": float(sum(t.get("fees", 0.0) for t in trades)),
        "total_funding": float(sum(t.get("funding", 0.0) for t in trades)),
        "gross_pnl": float(sum(t.get("gross", 0.0) for t in trades)),
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
    if r.get("assumptions"):
        a = r["assumptions"]
        lines.append(f"Costs: fee {a['fee_rate']*100:.3f}%/side, slippage {a['slippage_bps']} bps, fees paid {r.get('total_fees', 0):.2f}"
                     f", funding {'included' if a['funding_included'] else 'NOT included'}")
        lines.append(f"Risk rules: aggregate cap {a['max_portfolio_risk_pct']:.0f}% of equity, max {a['max_open_positions']} positions; {a['intrabar']}")
    for note in r.get("limitations", []):
        lines.append("! " + note)
    lines.append("Past results do not guarantee future performance.")
    return "\n".join(lines)
