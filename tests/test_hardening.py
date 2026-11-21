"""Regression tests for the v7.2.0 security / robustness review (all runnable without fastapi)."""
import ast
import os
import re
import subprocess
import sys
import unittest

import _env  # noqa: F401
import config
import security
from login_page import LOGIN_HTML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


def config_error(**env):
    """Import config in a clean interpreter with `env` set; return (accepted, message)."""
    code = "import sys; sys.path.insert(0, %r)\nimport config\nconfig.validate_config()\nprint('OK')" % ROOT
    full = dict(os.environ, **{k: str(v) for k, v in env.items()})
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=full, timeout=60)
    return done.stdout.strip() == "OK", (done.stderr.strip().splitlines() or [""])[-1]


class ConfigValidation(unittest.TestCase):
    def test_defaults_are_accepted(self):
        self.assertEqual(config_error()[0], True)

    def test_dangerous_values_are_rejected_with_the_variable_name(self):
        for name, value in (("SCAN_INTERVAL_SECONDS", 0), ("SCAN_INTERVAL_SECONDS", 5), ("POSITION_CHECK_SECONDS", 0),
                            ("INITIAL_BALANCE", -5), ("INITIAL_BALANCE", 0), ("DAILY_LOSS_LIMIT_PCT", 0),
                            ("DAILY_LOSS_LIMIT_PCT", -3), ("DAILY_LOSS_LIMIT_PCT", "nan"), ("ML_MIN_ACCURACY", 0.2),
                            ("PORT", 99999), ("MAX_SYMBOLS_TO_SCAN", 0), ("CORRELATION_MAX", 5)):
            ok, message = config_error(**{name: value})
            self.assertFalse(ok, "%s=%s should be rejected" % (name, value))
            self.assertIn(name, message)

    def test_typos_name_the_variable_instead_of_a_cryptic_conversion_error(self):
        ok, message = config_error(RISK_PER_TRADE_PCT="2,5")
        self.assertFalse(ok)
        self.assertIn("RISK_PER_TRADE_PCT", message)
        self.assertIn("got '2,5'", message)

    def test_reasonable_custom_values_still_pass(self):
        self.assertTrue(config_error(SCAN_INTERVAL_SECONDS=60, INITIAL_BALANCE=1000, DAILY_LOSS_LIMIT_PCT=5)[0])

    def test_legacy_dashboard_is_off_by_default_and_gated(self):
        self.assertIs(config.ENABLE_LEGACY_DASHBOARD, False)
        source = read("dashboard.py")
        body = source.split('async def dashboard():', 1)[1].split('return HTMLResponse("""', 1)[0]
        self.assertIn("ENABLE_LEGACY_DASHBOARD", body)
        self.assertIn("404", body)


class Authorization(unittest.TestCase):
    KEY = "correct-horse-battery"

    def setUp(self):
        security._fails.clear()

    def test_no_key_means_open(self):
        self.assertEqual(security.authorize("", "", "", "1.1.1.1"), "ok")

    def test_valid_session_cookie_is_never_locked_out(self):
        token = security.session_token(self.KEY)
        for _ in range(security.MAX_FAILS + 3):                    # someone behind the same proxy hop guesses wrongly
            security.authorize(self.KEY, "guess", "", "9.9.9.9")
        self.assertTrue(security.is_locked("9.9.9.9"))
        self.assertEqual(security.authorize(self.KEY, "", token, "9.9.9.9"), "ok")      # the owner still gets in
        self.assertEqual(security.authorize(self.KEY, self.KEY, "", "9.9.9.9"), "locked")  # key guessing stays locked

    def test_wrong_key_registers_failures_and_locks(self):
        verdicts = [security.authorize(self.KEY, "x%d" % i, "", "8.8.8.8") for i in range(security.MAX_FAILS + 1)]
        self.assertEqual(verdicts[:security.MAX_FAILS], ["denied"] * security.MAX_FAILS)
        self.assertEqual(verdicts[-1], "locked")

    def test_missing_credentials_do_not_count_as_guesses(self):
        for _ in range(20):
            self.assertEqual(security.authorize(self.KEY, "", "", "7.7.7.7"), "denied")
        self.assertFalse(security.is_locked("7.7.7.7"))

    def test_correct_key_and_forged_token(self):
        self.assertEqual(security.authorize(self.KEY, self.KEY, "", "6.6.6.6"), "ok")
        self.assertEqual(security.authorize(self.KEY, "", "0" * 64, "6.6.6.6"), "denied")


class RateLimiter(unittest.TestCase):
    def test_limit_window_and_independent_buckets(self):
        hits = [security.rate_limited("t:a", 3, 60, now=100.0 + i) for i in range(5)]
        self.assertEqual(hits, [False, False, False, True, True])
        self.assertFalse(security.rate_limited("t:b", 3, 60, now=105.0))             # other client unaffected
        self.assertFalse(security.rate_limited("t:a", 3, 60, now=100.0 + 61))        # window passed

    def test_endpoint_is_wired_to_the_limiter(self):
        source = read("dashboard.py")
        handler = source.split("async def market_klines", 1)[1].split("@router", 1)[0]
        self.assertIn("security.rate_limited", handler)
        self.assertIn("429", handler)


