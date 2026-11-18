import ast
import asyncio
import pathlib
import re
import subprocess
import unittest

import _env  # noqa: F401
import config
import security
import telegram_bot
from telegram_bot import TelegramNotifier
from engine import Engine
from helpers import make_db, open_pos, check_integrity
from test_engine_integration import FakeMarket, Notifier, run

ROOT = pathlib.Path(_env.ROOT)


class Security(unittest.TestCase):
    def test_session_token_never_contains_key(self):
        t = security.session_token("s3cret-key")
        self.assertNotIn("s3cret", t)
        self.assertEqual(t, security.session_token("s3cret-key"))
        self.assertNotEqual(t, security.session_token("other"))

    def test_credentials(self):
        k = "abc123"
        self.assertTrue(security.check_credentials(k, supplied_key="abc123"))
        self.assertTrue(security.check_credentials(k, supplied_token=security.session_token(k)))
        self.assertFalse(security.check_credentials(k, supplied_key="abc124"))
        self.assertFalse(security.check_credentials(k, supplied_token="x"))
        self.assertFalse(security.check_credentials(k))
        self.assertTrue(security.check_credentials("", supplied_key=""))     # empty key = open (POSTs blocked in main.py)

    def test_lockout_and_expiry(self):
        ip = "9.9.9.9"
        security._fails.clear()
        for i in range(security.MAX_FAILS):
            self.assertFalse(security.is_locked(ip, now=1000.0 + i))
            security.register_failure(ip, now=1000.0 + i)
        self.assertTrue(security.is_locked(ip, now=1010.0))
        self.assertFalse(security.is_locked(ip, now=1000.0 + security.LOCK_SECONDS + 5))
        security.register_failure(ip, now=5000.0)
        security.clear_failures(ip)
        self.assertFalse(security.is_locked(ip, now=5001.0))

    def test_client_ip_uses_proxy_appended_hop_not_spoofable_first_hop(self):
        self.assertEqual(security.client_ip("6.6.6.6, 1.2.3.4", "10.0.0.1"), "1.2.3.4")
        self.assertEqual(security.client_ip("", "10.0.0.1"), "10.0.0.1")
        self.assertEqual(security.client_ip("6.6.6.6", "10.0.0.1", trusted_proxy=False), "10.0.0.1")


class FakeMsg:
    def __init__(self):
        self.sent = []

    async def reply_text(self, text, reply_markup=None):
        self.sent.append(text)


class FakeQuery:
    def __init__(self, data):
        self.data, self.edits, self.answers = data, [], 0

    async def answer(self, *a, **k):
        self.answers += 1

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


class FakeUpdate:
    def __init__(self, uid, data=None):
        self.effective_user = type("U", (), {"id": uid})()
        self.effective_message = FakeMsg()
        self.callback_query = FakeQuery(data) if data is not None else None


class Ctx:
    def __init__(self, args=None):
        self.args = args or []


