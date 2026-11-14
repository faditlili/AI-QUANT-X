"""Safe configuration: public market data + virtual paper simulation only."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_NAME = "AI QUANT X"
APP_VERSION = "5.0.0"
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

SYMBOLS = tuple(s.strip().upper() for s in os.getenv(
    "SYMBOLS", 
    "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,DOGEUSDT,DOTUSDT,LINKUSDT,"
    "POLUSDT,TONUSDT,SHIBUSDT,LTCUSDT,BCHUSDT,UNIUSDT,NEARUSDT,APTUSDT,ICPUSDT,SUIUSDT,"
    "ARBUSDT,OPUSDT,INJUSDT,ATOMUSDT,FILUSDT,STXUSDT,IMXUSDT,RENDERUSDT,FETUSDT,WLDUSDT,"
    "TRXUSDT,ETCUSDT,XLMUSDT,HBARUSDT,AAVEUSDT,ALGOUSDT,VETUSDT,CRVUSDT,LDOUSDT,SEIUSDT,"
    "TIAUSDT,RUNEUSDT,GALAUSDT,SANDUSDT,MANAUSDT,AXSUSDT,ENAUSDT,ONDOUSDT,PEPEUSDT,1000PEPEUSDT"
).split(",") if s.strip())

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
MAX_SCAN_DURATION_SECONDS = 150
MAX_CONCURRENT_REQUESTS = 3
MAX_OPEN_POSITIONS = 5
CORRELATION_MAX = 0.92   
PAIR_LOCK_AFTER_STOPLOSS_MIN = 120   
USE_BTC_COMPASS = True     
USE_ROLLING_VWAP = True    
STRICT_HTF_CONFIRM = False 
MAX_SAME_SIDE = 3        
MIN_SIGNAL_SCORE = 50
SIGNAL_COOLDOWN_SECONDS = 3600
POSITION_CHECK_SECONDS = int(os.getenv("POSITION_CHECK_SECONDS", "15"))

# Strategy layer
STRATEGIES = tuple(s.strip() for s in os.getenv(
    "STRATEGIES", "trend,mean_reversion,breakout,dip_buyer").split(",") if s.strip())
HIGH_VOL_PERCENTILE = 95
TREND_ADX_MIN = 22
RANGE_ADX_MAX = 20

# Trade management
TRAILING_ENABLED = os.getenv("TRAILING_ENABLED", "true").lower() == "true"
BREAKEVEN_AT_R = 1.0
TRAIL_START_R = 1.5
TRAIL_DISTANCE_R = 1.0

# Portfolio protection
MAX_CONSECUTIVE_LOSSES = 4
LOSS_STREAK_PAUSE_SECONDS = 6 * 3600
MAX_DRAWDOWN_PCT = 15.0
DRAWDOWN_PAUSE_SECONDS = 24 * 3600

# Backtest
BACKTEST_CANDLES = int(os.getenv("BACKTEST_CANDLES", "2000"))
BACKTEST_INTERVAL = "1h"

# Dashboard protection (empty = open)
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY", "")

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "200"))
RISK_PER_TRADE_PCT = 2.0     
MAX_PORTFOLIO_RISK_PCT = 10.0
MAX_ALLOCATION_PCT = 100.0    
DAILY_LOSS_LIMIT_PCT = 3.0

# Fees & Notional
FEE_RATE = 0.0004            
FEE_RATE_SPOT = 0.001        
MIN_NOTIONAL_USDT = 10.0     # <--- أضفنا هذا السطر هنا

def fee_rate(source):
    return FEE_RATE if source == "futures" else FEE_RATE_SPOT

SLIPPAGE_BPS = 5.0
ATR_STOP_MULTIPLIER = 2.0
MIN_TARGET_PCT = 0.5         
REWARD_RISK_RATIO = 2.0
MAX_NEWS_RISK = 0.70

EMA_FAST, EMA_MEDIUM, EMA_SLOW = 9, 21, 50
RSI_PERIOD, ATR_PERIOD, ADX_PERIOD, VOLUME_SMA_PERIOD = 14, 14, 14, 20

NEWS_ENABLED = os.getenv("NEWS_ENABLED", "false").lower() == "true"
NEWS_REFRESH_SECONDS = 300
NEWS_TIMEOUT_SECONDS = 10

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "") or os.getenv("TELEGRAM_ADMIN_ID", "") 
HTTP_TIMEOUT_SECONDS = 12
HTTP_RETRY_ATTEMPTS = 2
USER_AGENT = "AI-QUANT-X-Paper/4.1"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Advanced Filters ---
USE_FUNDING_RATE_FILTER = True
MAX_LONG_FUNDING_RATE = 0.0005
MIN_SHORT_FUNDING_RATE = -0.0005

USE_SESSION_FILTER = False
LONDON_OPEN = 7
NEW_YORK_OPEN = 12
SESSION_END = 21

SCALE_OUT_ENABLED = True
SCALE_OUT_R = 1.0
SCALE_OUT_PCT = 0.5

def validate_config():
    if not PAPER_MODE:
        raise RuntimeError("This build is paper-simulation only.")
    if not SYMBOLS:
        raise ValueError("SYMBOLS cannot be empty.")
    if not 0 < MAX_PORTFOLIO_RISK_PCT <= 10:
        raise ValueError("Aggregate portfolio risk must be in (0, 10].")
    if not 0 < RISK_PER_TRADE_PCT <= MAX_PORTFOLIO_RISK_PCT:
        raise ValueError("Invalid per-position risk.")
    if not 0 < MAX_ALLOCATION_PCT <= 100:
        raise ValueError("Invalid allocation cap.")
    if DB_PATH == ":memory:":
        return True
    return True
