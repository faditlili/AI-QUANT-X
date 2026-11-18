"""Edge data layer (Phase 2). Standalone add-on: nothing in the Legacy Core imports this package.

Public market data only (no keys, no orders). Every value is either a real, validated number or the
call raises / returns None - never a made-up default. All stored series carry `available_at`, the
earliest moment the value could have been known, so research code can stay free of look-ahead bias.
"""
