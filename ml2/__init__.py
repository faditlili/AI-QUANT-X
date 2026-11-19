"""Phase 3: meta-labeling research layer (standalone, OFF by default via edge.flags).

Nothing in the Legacy Core imports this package. The legacy ml_filter.py is untouched and remains the
active filter. A model from here may only be used if it passes ml2.gate (out-of-sample, vs accept-all baseline).
"""
