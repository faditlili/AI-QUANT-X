"""Phase 4: realistic execution / margin / funding simulation + statistical validation (standalone, OFF by default).

Reuses the Legacy accounting functions (fees, slippage, sizing, portfolio limits incl. the 10% aggregate risk cap),
so the simulated rules are the SAME rules Paper Trading applies. Nothing in the Legacy Core imports this package;
backtest.py is untouched and remains the stable engine.
"""