class Headers(unittest.TestCase):
    def test_private_json_is_never_cached_and_pages_are_origin_locked(self):
        self.assertEqual(security.extra_headers("/api/pro/overview", "application/json"), {"Cache-Control": "no-store"})
        page = security.extra_headers("/pro", "text/html; charset=utf-8")
        self.assertIn("default-src 'self'", page["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", page["Content-Security-Policy"])
        self.assertNotIn("Content-Security-Policy", security.extra_headers("/api/x", "application/json"))
        self.assertNotIn("Content-Security-Policy", security.extra_headers("/legacy", "text/html"))
        login = security.extra_headers("/login", "text/html")
        self.assertIn("Cache-Control", login)
        self.assertIn("Content-Security-Policy", login)

    def test_csp_does_not_break_the_pro_dashboard(self):
        csp = security.CSP
        for path in ("pro.html", "pro_core.js", "pro_overview.js", "pro_markets.js", "pro_signals.js", "pro_trades.js", "pro_more.js", "pro_tools.js"):
            text = read(path)
            self.assertNotRegex(text, r'\bon(click|input|change|load|error|submit)\s*=\s*"', path)      # inline handlers need unsafe-inline attrs
            self.assertNotRegex(text, r"https?://", path)                                              # nothing external to block
        self.assertIn("img-src 'self' data:", csp)          # the profile photo is a data: URL
        self.assertIn("connect-src 'self'", csp)

    def test_main_uses_the_hardened_flow(self):
        main = read("main.py")
        self.assertIn("security.authorize(", main)
        self.assertIn("security.extra_headers(", main)
        self.assertNotIn("security.is_locked(_client_ip(request))", main)
        ast.parse(main)


class LoginPage(unittest.TestCase):
    def test_no_third_party_resources_and_no_scripts(self):
        self.assertNotRegex(LOGIN_HTML, r"https?://")
        self.assertNotIn("<script", LOGIN_HTML.lower())
        self.assertNotRegex(LOGIN_HTML, r"<link[^>]+href=")
        self.assertNotIn("tailwind", LOGIN_HTML.lower())

    def test_form_still_works_with_existing_login_route(self):
        self.assertIn("INITIALIZE", LOGIN_HTML)
        self.assertIn('action="/api/login"', LOGIN_HTML)
        self.assertIn('method="POST"', LOGIN_HTML)
        self.assertIn('name="password"', LOGIN_HTML)
        self.assertIn('type="password"', LOGIN_HTML)


class Dependencies(unittest.TestCase):
    def test_minimum_versions_exclude_releases_with_known_advisories(self):
        floors = {"python-multipart": (0, 0, 18), "fastapi": (0, 115, 3), "aiohttp": (3, 10, 11), "nltk": (3, 9, 0)}
        found = {}
        for line in read("requirements.txt").splitlines():
            match = re.match(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?>=([0-9.]+)", line.strip())
            if match:
                found[match.group(1).lower()] = tuple(int(x) for x in (match.group(2).split(".") + ["0", "0"])[:3])
        for name, floor in floors.items():
            self.assertIn(name, found)
            self.assertGreaterEqual(found[name], floor, name)


if __name__ == "__main__":
    unittest.main()


class TickPlausibility(unittest.TestCase):
    """A corrupt WebSocket print must never reach stop-loss / take-profit evaluation on its own."""

    def setUp(self):
        import websocket_streamer as W
        self.W = W
        W.live_prices.clear()
        W._suspect.clear()

    def feed(self, price):
        import asyncio
        import json
        asyncio.run(self.W._handle_message(json.dumps([{"s": "BTCUSDT", "c": str(price)}]), None))
        item = self.W.live_prices.get("BTCUSDT")
        return item[0] if item else None

    def test_normal_moves_pass_and_absurd_prints_are_ignored(self):
        self.assertEqual(self.feed(60000), 60000)                 # first tick of a symbol is accepted
        self.assertEqual(self.feed(60600), 60600)                 # +1%
        self.assertEqual(self.feed(1e300), 60600)                 # absurd print ignored
        self.assertEqual(self.feed(60500), 60500)                 # market continues normally; suspicion cleared
        self.assertEqual(self.W._suspect, {})

    def test_a_real_crash_is_accepted_once_a_second_tick_confirms_it(self):
        self.feed(100.0)
        self.assertEqual(self.feed(20.0), 100.0)                  # -80% in one tick: not believed yet
        self.assertEqual(self.feed(20.4), 20.4)                   # confirmed by a similar tick

    def test_a_lone_spike_followed_by_the_old_price_is_discarded(self):
        self.feed(100.0)
        self.assertEqual(self.feed(900.0), 100.0)
        self.assertEqual(self.feed(100.5), 100.5)
        self.assertEqual(self.feed(900.0), 100.5)                 # the spike must be confirmed again from scratch

    def test_old_previous_price_does_not_block_a_legitimate_gap(self):
        import time
        self.W.live_prices["BTCUSDT"] = (100.0, time.monotonic() - 3600)
        self.assertEqual(self.feed(350.0), 350.0)                 # after a long outage the market may differ a lot
