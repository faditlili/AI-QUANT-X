"""Event-driven simulation on aligned OHLCV frames with Legacy accounting rules.

Inputs
  frames : {symbol: DataFrame[timestamp(ms), open, high, low, close, volume]} - identical timestamps, volume in base units
  events : [{"symbol", "t0", "side": "LONG"|"SHORT"|+1|-1, "sl_dist", "tp_dist", optional tags (strategy, regime, ...)}]
           decided at the CLOSE of bar t0; entered at the OPEN of bar t0+1 (barriers measured from that raw open)
  mark   : optional {symbol: DataFrame[high, low, close]} mark-price bars (default: last-price bars - an assumption)
Per bar: (1) entries at the open, (2) exits, (3) mark-to-market. Conservative rules:
  * stop/liquidation before target when both are reachable in one bar; liquidation vs stop ordered by price level;
  * a bar opening beyond the stop fills at the OPEN (loss can exceed 1R); all exits pay slippage (+impact);
  * a liquidated isolated position loses its WHOLE margin (plus the opening fee), no exit fee;
  * partial fills: an order is capped at max_participation * bar volume, the remainder is cancelled;
  * admission = Legacy accounting.check_portfolio_limits (10% aggregate cap, duplicates, same-side...) AND a second
    check using this engine's own costs (so impact/participation can never under-state risk).
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

import accounting
import config

from .execution import ExecCfg, base_slippage_bps, fill_price, fillable_qty, total_slippage_bps
from .funding import clean_events, funding_cost
from .margin import MarginTable, is_liquidated, liquidation_price


@dataclass
class SimCfg:
    initial: float = None                     # None -> config.INITIAL_BALANCE
    source: str = "futures"
    leverage: float = None                    # None -> config.FUTURES_LEVERAGE
    risk_pct: float = None                    # None -> config.RISK_PER_TRADE_PCT
    max_hold: int = 24                        # bars, including the entry bar
    execution: ExecCfg = field(default_factory=ExecCfg)
    margin_table: MarginTable = None          # None -> flat Legacy maintenance rate
    funding: dict = None                      # {symbol: [{"fundingTime", "fundingRate"}]}
    rules: dict = None                        # {"step", "min_qty", "min_notional"} exchange filters


def _side(v):
    if v in ("LONG", 1, "BUY"):
        return "LONG"
    if v in ("SHORT", -1, "SELL"):
        return "SHORT"
    raise ValueError("bad side %r" % (v,))


def _bar_vol_pct(h, l, c, window=14):
    """Causal per-bar volatility proxy known BEFORE bar i opens: mean (high-low)/close over the previous `window` bars."""
    rng = (h - l) / np.where(c > 0, c, np.nan)
    out = np.full(len(c), np.nan)
    for i in range(1, len(c)):
        seg = rng[max(0, i - window):i]
        seg = seg[np.isfinite(seg)]
        out[i] = seg.mean() if len(seg) else np.nan
    return np.nan_to_num(out, nan=0.0)


def simulate(frames, events, cfg=None, mark=None):
    cfg = cfg or SimCfg()
    initial = float(config.INITIAL_BALANCE if cfg.initial is None else cfg.initial)
    source = cfg.source
    lev = max(1.0, float(config.FUTURES_LEVERAGE if cfg.leverage is None else cfg.leverage)) if source == "futures" else 1.0
    risk_pct = config.RISK_PER_TRADE_PCT if cfg.risk_pct is None else cfg.risk_pct
    fee = accounting.fee_rate(source, cfg.execution.fee)
    table = cfg.margin_table or MarginTable.flat()
    syms = list(frames)
    n = len(frames[syms[0]])
    ts = frames[syms[0]]["timestamp"].to_numpy("int64")
    for s in syms:
        if len(frames[s]) != n or not np.array_equal(frames[s]["timestamp"].to_numpy("int64"), ts):
            raise ValueError("frames must share identical timestamps (symbol %s differs)" % s)
    if n < 3 or np.any(np.diff(ts) <= 0):
        raise ValueError("need >= 3 strictly increasing bars")
    bar_ms = int(np.median(np.diff(ts)))
    A = {s: {k: frames[s][k].to_numpy(float) for k in ("open", "high", "low", "close", "volume")} for s in syms}
    for s in syms:
        a = A[s]
        if not (np.all(np.isfinite([a["open"], a["high"], a["low"], a["close"]])) and np.all(a["open"] > 0)):
            raise ValueError("%s: non-finite or non-positive prices" % s)
        a["vp"] = _bar_vol_pct(a["high"], a["low"], a["close"])
        m = (mark or {}).get(s)
        a["mh"], a["ml"] = (m["high"].to_numpy(float), m["low"].to_numpy(float)) if m is not None else (a["high"], a["low"])
    fund = {s: clean_events((cfg.funding or {}).get(s)) for s in syms}

    by_entry = defaultdict(list)
    for k, e in enumerate(events):
        if e["symbol"] not in A:
            raise ValueError("event for unknown symbol %r" % e["symbol"])
        if not (e["sl_dist"] > 0 and e["tp_dist"] > 0):
            raise ValueError("sl_dist and tp_dist must be positive")
        if 0 <= e["t0"] + 1 < n:
            by_entry[e["t0"] + 1].append((k, e))

    cash, positions, trades, rejected, curve = initial, [], [], [], []
    max_risk_pct = 0.0

    def equity_at(i, field_name):
        return cash + sum(p["margin"] + accounting.side_sign(p["side"]) * (A[p["symbol"]][field_name][i] - p["entry_fill"]) * p["quantity"]
                          for p in positions)

    def close_position(p, i, raw_exit, reason, liquidated=False):
        nonlocal cash
        a, side = A[p["symbol"]], p["side"]
        if liquidated:
            exit_px, exit_bps, exit_fee, gross, fund_cost = raw_exit, 0.0, 0.0, -p["margin"], 0.0
            net = -p["margin"] - p["opening_fee"]
            cash += 0.0
        else:
            exit_px, exit_bps = fill_price(raw_exit, side, p["quantity"], a["volume"][i], a["vp"][i], cfg.execution, entry=False)
            gross = accounting.gross_pnl(side, p["entry_fill"], exit_px, p["quantity"])
            exit_fee = p["quantity"] * exit_px * fee
            price_at = lambda t, a=a: a["open"][max(0, min(n - 1, int(np.searchsorted(ts, t, side="right")) - 1))]
            fund_cost = funding_cost(side, p["quantity"], fund[p["symbol"]], ts[p["entry_bar"]], ts[i] + bar_ms, price_at)
            net = gross - p["opening_fee"] - exit_fee - fund_cost
            cash += p["margin"] + gross - exit_fee - fund_cost
        positions.remove(p)
        trades.append({"symbol": p["symbol"], "side": side, "entry_bar": p["entry_bar"], "exit_bar": i, "reason": reason,
                       "quantity": p["quantity"], "requested_quantity": p["requested_quantity"], "partial_fill": p["partial_fill"],
                       "raw_entry": p["raw_entry"], "entry_fill": p["entry_fill"], "exit_fill": exit_px,
                       "gross_pnl": gross, "fees": p["opening_fee"] + exit_fee, "funding": fund_cost,
                       "entry_participation": p["quantity"] / A[p["symbol"]]["volume"][p["entry_bar"]] if A[p["symbol"]]["volume"][p["entry_bar"]] > 0 else float("nan"),
                       "entry_slippage_bps": p["entry_bps"], "exit_slippage_bps": exit_bps,
                       "net_pnl": net, "initial_risk": p["initial_risk"], "R": net / p["initial_risk"], "margin": p["margin"],
                       "liquidated": liquidated, **p["tags"]})

    for i in range(n):
        # (1) entries at this bar's open
        for _, e in by_entry.get(i, ()):
            sym, side = e["symbol"], _side(e["side"])
            a, s = A[sym], accounting.side_sign(_side(e["side"]))
            raw, vol, vp = a["open"][i], a["volume"][i], a["vp"][i]
            stop, target = raw - s * e["sl_dist"], raw + s * e["tp_dist"]
            tags = {k: v for k, v in e.items() if k not in ("symbol", "t0", "side", "sl_dist", "tp_dist")}

            def reject(why, sym=sym, side=side):
                rejected.append({"bar": i, "symbol": sym, "side": side, "reason": why})

            equity = equity_at(i, "open")
            cap = accounting.portfolio_risk_cap(equity)
            own_open = sum(p["risk_amount"] for p in positions)
            budget = min(equity * risk_pct / 100.0, cap - own_open)
            if budget <= 0:
                reject("No risk budget left"); continue
            guess = budget / e["sl_dist"]                                     # first-pass quantity for the impact estimate
            px0, bps0 = fill_price(raw, side, guess, vol, vp, cfg.execution, entry=True)
            sizing, why = accounting.size_position(equity=equity, cash=cash, entry=px0, stop=stop, side=side, source=source,
                                                   risk_budget=budget, leverage=lev, fee=fee, slippage_bps=bps0, rules=cfg.rules)
            if sizing is None:
                reject(why); continue
            qty_req = sizing["quantity"]
            qty = fillable_qty(qty_req, vol, cfg.execution)
            if cfg.rules:
                qty = accounting.floor_to_step(qty, cfg.rules.get("step"))
            min_notional = max(config.MIN_NOTIONAL_USDT, (cfg.rules or {}).get("min_notional") or 0)
            if qty <= 0 or qty * raw < min_notional:
                reject("Partial fill below minimum notional (bar volume too thin)"); continue
            fill, bps = fill_price(raw, side, qty, vol, vp, cfg.execution, entry=True)
            if s * (fill - stop) <= 0:
                reject("Entry slippage pushed the fill through the stop"); continue
            notional = qty * fill
            opening_fee, margin = notional * fee, notional / lev
            risk = accounting.stop_risk(side, fill, stop, qty, source, fee, bps, entry_fee=opening_fee)
            cand = {"symbol": sym, "source": source, "side": side, "margin_used": margin, "opening_fee": opening_fee, "risk_amount": risk}
            ok, why = accounting.check_portfolio_limits(equity=equity, cash=cash, positions=positions, cand=cand)
            if ok and own_open + risk > cap + accounting.EPS:
                ok, why = False, "Aggregate risk cap exceeded (engine cost model)"
            if not ok:
                reject(why); continue
            cash -= margin + opening_fee
            liq = liquidation_price(side, qty, fill, margin, table) if source == "futures" else None
            positions.append({"symbol": sym, "source": source, "side": side, "quantity": qty, "requested_quantity": qty_req,
                              "partial_fill": qty < qty_req * (1 - 1e-12), "entry_price": fill, "entry_fill": fill, "raw_entry": raw,
                              "stop_price": stop, "stop": stop, "target": target, "margin": margin, "opening_fee": opening_fee,
                              "risk_amount": risk, "initial_risk": qty * abs(fill - stop), "entry_bar": i, "entry_bps": bps,
                              "liq": liq, "tags": tags})
            max_risk_pct = max(max_risk_pct, sum(p["risk_amount"] for p in positions) / equity * 100.0)

        # (2) exits
        for p in list(positions):
            a, s = A[p["symbol"]], accounting.side_sign(p["side"])
            o, h, l, c = a["open"][i], a["high"][i], a["low"][i], a["close"][i]
            stop_hit = (l <= p["stop"]) if s == 1 else (h >= p["stop"])
            adverse_mark = a["ml"][i] if s == 1 else a["mh"][i]
            liq_hit = source == "futures" and is_liquidated(p["side"], p["quantity"], p["entry_fill"], p["margin"], adverse_mark, table)
            tp_hit = (h >= p["target"]) if s == 1 else (l <= p["target"])
            if stop_hit or liq_hit:
                liq_first = liq_hit and (not stop_hit or (p["liq"] is not None and s * (p["liq"] - p["stop"]) > 0))
                if liq_first:
                    close_position(p, i, p["liq"] if p["liq"] is not None else adverse_mark, "liquidation", liquidated=True)
                else:
                    gap = (o <= p["stop"]) if s == 1 else (o >= p["stop"])
                    close_position(p, i, o if gap and p["entry_bar"] < i else p["stop"], "stop")
            elif tp_hit:
                gap = (o >= p["target"]) if s == 1 else (o <= p["target"])
                close_position(p, i, o if gap and p["entry_bar"] < i else p["target"], "target")
            elif i >= p["entry_bar"] + cfg.max_hold - 1:
                close_position(p, i, c, "timeout")
            elif i == n - 1:
                close_position(p, i, c, "end")
        curve.append(equity_at(i, "close"))

    return {"trades": trades, "rejected": rejected, "curve": curve, "initial": initial, "final_equity": curve[-1],
            "max_open_risk_pct": max_risk_pct, "bar_ms": bar_ms,
            "settings": {"leverage": lev, "fee": fee, "slippage_bps": base_slippage_bps(cfg.execution),
                         "impact_coeff": cfg.execution.impact_coeff, "max_participation": cfg.execution.max_participation,
                         "risk_pct": risk_pct, "max_hold": cfg.max_hold}}
