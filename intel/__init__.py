"""Phase 5: Strategy Intelligence (standalone, ADVISORY, OFF by default via edge.flags STRATEGY_INTEL).

Turns closed-trade evidence (backtest, bt2 or paper trades) into an auditable per-(strategy, regime) verdict:
ENABLE / UNPROVEN / DISABLE, decided by statistical rules (bootstrap CI, multiple-testing control, deflated Sharpe,
time stability) - never by win rate. Nothing in the Legacy Core imports this package; it can only RESTRICT (risk
multiplier in [0, 1]); it can never raise risk, so the 10% aggregate cap is untouched.
"""
