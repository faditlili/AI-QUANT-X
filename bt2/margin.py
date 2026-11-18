"""Isolated-margin maintenance tiers and liquidation, derived from first principles (no remembered exchange constants).

Maintenance margin for a position of notional N:   MM(N) = N * mmr(tier) - cum(tier)      (cum = "maintenance amount")
Isolated margin balance at mark price m:           MB = WB + side * qty * (m - entry)       (WB = isolated wallet balance)
Liquidation when MB <= MM(qty * m).  Solving for m (flat tier):
  long : m = (qty*entry - WB - cum) / (qty*(1 - mmr))        short: m = (WB + qty*entry + cum) / (qty*(1 + mmr))
REAL tier tables must be supplied by the user (Binance publishes them per symbol; they are NOT bundled here because
they could not be verified). The default is ONE flat tier = the Legacy MAINTENANCE_MARGIN_RATE.
"""
import math
from dataclasses import dataclass

import accounting
import config


@dataclass(frozen=True)
class Tier:
    cap: float      # tier applies to notionals <= cap (last tier: inf)
    mmr: float
    cum: float = 0.0


class MarginTable:
    def __init__(self, tiers):
        ts = sorted(tiers, key=lambda t: t.cap)
        if not ts:
            raise ValueError("at least one tier required")
        if not math.isinf(ts[-1].cap):
            raise ValueError("the last tier must have cap=inf")
        for t in ts:
            if not (0 <= t.mmr < 0.5) or t.cum < 0 or t.cap <= 0:
                raise ValueError("invalid tier %r" % (t,))
        for a, b in zip(ts, ts[1:]):                     # maintenance margin must be continuous across tier edges
            lo, hi = a.cap * a.mmr - a.cum, a.cap * b.mmr - b.cum
            if abs(lo - hi) > 1e-6 * max(1.0, abs(lo)):
                raise ValueError("tiers %r -> %r are not continuous at notional %s (%.6f vs %.6f)" % (a, b, a.cap, lo, hi))
        self.tiers = ts

    @classmethod
    def flat(cls, mmr=None):
        return cls([Tier(math.inf, config.MAINTENANCE_MARGIN_RATE if mmr is None else mmr, 0.0)])

    def tier(self, notional):
        for t in self.tiers:
            if notional <= t.cap:
                return t
        return self.tiers[-1]

    def maintenance(self, notional):
        t = self.tier(notional)
        return max(0.0, notional * t.mmr - t.cum)


def is_liquidated(side, qty, entry, wallet_balance, mark, table):
    s = accounting.side_sign(side)
    margin_balance = wallet_balance + s * qty * (mark - entry)
    return margin_balance <= table.maintenance(qty * mark)


def liquidation_price(side, qty, entry, wallet_balance, table, iterations=6):
    """Mark price at which the position is liquidated (tier re-selected at the liquidation notional)."""
    s = accounting.side_sign(side)
    m = entry
    for _ in range(iterations):
        t = table.tier(qty * m)
        if s == 1:
            nm = (qty * entry - wallet_balance - t.cum) / (qty * (1 - t.mmr))
        else:
            nm = (wallet_balance + qty * entry + t.cum) / (qty * (1 + t.mmr))
        if abs(nm - m) < 1e-12 * max(1.0, abs(m)):
            m = nm
            break
        m = nm
    return max(0.0, m)
