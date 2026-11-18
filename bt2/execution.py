"""Fill model. With the defaults (impact off, no participation cap) it reproduces the Legacy flat-slippage fills
EXACTLY (it calls the same accounting.entry_fill / exit_fill)."""
import math
from dataclasses import dataclass

import accounting
import config


@dataclass(frozen=True)
class ExecCfg:
    slippage_bps: float = None          # None -> Legacy config.SLIPPAGE_BPS
    fee: float = None                   # None -> Legacy fee schedule for the market
    impact_coeff: float = 0.0           # square-root-law coefficient; 0 = off. ASSUMPTION when > 0, not calibrated.
    max_participation: float = None     # max fraction of a bar's volume one order may take; None = unlimited


def base_slippage_bps(cfg):
    return config.SLIPPAGE_BPS if cfg.slippage_bps is None else cfg.slippage_bps


def impact_bps(qty, bar_volume, vol_pct, coeff):
    """Square-root impact: coeff * bar volatility (bps) * sqrt(participation). Participation capped at 100%."""
    if coeff <= 0 or qty <= 0:
        return 0.0
    part = 1.0 if not (bar_volume and bar_volume > 0) else min(qty / bar_volume, 1.0)
    return coeff * max(vol_pct, 0.0) * 10_000.0 * math.sqrt(part)


def total_slippage_bps(qty, bar_volume, vol_pct, cfg):
    return base_slippage_bps(cfg) + impact_bps(qty, bar_volume, vol_pct, cfg.impact_coeff)


def fill_price(raw, side, qty, bar_volume, vol_pct, cfg, entry=True):
    """Worse-than-raw fill for the trader (entry or exit). Returns (price, slippage_bps_used)."""
    bps = total_slippage_bps(qty, bar_volume, vol_pct, cfg)
    fn = accounting.entry_fill if entry else accounting.exit_fill
    return fn(raw, side, bps), bps


def fillable_qty(qty, bar_volume, cfg):
    """Partial-fill rule: an order cannot take more than max_participation of the bar's volume (remainder is cancelled)."""
    if cfg.max_participation is None:
        return qty
    if not (bar_volume and bar_volume > 0):
        return 0.0
    return min(qty, cfg.max_participation * bar_volume)
