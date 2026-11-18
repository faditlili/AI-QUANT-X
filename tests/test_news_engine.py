"""news_engine: whole-word risk matching and real coin attribution (regression for substring bugs)."""
import asyncio
import time
import unittest

import _env  # noqa: F401
import config
import news_engine
from news_engine import NewsEngine, is_risk_headline, mentions_symbol


class RiskWords(unittest.TestCase):
    def test_ban_is_not_matched_inside_other_words(self):
        for title in ("Bank of America adds Bitcoin custody", "Urban mining firm lists token",
                      "Exploitation of oracle is a myth, says dev", "Hackathon winners announced",
                      "Fidelity banking unit lists ETH"):
            self.assertFalse(is_risk_headline(title), title)

    def test_real_risk_headlines_are_matched(self):
        for title in ("Binance banned in country X", "Exchange hacked for $40M", "Protocol exploited, funds drained",
                      "SEC lawsuit hits issuer", "Lender files for bankruptcy", "Founder charged with fraud",
                      "Rug pull scam on new memecoin", "Regulator bans leverage trading"):
            self.assertTrue(is_risk_headline(title), title)

    def test_arabic_terms_still_match(self):
        self.assertTrue(is_risk_headline("اختراق منصة تداول كبرى"))
        self.assertTrue(is_risk_headline("قرار بحظر العملات الرقمية"))

    def test_public_constant_is_preserved(self):
        self.assertIn("ban", news_engine.RISK_WORDS)


class Attribution(unittest.TestCase):
    def test_no_three_letter_prefix_false_positives(self):
        self.assertFalse(mentions_symbol("New solution for scaling announced", "SOLUSDT"))
        self.assertFalse(mentions_symbol("Boston and Washington regulators meet", "TONUSDT"))
        self.assertFalse(mentions_symbol("Shipping firm adopts stablecoin", "SHIBUSDT"))
        self.assertFalse(mentions_symbol("Fund raises 100 million for AI", "1000PEPEUSDT"))

    def test_names_and_tickers_are_attributed(self):
        self.assertTrue(mentions_symbol("Bitcoin ETF sees record inflows", "BTCUSDT"))
        self.assertTrue(mentions_symbol("BTC falls below key support", "BTCUSDT"))
        self.assertTrue(mentions_symbol("Solana network suffers outage", "SOLUSDT"))
        self.assertTrue(mentions_symbol("$SOL rallies 8%", "SOLUSDT"))
        self.assertTrue(mentions_symbol("PEPE whales accumulate", "1000PEPEUSDT"))

    def test_common_english_words_do_not_match_lowercase_tickers(self):
        self.assertFalse(mentions_symbol("Price is near all-time high", "NEARUSDT"))
        self.assertFalse(mentions_symbol("Click the link below", "LINKUSDT"))
        self.assertTrue(mentions_symbol("NEAR Protocol announces upgrade", "NEARUSDT"))

    def test_unknown_or_empty_symbol_never_matches(self):
        self.assertFalse(mentions_symbol("Bitcoin up", ""))
        self.assertFalse(mentions_symbol("Bitcoin up", None))


class EngineBehaviour(unittest.TestCase):
    def _engine(self, titles):
        eng = NewsEngine()
        eng.items, eng.updated = list(titles), time.time()
        return eng

    def test_general_news_does_not_leak_to_unrelated_coin(self):
        old = config.NEWS_ENABLED
        config.NEWS_ENABLED = True
        try:
            eng = self._engine(["Solana network exploited for $5M", "Bank of America opens crypto desk"])
            sol = asyncio.run(eng.get_news_risk("SOLUSDT"))
            eth = asyncio.run(eng.get_news_risk("ETHUSDT"))
        finally:
            config.NEWS_ENABLED = old
        self.assertEqual(sol["risk"], 1.0)
        self.assertEqual(eth["risk"], 0.0)

    def test_api_shape_is_unchanged(self):
        old = config.NEWS_ENABLED
        config.NEWS_ENABLED = True
        try:
            res = asyncio.run(self._engine(["Bitcoin steady"]).get_news_risk("BTCUSDT"))
        finally:
            config.NEWS_ENABLED = old
        self.assertEqual(set(res), {"available", "risk", "summary"})

    def test_disabled_by_default_returns_no_risk(self):
        self.assertFalse(config.NEWS_ENABLED)
        res = asyncio.run(NewsEngine().get_news_risk("BTCUSDT"))
        self.assertEqual(res["risk"], 0.0)
        self.assertFalse(res["available"])


if __name__ == "__main__":
    unittest.main()
