"""Smoke tests against the REAL FastAPI/Starlette stack (no engine, no network).

They are skipped automatically when fastapi/httpx are not installed (as in the offline audit sandbox),
so the legacy suite behaves exactly as before. Install `requirements-dev.txt` to run them:
    pytest -q tests/test_real_stack_smoke.py
The app lifespan is NOT entered (no `with TestClient`), so no engine/Telegram/Binance traffic happens.
"""
import importlib.util
import unittest

import _env  # noqa: F401
import config

def _real(name):
    """True only for a genuinely installed package (not one of tests/_env.py's offline stand-ins)."""
    if name in _env.STUBBED:
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except (ValueError, ImportError):
        return False


HAVE_STACK = all(_real(m) for m in ("fastapi", "httpx", "uvicorn", "multipart"))
HAVE_TELEGRAM = _real("telegram")


@unittest.skipUnless(HAVE_STACK, "fastapi/httpx/uvicorn/python-multipart not installed")
class RealFastAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import main
        cls.main = main
        cls.client = TestClient(main.app, follow_redirects=False)

    def setUp(self):
        self._key, self._insecure = config.DASHBOARD_KEY, config.ALLOW_INSECURE_DASHBOARD
        import security
        security._fails.clear()

    def tearDown(self):
        config.DASHBOARD_KEY, config.ALLOW_INSECURE_DASHBOARD = self._key, self._insecure

    def test_health_reports_starting_without_engine(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["mode"], "PAPER SIMULATION")
        self.assertEqual(r.headers.get("x-frame-options"), "DENY")

    def test_login_page_renders(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertIn("INITIALIZE", r.text)

    def test_control_posts_blocked_without_key(self):
        config.DASHBOARD_KEY, config.ALLOW_INSECURE_DASHBOARD = "", False
        self.assertEqual(self.client.post("/api/anything").status_code, 403)

    def test_api_requires_key_when_configured(self):
        config.DASHBOARD_KEY = "k" * 16
        self.assertEqual(self.client.get("/api/pro/overview").status_code, 401)
        self.assertIn(self.client.get("/").status_code, (302, 303, 307))

    def test_login_wrong_then_right(self):
        config.DASHBOARD_KEY = "correct-horse-battery"
        bad = self.client.post("/api/login", data={"password": "nope"})
        self.assertEqual(bad.status_code, 401)
        good = self.client.post("/api/login", data={"password": "correct-horse-battery"})
        self.assertEqual(good.status_code, 303)
        self.assertIn("dash_key", good.headers.get("set-cookie", ""))
        self.assertIn("httponly", good.headers["set-cookie"].lower())

    def test_lockout_after_repeated_failures(self):
        config.DASHBOARD_KEY = "correct-horse-battery"
        codes = [self.client.post("/api/login", data={"password": "x%d" % i}).status_code for i in range(7)]
        self.assertEqual(codes[-1], 429)


@unittest.skipUnless(HAVE_TELEGRAM, "python-telegram-bot not installed")
class RealTelegramLibrary(unittest.TestCase):
    def test_application_builds_and_handlers_register_offline(self):
        """Compatibility with the installed python-telegram-bot major version (no network: only builds)."""
        import telegram_bot
        from telegram.ext import Application
        app = Application.builder().token("123456:TEST-TOKEN-NOT-REAL").build()
        n = 0
        for name in ("cmd_start", "cmd_status", "cmd_positions", "cmd_pause", "cmd_resume", "cmd_forceexit",
                     "cmd_help", "handle_callback"):
            self.assertTrue(hasattr(telegram_bot.TelegramNotifier, name), name)
            n += 1
        self.assertEqual(n, 8)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
