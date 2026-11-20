"""Safe configuration: public market data + virtual paper simulation only."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _bool(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


APP_NAME = "AI QUANT X"
APP_VERSION = "7.2.0"
PAPER_MODE = True
TRADING_MODE = "PAPER SIMULATION"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
DB_PATH = os.getenv("DB_PATH", "/data/ai_quant_x.db")

BINANCE_SPOT_BASE_URL = "https://api.binance.com"
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
SPOT_EXCHANGE_INFO_PATH = "/api/v3/exchangeInfo"
FUTURES_EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"
SPOT_KLINES_PATH = "/api/v3/klines"
FUTURES_KLINES_PATH = "/fapi/v1/klines"
SPOT_TICKER_24H_PATH = "/api/v3/ticker/24hr"
FUTURES_TICKER_24H_PATH = "/fapi/v1/ticker/24hr"
SPOT_PRICE_PATH = "/api/v3/ticker/price"
FUTURES_PRICE_PATH = "/fapi/v1/ticker/price"

_DEFAULT_SYMBOLS = (
    "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,DOGEUSDT,DOTUSDT,LINKUSDT,"
    "POLUSDT,TONUSDT,SHIBUSDT,LTCUSDT,BCHUSDT,UNIUSDT,NEARUSDT,APTUSDT,ICPUSDT,SUIUSDT,"
    "ARBUSDT,OPUSDT,INJUSDT,ATOMUSDT,FILUSDT,STXUSDT,IMXUSDT,RENDERUSDT,FETUSDT,WLDUSDT,"
    "TRXUSDT,ETCUSDT,XLMUSDT,HBARUSDT,AAVEUSDT,ALGOUSDT,VETUSDT,CRVUSDT,LDOUSDT,SEIUSDT,"
    "TIAUSDT,RUNEUSDT,GALAUSDT,SANDUSDT,MANAUSDT,AXSUSDT,ENAUSDT,ONDOUSDT,PEPEUSDT,1000PEPEUSDT"
)
BASE_SYMBOLS = tuple(s.strip().upper() for s in os.getenv("SYMBOLS", _DEFAULT_SYMBOLS).split(",") if s.strip())
# SYMBOLS can be replaced at runtime by the symbol scanner; BASE_SYMBOLS never changes.
SYMBOLS = BASE_SYMBOLS
USE_SYMBOL_SCANNER = _bool("USE_SYMBOL_SCANNER", True)
SYMBOL_SCAN_REFRESH_SECONDS = int(os.getenv("SYMBOL_SCAN_REFRESH_SECONDS", "43200"))

MARKET_SOURCES = ("spot", "futures")
DIRECTION_SYMBOLS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("15m", "1h", "4h")
PRIMARY_TIMEFRAME = "1h"
KLINE_LIMIT = 200
MIN_CANDLES_REQUIRED = 60
MIN_24H_VOLUME_USDT = float(os.getenv("MIN_24H_VOLUME_USDT", "5000000"))
MAX_SYMBOLS_TO_SCAN = int(os.getenv("MAX_SYMBOLS_TO_SCAN", "50"))
EXCLUDED_SYMBOLS = set()
EXCLUDED_KEYWORDS = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "180"))
MAX_SCAN_DURATION_SECONDS = int(os.getenv("MAX_SCAN_DURATION_SECONDS", "150"))
MAX_CONCURRENT_REQUESTS = 3
MAX_OPEN_POSITIONS = 5
CORRELATION_MAX = float(os.getenv("CORRELATION_MAX", "0.85"))
PAIR_LOCK_AFTER_STOPLOSS_MIN = int(os.getenv("PAIR_LOCK_AFTER_STOPLOSS_MIN", "120"))
USE_BTC_COMPASS = _bool("USE_BTC_COMPASS", True)
USE_ROLLING_VWAP = _bool("USE_ROLLING_VWAP", True)
STRICT_HTF_CONFIRM = _bool("STRICT_HTF_CONFIRM", False)
MAX_SAME_SIDE = int(os.getenv("MAX_SAME_SIDE", "3"))

MIN_SIGNAL_SCORE = 50
SIGNAL_COOLDOWN_SECONDS = 3600
POSITION_CHECK_SECONDS = int(os.getenv("POSITION_CHECK_SECONDS", "15"))

# Entry is taken at the live price. If price moved more than this many ATR away
# from the closed candle the setup is considered stale and skipped.
ENTRY_MAX_DRIFT_ATR = float(os.getenv("ENTRY_MAX_DRIFT_ATR", "1.0"))

TAKER_LONG_MIN = 0.45
TAKER_SHORT_MAX = 0.55
FEAR_GREED_MAX_LONG = 80
FEAR_GREED_MIN_SHORT = 20
BREADTH_MIN_LONG = 30.0
BREADTH_MAX_SHORT = 70.0

CONFLICT_MIN_SCORE_GAP = int(os.getenv("CONFLICT_MIN_SCORE_GAP", "15"))
SOFT_FILTER_PENALTY = 10
MAX_SOFT_FILTER_FAILS = 2
HIGH_VOL_MIN_SCORE = 65
COUNTER_TREND_MIN_SCORE = 65

USE_VOLUME_ANOMALY_FILTER = True
USE_ORDER_BOOK_FILTER = True

# --- ML & Sentiment Filters ---
# The ML filter switches itself off (neutral) unless the trained model proves an
# out-of-sample edge. See ml_filter.py.
USE_ML_FILTER = _bool("USE_ML_FILTER", True)
ML_CONFIDENCE_THRESHOLD = 0.55
ML_NEUTRAL_THRESHOLD = 0.45
ML_HORIZON_CANDLES = int(os.getenv("ML_HORIZON_CANDLES", "4"))
ML_MIN_ACCURACY = float(os.getenv("ML_MIN_ACCURACY", "0.52"))
ML_RETRAIN_DAYS = int(os.getenv("ML_RETRAIN_DAYS", "7"))
ML_TRAIN_SYMBOLS = tuple(s.strip().upper() for s in os.getenv(
    "ML_TRAIN_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT").split(",") if s.strip())
ML_MODEL_PATH = os.getenv("ML_MODEL_PATH", os.path.join(os.path.dirname(DB_PATH) or ".", "model.pkl"))

USE_SENTIMENT_FILTER = True
SENTIMENT_BEARISH_BLOCK = -0.4
SENTIMENT_BULLISH_BLOCK = 0.4

STRATEGIES = tuple(s.strip() for s in os.getenv(
    "STRATEGIES", "trend,mean_reversion,breakout,dip_buyer").split(",") if s.strip())
HIGH_VOL_PERCENTILE = 95
TREND_ADX_MIN = 22
RANGE_ADX_MAX = 20

TRAILING_ENABLED = _bool("TRAILING_ENABLED", True)
BREAKEVEN_AT_R = 1.0
TRAIL_START_R = 2.0
TRAIL_DISTANCE_R = 0.8

MAX_CONSECUTIVE_LOSSES = 4
LOSS_STREAK_PAUSE_SECONDS = 6 * 3600
MAX_DRAWDOWN_PCT = 15.0
DRAWDOWN_PAUSE_SECONDS = 24 * 3600

# A strategy with MAX_CONSECUTIVE_LOSSES losses in a row is paused for this long, then retried.
STRATEGY_PAUSE_SECONDS = int(os.getenv("STRATEGY_PAUSE_SECONDS", str(6 * 3600)))
# Kelly sizing needs a meaningful sample before it replaces the fixed risk per trade.
BRAIN_MIN_TRADES = int(os.getenv("BRAIN_MIN_TRADES", "30"))

BACKTEST_CANDLES = int(os.getenv("BACKTEST_CANDLES", "2000"))
BACKTEST_INTERVAL = "1h"
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "")

# --- Auto-Tune (tuned on the first part of the history, validated on the unseen last part) ---
AUTOTUNE_MIN_TRADES = int(os.getenv("AUTOTUNE_MIN_TRADES", "8"))
AUTOTUNE_MIN_PROFIT_FACTOR = float(os.getenv("AUTOTUNE_MIN_PROFIT_FACTOR", "1.1"))
AUTOTUNE_MAX_DRAWDOWN_PCT = float(os.getenv("AUTOTUNE_MAX_DRAWDOWN_PCT", "25"))
AUTOTUNE_TEST_FRACTION = float(os.getenv("AUTOTUNE_TEST_FRACTION", "0.3"))
AUTOTUNE_TEST_MIN_TRADES = int(os.getenv("AUTOTUNE_TEST_MIN_TRADES", "10"))
AUTOTUNE_TEST_MIN_PROFIT_FACTOR = float(os.getenv("AUTOTUNE_TEST_MIN_PROFIT_FACTOR", "1.2"))

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "200"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "2.0"))
MAX_PORTFOLIO_RISK_PCT = float(os.getenv("MAX_PORTFOLIO_RISK_PCT", "10.0"))
MAX_ALLOCATION_PCT = float(os.getenv("MAX_ALLOCATION_PCT", "100.0"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))

MAX_DIRECTIONAL_HEAT_PCT = float(os.getenv("MAX_DIRECTIONAL_HEAT_PCT", "10.0"))
# Kept for backward compatibility only. The aggregate cap is MAX_PORTFOLIO_RISK_PCT (hard ceiling 10%);
# the old default of 20% silently allowed double the specified limit and is no longer honoured.
MAX_TOTAL_HEAT_PCT = min(float(os.getenv("MAX_TOTAL_HEAT_PCT", "10.0")), MAX_PORTFOLIO_RISK_PCT)

# --- Futures simulation (isolated margin). Leverage 1 = fully collateralised. ---
FUTURES_LEVERAGE = float(os.getenv("FUTURES_LEVERAGE", "1"))
MAINTENANCE_MARGIN_RATE = float(os.getenv("MAINTENANCE_MARGIN_RATE", "0.005"))
FUNDING_ENABLED = _bool("FUNDING_ENABLED", True)
REQUIRE_SYMBOL_RULES = _bool("REQUIRE_SYMBOL_RULES", True)   # refuse trades whose exchange rules are unknown

# --- Data safety ---
PRICE_MAX_AGE_SECONDS = float(os.getenv("PRICE_MAX_AGE_SECONDS", "30"))    # WebSocket price older than this is ignored
DATA_STALE_SECONDS = float(os.getenv("DATA_STALE_SECONDS", "300"))         # no fresh prices this long -> block new entries
SYMBOL_INFO_TTL_SECONDS = int(os.getenv("SYMBOL_INFO_TTL_SECONDS", "21600"))
KLINE_CACHE_SECONDS = float(os.getenv("KLINE_CACHE_SECONDS", "20"))


def _ws_url(url):
    """Binance retired the legacy USDⓈ-M futures WebSocket paths (wss://fstream.binance.com/ws, /stream) on
    2026-04-23: regular market streams now live under /market. A legacy URL, e.g. left in an old
    BINANCE_WS_URL variable, is rewritten so the price stream cannot silently stay dead."""
    return url.replace("://fstream.binance.com/ws/", "://fstream.binance.com/market/ws/", 1)


# !miniTicker@arr replaces the deprecated !ticker@arr; both carry the symbol ("s") and last price ("c") we read.
WS_URL = _ws_url(os.getenv("BINANCE_WS_URL", "wss://fstream.binance.com/market/ws/!miniTicker@arr"))

# --- Dashboard security ---
ALLOW_INSECURE_DASHBOARD = _bool("ALLOW_INSECURE_DASHBOARD", False)  # allow control POSTs without DASHBOARD_KEY
TRUSTED_PROXY = _bool("TRUSTED_PROXY", True)                          # behind Railway's proxy: use last X-Forwarded-For hop

FEE_RATE = 0.0004
FEE_RATE_SPOT = 0.001
MIN_NOTIONAL_USDT = 10.0


def fee_rate(source):
    return FEE_RATE if source == "futures" else FEE_RATE_SPOT


SLIPPAGE_BPS = 5.0
ATR_STOP_MULTIPLIER = 2.0
MIN_TARGET_PCT = 0.5
REWARD_RISK_RATIO = 2.0
MAX_NEWS_RISK = 0.70

EMA_FAST, EMA_MEDIUM, EMA_SLOW = 9, 21, 50
RSI_PERIOD, ATR_PERIOD, ADX_PERIOD, VOLUME_SMA_PERIOD = 14, 14, 14, 20

NEWS_ENABLED = _bool("NEWS_ENABLED", False)
NEWS_REFRESH_SECONDS = 300
NEWS_TIMEOUT_SECONDS = 10

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_ADMIN_ID", "")
HTTP_TIMEOUT_SECONDS = 12
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "AI-QUANT-X-Paper/7.2"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

USE_FUNDING_RATE_FILTER = _bool("USE_FUNDING_RATE_FILTER", True)
MAX_LONG_FUNDING_RATE = 0.0005
MIN_SHORT_FUNDING_RATE = -0.0005

USE_SESSION_FILTER = _bool("USE_SESSION_FILTER", False)
LONDON_OPEN = 7
NEW_YORK_OPEN = 12
SESSION_END = 21

SCALE_OUT_ENABLED = _bool("SCALE_OUT_ENABLED", True)
SCALE_OUT_R = 1.0
SCALE_OUT_PCT = 0.5


def validate_config():
    if not PAPER_MODE:
        raise RuntimeError("This build is paper-simulation only.")
    if not SYMBOLS:
        raise ValueError("SYMBOLS cannot be empty.")
    if not 0 < MAX_PORTFOLIO_RISK_PCT <= 10:
        raise ValueError("Aggregate portfolio risk must be in (0, 10] (specification hard limit).")
    if not 1 <= FUTURES_LEVERAGE <= 20:
        raise ValueError("FUTURES_LEVERAGE must be in [1, 20].")
    if not 0 <= MAINTENANCE_MARGIN_RATE < 0.5:
        raise ValueError("MAINTENANCE_MARGIN_RATE must be in [0, 0.5).")
    if MAX_SAME_SIDE < 1 or MAX_OPEN_POSITIONS < 1:
        raise ValueError("MAX_SAME_SIDE and MAX_OPEN_POSITIONS must be >= 1.")
    unknown = [x for x in STRATEGIES if x not in ("trend", "mean_reversion", "breakout", "dip_buyer")]
    if unknown:
        raise ValueError("Unknown strategies: %s" % ", ".join(unknown))
    if not 0 < RISK_PER_TRADE_PCT <= MAX_PORTFOLIO_RISK_PCT:
        raise ValueError("Invalid per-position risk.")
    if not 0 < MAX_ALLOCATION_PCT <= 100:
        raise ValueError("Invalid allocation cap.")
    if not 0 < MAX_DIRECTIONAL_HEAT_PCT <= MAX_TOTAL_HEAT_PCT:
        raise ValueError("Directional heat must be in (0, MAX_TOTAL_HEAT_PCT].")
    if not 0 < AUTOTUNE_TEST_FRACTION < 0.6:
        raise ValueError("AUTOTUNE_TEST_FRACTION must be in (0, 0.6).")
    return True
