"""Static + headless checks of the mobile dashboard (pro.html / pro.css / pro_*.js).

The JS smoke test needs Node.js; without it those tests are skipped (the static ones still run).
None of this needs fastapi, so it also runs in minimal environments."""
import glob
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = sorted(glob.glob(os.path.join(ROOT, "pro_*.js"))) + [os.path.join(ROOT, "pro.css"), os.path.join(ROOT, "pro.html")]
NODE = shutil.which("node")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class StaticChecks(unittest.TestCase):
    def test_every_asset_in_pro_html_is_served_by_ui_py(self):
        served = set(re.findall(r'"(pro[\w.]*\.(?:js|css))":', read(os.path.join(ROOT, "ui.py"))))
        used = set(re.findall(r'/pro/([\w.]+\.(?:js|css))', read(os.path.join(ROOT, "pro.html"))))
        self.assertTrue(used)
        self.assertEqual(used - served, set(), "pro.html references files ui.py does not serve")
        for name in used:
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), name)

    def test_every_module_is_in_the_html_readiness_check(self):
        html = read(os.path.join(ROOT, "pro.html"))
        for name in re.findall(r'/pro/pro_(\w+)\.js', html):
            self.assertIn('"%s"' % name, html.split("var need")[1].split("]")[0], name)

    def test_front_end_only_calls_endpoints_that_exist(self):
        routes = read(os.path.join(ROOT, "ui.py")) + read(os.path.join(ROOT, "dashboard.py"))
        defined = set(re.findall(r'@router\.(?:get|post)\("([^"{]+)', routes))
        called = set()
        for path in FRONT:
            if path.endswith(".js"):
                called |= set(re.findall(r'"(/api/[a-z_/]+)', read(path)))
        self.assertTrue(called)
        for api in called:
            self.assertTrue(any(api.rstrip("/") == d.rstrip("/") for d in defined), "unknown endpoint " + api)

    def test_paper_only_no_order_or_money_endpoints(self):
        for path in FRONT:
            if path.endswith(".js"):
                for api in re.findall(r'"(/api/[a-z_/]+)', read(path)):
                    self.assertNotRegex(api, r"order|withdraw|deposit|transfer|live_trade|real", path)

    def test_no_external_urls_no_secrets_no_dangerous_apis(self):
        for path in FRONT:
            text = read(path)
            self.assertNotRegex(text, r"https?://(?!www\.w3\.org)", path)
            self.assertNotRegex(text, r"TELEGRAM_TOKEN|API_SECRET|SECRET_KEY|DASHBOARD_KEY|BINANCE_API", path)
            self.assertNotRegex(text, r"\beval\(|document\.write|new Function\(", path)

    def test_css_guards_against_horizontal_overflow_and_keeps_sentinel(self):
        css = read(os.path.join(ROOT, "pro.css"))
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertTrue(css.rstrip().endswith(":root{--end:1}"))
        self.assertRegex(css, r"(?m)^html\{overflow-x:hidden")
        self.assertNotRegex(css, r"(?m)^body\{[^}]*overflow-x:hidden", "hidden on <body> breaks position:sticky")
        self.assertRegex(css, r"\.btn svg[^{]*\{[^}]*width:18px", "icons inside buttons must have an explicit size")
        self.assertNotRegex(css, r"width:\s*100vw")
        self.assertIn("env(safe-area-inset-bottom", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("minmax(0,1fr)", css)
        self.assertIn("viewport-fit=cover", read(os.path.join(ROOT, "pro.html")))

    def test_touch_targets_are_at_least_44px(self):
        css = read(os.path.join(ROOT, "pro.css"))
        for selector in (r"\.ib", r"\.go", r"\.back \.go", r"\.qb", r"\.btn", r"\.tab"):
            block = re.search(r"(?m)^" + selector + r"\{([^}]*)\}", css)
            self.assertTrue(block, selector)
            size = re.findall(r"(?:min-height|width):(\d+)px", block.group(1))
            self.assertTrue(size and max(int(x) for x in size) >= 44, selector + " is smaller than a 44px touch target")
        # small filter chips stay compact visually but get an invisible 44px hit area
        self.assertRegex(css, r"\.chip::after[^{]*\{[^}]*inset:-4px")

    def test_profile_name_default_and_photo_stay_local(self):
        core = read(os.path.join(ROOT, "pro_core.js"))
        self.assertIn('"Fedi Tl"', core)
        self.assertIn("aiqx_avatar", core)
        self.assertNotRegex(core, r"fetch\([^)]*avatar", "the photo must never be uploaded")


@unittest.skipUnless(NODE, "Node.js not installed")
class NodeChecks(unittest.TestCase):
    def test_javascript_syntax(self):
        for path in [p for p in FRONT if p.endswith(".js")]:
            done = subprocess.run([NODE, "--check", path], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, path + "\n" + done.stderr)

    def test_headless_smoke_all_views_both_languages(self):
        done = subprocess.run([NODE, os.path.join(ROOT, "tests", "js_smoke.js"), ROOT], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
