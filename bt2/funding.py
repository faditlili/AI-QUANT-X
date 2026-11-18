"""Funding payments for a held position. Rule (documented, conservative on the exit side):
a payment at time F is charged when  entry_time < F < exit_bar_end  (the exit bar counts fully, because the intrabar
exit time is unknown). Notional = qty * price at F (open of the bar containing F). Sign: accounting.funding_payment
(positive = trader pays; long pays when rate > 0)."""
import math

import accounting


def clean_events(events):
    """events: iterable of {"fundingTime": ms, "fundingRate": x} (Binance shape) -> sorted [(ts, rate)]. Raises on garbage."""
    out = []
    for e in events or ():
        ts, rate = int(e["fundingTime"]), float(e["fundingRate"])
        if ts <= 0 or not math.isfinite(rate) or abs(rate) > 0.05:      # 5% per interval is far beyond any real rate
            raise ValueError("invalid funding event %r" % (e,))
        out.append((ts, rate))
    return sorted(out)


def funding_cost(side, qty, events, t_in, t_out, price_at):
    total = 0.0
    for ts, rate in events:
        if t_in < ts < t_out:
            total += accounting.funding_payment(side, qty * price_at(ts), rate)
    return total
