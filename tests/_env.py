"""Test bootstrap (imported first by every test module).

* puts the project root on sys.path;
* points config at a temp DB and forces PAPER mode;
* if a third-party package that needs the network/build is NOT installed in this environment
  (aiohttp, websockets, telegram), installs a minimal in-memory stand-in so the pure logic that
  imports it can still be exercised. Where the real package IS installed it is always used.
  Tests never perform real network I/O.
"""
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "aiqx_test_default.db"))
os.environ.setdefault("TELEGRAM_TOKEN", "")
os.environ.setdefault("DASHBOARD_KEY", "")

STUBBED = []


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    STUBBED.append(name)
    return mod


def _missing(name):
    try:
        __import__(name)
        return False
    except ImportError:
        return True


if _missing("aiohttp"):
    class _ClientError(Exception):
        pass

    class _Dummy:
        def __init__(self, *a, **k):
            self.closed = False

        async def close(self):
            self.closed = True

    _stub("aiohttp", ClientError=_ClientError, ClientSession=_Dummy, ClientTimeout=_Dummy, TCPConnector=_Dummy)

if _missing("websockets"):
    _stub("websockets", connect=lambda *a, **k: None)

if _missing("telegram"):
    class _Btn:
        def __init__(self, text, callback_data=None):
            self.text, self.callback_data = text, callback_data

    class _Markup:
        def __init__(self, keyboard):
            self.inline_keyboard = keyboard

    class _Any:
        def __init__(self, *a, **k):
            pass

    tg = _stub("telegram", Update=_Any, InlineKeyboardButton=_Btn, InlineKeyboardMarkup=_Markup)
    _stub("telegram.ext", Application=_Any, CommandHandler=_Any, CallbackQueryHandler=_Any,
          ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object))
    tg.ext = sys.modules["telegram.ext"]

import config  # noqa: E402

config.PAPER_MODE = True
HAS_FASTAPI = not _missing("fastapi")