class Telegram(unittest.TestCase):
    ADMIN = 4242

    def setUp(self):
        self._old = config.TELEGRAM_ADMIN_ID
        config.TELEGRAM_ADMIN_ID = str(self.ADMIN)
        self.addCleanup(lambda: setattr(config, "TELEGRAM_ADMIN_ID", self._old))
        self.db = make_db(1000)
        self.market = FakeMarket()
        self.eng = Engine(self.db, self.market)
        self.bot = TelegramNotifier(self.db, self.eng)
        self.bot.engine = self.eng
        self.pos = open_pos(self.eng.trader, "SOLUSDT", self.market.price, 1.0)["position"]

    COMMANDS = ["cmd_start", "cmd_status", "cmd_balance", "cmd_performance", "cmd_risk", "cmd_history",
                "cmd_positions", "cmd_pause", "cmd_resume", "cmd_help", "cmd_profit", "cmd_daily", "cmd_stats",
                "cmd_pairs", "cmd_count", "cmd_forceexit"]

    def test_every_command_rejects_non_admin_without_side_effects(self):
        for name in self.COMMANDS:
            up = FakeUpdate(999)
            run(getattr(self.bot, name)(up, Ctx(["all"])))
            self.assertEqual(len(up.effective_message.sent), 1, name)
            self.assertIn("غير مصرح", up.effective_message.sent[0], name)
        self.assertFalse(self.eng.paused)
        self.assertEqual(len(self.db.get_open_positions()), 1)               # /forceexit all did NOT run

    def test_callbacks_reject_non_admin(self):
        for data in ("toggle_pause", f"close_{self.pos['id']}"):
            up = FakeUpdate(999, data)
            run(self.bot.handle_callback(up, Ctx()))
        self.assertFalse(self.eng.paused)
        self.assertEqual(len(self.db.get_open_positions()), 1)

    def test_missing_user_is_rejected(self):
        up = FakeUpdate(self.ADMIN)
        up.effective_user = None
        run(self.bot.cmd_pause(up, Ctx()))
        self.assertFalse(self.eng.paused)

    def test_admin_commands_work(self):
        for name in self.COMMANDS:
            if name in ("cmd_forceexit",):
                continue
            up = FakeUpdate(self.ADMIN)
            run(getattr(self.bot, name)(up, Ctx()))
            self.assertTrue(up.effective_message.sent, name)
            self.assertNotIn("غير مصرح", up.effective_message.sent[0], name)

    def test_pause_resume_toggle(self):
        run(self.bot.cmd_pause(FakeUpdate(self.ADMIN), Ctx()))
        self.assertTrue(self.eng.paused)
        run(self.bot.cmd_resume(FakeUpdate(self.ADMIN), Ctx()))
        self.assertFalse(self.eng.paused)
        up = FakeUpdate(self.ADMIN, "toggle_pause")
        run(self.bot.handle_callback(up, Ctx()))
        self.assertTrue(self.eng.paused)

    def test_risk_report_matches_risk_manager(self):
        up = FakeUpdate(self.ADMIN)
        run(self.bot.cmd_risk(up, Ctx()))
        st = self.eng.risk.get_risk_status()
        self.assertIn(f"{st['open_risk']:.2f} / {st['risk_cap']:.2f}", up.effective_message.sent[0])

    def test_forceexit_closes_with_live_price_and_notifies(self):
        self.bot.engine = self.eng
        sent = []

        async def fake_send(msg, reply_markup=None):
            sent.append(msg)
            return True
        self.bot.send = fake_send
        up = FakeUpdate(self.ADMIN)
        run(self.bot.cmd_forceexit(up, Ctx([str(self.pos["id"])])))
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertTrue(sent)
        check_integrity(self, self.db)

    def test_forceexit_bad_args_do_not_crash(self):
        for args in ([], ["abc"], ["99999"]):
            up = FakeUpdate(self.ADMIN)
            run(self.bot.cmd_forceexit(up, Ctx(args)))
            self.assertEqual(len(up.effective_message.sent), 1)
        self.assertEqual(len(self.db.get_open_positions()), 1)

    def test_close_callback_garbage_and_no_price(self):
        up = FakeUpdate(self.ADMIN, "close_notanumber")
        run(self.bot.handle_callback(up, Ctx()))
        self.assertEqual(len(self.db.get_open_positions()), 1)
        self.market.price_error = True
        up = FakeUpdate(self.ADMIN, f"close_{self.pos['id']}")
        run(self.bot.handle_callback(up, Ctx()))
        self.assertEqual(len(self.db.get_open_positions()), 1)               # no price -> no blind close

    def test_close_callback_closes(self):
        up = FakeUpdate(self.ADMIN, f"close_{self.pos['id']}")
        run(self.bot.handle_callback(up, Ctx()))
        self.assertEqual(self.db.get_open_positions(), [])
        self.assertIn("✅", up.callback_query.edits[0])

    def test_disabled_telegram_never_blocks_engine(self):
        old = (config.TELEGRAM_TOKEN, config.TELEGRAM_ADMIN_ID)
        config.TELEGRAM_TOKEN = ""
        try:
            bot = TelegramNotifier(self.db, self.eng)
            run(bot.start())
            self.assertFalse(bot.enabled)
            self.assertFalse(run(bot.send("hello")))
            run(bot.notify_trade_opened(self.pos))
            run(bot.close())
        finally:
            config.TELEGRAM_TOKEN, config.TELEGRAM_ADMIN_ID = old

    def test_notification_content(self):
        captured = []
        self.bot.enabled = True

        async def fake_send(msg, reply_markup=None):
            captured.append(msg)
            return True
        self.bot.send = fake_send
        run(self.bot.notify_trade_opened(self.pos))
        self.assertIn("SOLUSDT", captured[0])
        self.assertIn(f"{self.pos['risk_amount']:.2f}", captured[0])
        closed = self.eng.trader.close_position(self.pos["id"], self.market.price, "MANUAL")
        run(self.bot.notify_trade_closed(closed))
        self.assertIn(f"{closed['net_pnl']:+.4f}", captured[1])


