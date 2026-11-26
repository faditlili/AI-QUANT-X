"""Telegram messages: numbers must keep their sign/units in reading order, and /pairs must not hide losing pairs."""
import asyncio
import os
import re
import unittest

import _env  # noqa: F401
import config
import telegram_bot as T
from engine import Engine
from helpers import make_db, open_pos
from test_engine_integration import FakeMarket
from test_security_telegram_static import Ctx, FakeUpdate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LRI, PDI = T._LRI, T._PDI


def run(coro):
    return asyncio.run(coro)


def plain(text):
    return text.replace(LRI, "").replace(PDI, "")


class NumberIsolation(unittest.TestCase):
    def test_negative_amounts_percentages_and_times_are_isolated_with_their_units(self):
        out = T._b("صافي الربح: -3.9062 USDT\nنسبة النجاح: 71.4%\nR: -1.08\n08:42 UTC")
        for token in ("-3.9062 USDT", "71.4%", "-1.08", "08:42 UTC"):
            self.assertIn(LRI + token + PDI, out, token)

    def test_a_series_like_open_risk_over_cap_stays_in_order_as_one_block(self):
        out = T._b("المخاطرة المفتوحة: 19.62 / 99.96 (المتبقي 80.34)")
        self.assertIn(LRI + "19.62 / 99.96" + PDI, out)             # separate blocks would display as "99.96 / 19.62" in RTL
        self.assertIn(LRI + "80.34" + PDI, out)
        self.assertIn(LRI + "$12 / $24".replace("$", "") + PDI, T._b("12 / 24"))

    def test_symbols_with_digits_and_words_are_untouched_and_text_is_preserved(self):
        for text in ("1000PEPEUSDT: +2.10 USDT (3 صفقة)", "BTCUSDT | LONG", "لا توجد صفقات مغلقة بعد."):
            out = T._b(text)
            self.assertEqual(plain(out), text)
        self.assertNotIn(LRI + "1000" + PDI, T._b("1000PEPEUSDT"))
        self.assertEqual(T._b("لا توجد صفقات"), "لا توجد صفقات")

    def test_every_outgoing_message_goes_through_the_isolator(self):
        with open(os.path.join(ROOT, "telegram_bot.py"), encoding="utf-8") as handle:
            source = handle.read()
        calls = len(re.findall(r"(?:reply_text|edit_message_text)\(", source))
        wrapped = len(re.findall(r"(?:reply_text|edit_message_text)\(_b\(", source))
        self.assertGreaterEqual(calls, 30)
        self.assertEqual(calls, wrapped, "an unwrapped reply_text/edit_message_text would show '34.84-' for a loss")
        self.assertIn("text=_b(message)", source)


class Handlers(unittest.TestCase):
    ADMIN = 4242

    def setUp(self):
        self._old = config.TELEGRAM_ADMIN_ID
        config.TELEGRAM_ADMIN_ID = str(self.ADMIN)
        self.addCleanup(lambda: setattr(config, "TELEGRAM_ADMIN_ID", self._old))
        self.db = make_db(100000)
        self.market = FakeMarket()
        self.eng = Engine(self.db, self.market)
        self.bot = T.TelegramNotifier(self.db, self.eng)
        self.bot.engine = self.eng

    def trade(self, symbol, exit_price, entry=100.0):
        pid = open_pos(self.eng.trader, symbol, entry, max(entry * 0.01, 1e-6))["position"]["id"]
        self.eng.trader.close_position(pid, exit_price, "MANUAL")

    def ask(self, name):
        up = FakeUpdate(self.ADMIN)
        run(getattr(self.bot, name)(up, Ctx([])))
        return up.effective_message.sent[0]

    def test_tiers_groups_trades_by_entry_price_correctly(self):
        self.trade("MICROUSDT", 0.0011, entry=0.001)      # < 0.01$ tier, winner
        self.trade("CENTUSDT", 0.45, entry=0.5)            # 0.01$-1$ tier, loser
        self.trade("MIDUSDT", 106.0, entry=100.0)          # 1$-100$... wait boundary
        self.trade("MAJORUSDT", 68000.0, entry=65000.0)    # > 100$ tier, winner
        text = plain(self.ask("cmd_tiers"))
        self.assertIn("< 0.01$", text)
        self.assertIn("0.01$ - 1$", text)
        self.assertIn("> 100$", text)
        self.assertIn("4 صفقة".replace("4", "1"), text)    # each populated tier has exactly 1 trade below
        self.assertIn("⚠️", text)                           # the slippage-model caveat must always show

    def test_tiers_handles_no_trades_and_sums_match_totals(self):
        text = plain(self.ask("cmd_tiers"))
        self.assertIn("لا توجد صفقات مغلقة بعد", text)
        self.trade("AUSDT", 101.0, entry=100.0)    # entry price boundary: 100 falls in "> 100$" (low <= price)
        self.trade("BUSDT", 0.0002, entry=0.0001)  # "< 0.01$" tier
        self.trade("CUSDT", 50.0, entry=50.0)      # "1$ - 100$" tier
        text = plain(self.ask("cmd_tiers"))
        amounts = [float(m) for m in re.findall(r"([+-]\d+\.\d\d) USDT", text)]
        expected = [float(t["net_pnl"]) for t in self.db.get_closed_trades(50)]
        self.assertAlmostEqual(sum(amounts), sum(expected), delta=0.02)   # rounding of 2 displayed figures
        self.assertEqual(len(amounts), 3, "all three populated tiers must each report their own net once")

    def test_pairs_shows_the_losing_pairs_not_just_the_winners(self):
        for i in range(12):
            self.trade("WIN%dUSDT" % i, 106.0 + i)              # winners
        self.trade("LOSEAUSDT", 94.0)                           # losers must stay visible
        self.trade("LOSEBUSDT", 96.0)
        text = plain(self.ask("cmd_pairs"))
        self.assertIn("الأضعف", text)
        self.assertIn("LOSEAUSDT", text)
        self.assertIn("LOSEBUSDT", text)
        self.assertIn("🔴", text)
        self.assertLessEqual(len([l for l in text.splitlines() if "USDT:" in l]), 15)

    def test_stats_and_performance_keep_negative_signs_readable(self):
        self.trade("AAAUSDT", 106.0)
        self.trade("BBBUSDT", 94.0)
        stats = self.ask("cmd_stats")
        loss = re.search(r"STOP|MANUAL", stats)
        self.assertTrue(loss)
        self.assertRegex(stats, LRI + r"-\d+\.\d{2} USDT" + PDI)           # the loss is isolated: "-x.xx USDT"
        perf = self.ask("cmd_performance")
        self.assertRegex(perf, LRI + r"\d+\.\d%" + PDI)


if __name__ == "__main__":
    unittest.main()