PY_FILES = sorted(ROOT.glob("*.py"))


class StaticChecks(unittest.TestCase):
    def test_all_python_compiles(self):
        for f in PY_FILES + list((ROOT / "tests").glob("*.py")):
            ast.parse(f.read_text(encoding="utf-8"), str(f))

    def test_no_duplicate_routes_and_routers_included_once(self):
        seen = {}
        for f in ("ui.py", "dashboard.py", "main.py"):
            tree = ast.parse((ROOT / f).read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) \
                                and dec.func.attr in ("get", "post", "put", "delete") and dec.args \
                                and isinstance(dec.args[0], ast.Constant):
                            key = (dec.func.attr.upper(), dec.args[0].value)
                            self.assertNotIn(key, seen, f"duplicate route {key}: {seen.get(key)} and {f}")
                            seen[key] = f
        main_src = (ROOT / "main.py").read_text()
        includes = re.findall(r"include_router\((\w+)\)", main_src)
        self.assertEqual(len(includes), len(set(includes)), includes)

    def test_every_endpoint_the_frontend_calls_exists(self):
        routes = set()
        for f in ("ui.py", "dashboard.py", "main.py"):
            routes |= set(re.findall(r'\.(?:get|post)\("(/[^"]*)"', (ROOT / f).read_text()))
        pat = lambda r: re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", r) + "$")
        for js in ROOT.glob("pro_*.js"):
            for m in re.findall(r'["\'](/api/[A-Za-z0-9_/\-]+)', js.read_text()):
                m = m.rstrip("/")
                self.assertTrue(any(pat(r).match(m) or r.startswith(m) for r in routes), f"{js.name}: {m}")

    def test_javascript_syntax(self):
        node = subprocess.run(["which", "node"], capture_output=True, text=True).stdout.strip()
        if not node:
            self.skipTest("node not installed")
        for js in ROOT.glob("pro_*.js"):
            r = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{js.name}: {r.stderr}")

    def test_no_secrets_in_repository(self):
        pats = [re.compile(p) for p in (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b",        # telegram bot token
                                        r"(?i)api[_-]?secret\s*[=:]\s*['\"][^'\"]{8,}",
                                        r"(?i)AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
        for f in ROOT.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".js", ".html", ".css", ".md", ".toml", ".txt", ".example", "") \
                    and ".git" not in f.parts and "__pycache__" not in f.parts and f.stat().st_size < 400_000:
                text = f.read_text(errors="ignore")
                for p in pats:
                    self.assertIsNone(p.search(text), f"{f.name} matches {p.pattern}")

    def test_env_example_has_no_filled_secrets(self):
        env = (ROOT / ".env.example").read_text()
        for key in ("TELEGRAM_TOKEN", "TELEGRAM_ADMIN_ID", "TELEGRAM_CHAT_ID", "DASHBOARD_KEY"):
            self.assertRegex(env, rf"(?m)^{key}=\s*$")

    def test_paper_only_no_exchange_credentials_or_order_calls(self):
        self.assertTrue(config.PAPER_MODE)
        banned = re.compile(r"(?i)(BINANCE_API_KEY|BINANCE_SECRET|X-MBX-APIKEY|hmac.*signature|newOrder|/order\b)")
        for f in PY_FILES:
            if f.name in ("security.py",):
                continue
            self.assertIsNone(banned.search(f.read_text()), f.name)
        old = config.PAPER_MODE
        try:
            config.PAPER_MODE = False
            with self.assertRaises(RuntimeError):
                config.validate_config()
        finally:
            config.PAPER_MODE = old

    def test_config_rejects_unsafe_risk_settings(self):
        for name, val in (("MAX_PORTFOLIO_RISK_PCT", 15.0), ("MAX_PORTFOLIO_RISK_PCT", 0.0),
                          ("FUTURES_LEVERAGE", 50.0), ("MAX_SAME_SIDE", 0)):
            old = getattr(config, name)
            setattr(config, name, val)
            try:
                with self.assertRaises(ValueError, msg=f"{name}={val}"):
                    config.validate_config()
            finally:
                setattr(config, name, old)
        self.assertTrue(config.validate_config())

    def test_deployment_files_consistent(self):
        docker = (ROOT / "Dockerfile").read_text()
        toml = (ROOT / "railway.toml").read_text()
        reqs = (ROOT / "requirements.txt").read_text().lower()
        self.assertRegex(docker, r"FROM python:3\.1[12]")
        self.assertIn("main.py", docker)
        self.assertIn('healthcheckPath = "/health"', toml)
        self.assertIn('"/health"', (ROOT / "main.py").read_text())
        for pkg in ("fastapi", "uvicorn", "aiohttp", "pandas", "numpy", "python-telegram-bot", "scikit-learn",
                    "joblib", "websockets", "python-multipart", "python-dotenv"):
            self.assertIn(pkg, reqs, pkg)
        self.assertTrue((ROOT / ".dockerignore").exists() and (ROOT / ".gitignore").exists())
        self.assertIn(".env", (ROOT / ".dockerignore").read_text())

    def test_every_import_resolves_to_a_project_module_or_declared_dependency(self):
        mods = {f.stem for f in PY_FILES}
        std = set(__import__("sys").stdlib_module_names)
        declared = {"fastapi", "uvicorn", "aiohttp", "pandas", "numpy", "telegram", "dotenv", "sklearn", "joblib",
                    "websockets", "nltk", "starlette", "multipart"}
        for f in PY_FILES:
            for node in ast.walk(ast.parse(f.read_text())):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                for n in names:
                    self.assertTrue(n in mods or n in std or n in declared, f"{f.name}: unknown import {n}")

    def test_project_internal_names_exist(self):
        """Every `from module import name` between project modules must name something that exists."""
        mods = {f.stem: ast.parse(f.read_text()) for f in PY_FILES}
        for f, tree in mods.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in mods:
                    defined = set()
                    for n in ast.walk(mods[node.module]):
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            defined.add(n.name)
                        elif isinstance(n, ast.Assign):
                            for t in n.targets:
                                if isinstance(t, ast.Name):
                                    defined.add(t.id)
                        elif isinstance(n, (ast.Import, ast.ImportFrom)):
                            defined.update((a.asname or a.name).split(".")[0] for a in n.names)
                    for a in node.names:
                        self.assertIn(a.name, defined, f"{f}.py imports {a.name} from {node.module}.py")


if __name__ == "__main__":
    unittest.main()
