/* Headless smoke test of the mobile dashboard: fake DOM + mocked API, runs every view in both languages.
   It catches: exceptions, painting into containers that do not exist, "undefined"/"NaN" leaking into markup,
   duplicated global listeners/intervals. It is NOT a visual test. Usage: node js_smoke.js <project dir> */
const fs = require("fs"), path = require("path"), vm = require("vm");
const ROOT = path.resolve(process.argv[2] || "..");
const fails = [], notes = [];
const fail = (m) => { fails.push(m); };

/* ---------- fake DOM ---------- */
const registry = new Map(), all = new Set();
const ctx2d = new Proxy({}, { get: (t, k) => k === "measureText" ? () => ({ width: 30 }) : (k === "createLinearGradient" ? () => ({ addColorStop() {} }) : (k in t ? t[k] : () => {})), set: (t, k, v) => { t[k] = v; return true; } });
class El {
  constructor(tag, id) { this.tag = tag; this.id = id || ""; this._html = ""; this.style = {}; this.className = ""; this.value = ""; this.textContent = ""; this._kids = []; this._opts = []; this.attrs = {}; all.add(this); }
  get innerHTML() { return this._html; }
  set innerHTML(h) {
    this._kids.forEach((k) => { if (registry.get(k.id) === k) registry.delete(k.id); });
    this._kids = []; this._html = String(h);
    for (const m of this._html.matchAll(/<(\w+)[^>]*\sid="([^"]+)"[^>]*>/g)) { const e = new El(m[1], m[2]); if (m[1] === "select") e._isSel = true; registry.set(m[2], e); this._kids.push(e); }
  }
  get options() { return this._isSel ? [{}, ...this._opts] : this._opts; }
  appendChild(c) { this._opts.push(c); }
  addEventListener(t, fn) { (this.l = this.l || {})[t] = fn; }
  getBoundingClientRect() { return { width: 300, height: 190, left: 0, top: 0 }; }
  getContext() { return ctx2d; }
  click() { this.clicked = true; }
  get offsetWidth() { return 0; }
  toDataURL() { return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ"; }
}
const mk = (id, tag) => { const e = new El(tag || "div", id); registry.set(id, e); return e; };
["boot", "top", "sub", "view", "tabs", "sheet", "toast"].forEach((i) => mk(i));
const docL = {}; let docListenerCount = 0, intervalCount = 0;
const store = new Map();
Object.assign(globalThis, {
  window: globalThis,
  document: { getElementById: (i) => registry.get(i) || null, createElement: (t) => new El(t), documentElement: { style: {}, lang: "", dir: "" }, visibilityState: "visible",
              addEventListener: (t, fn) => { docListenerCount++; docL[t] = fn; } },
  localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
  location: { hash: "", href: "" }, history: { replaceState() {} }, scrollTo() {}, devicePixelRatio: 2,
  setInterval: () => { intervalCount++; return 1; }, clearInterval() {}, setTimeout: (fn) => 1, clearTimeout() {},
  FileReader: class { readAsDataURL() { this.result = "data:image/png;base64,AAAA"; setImmediate(() => this.onload && this.onload()); } },
  Image: class { set src(v) { this.width = 400; this.height = 300; setImmediate(() => this.onload && this.onload()); } }
});

/* ---------- mocked API ---------- */
const now = Math.floor(Date.now() / 1000);
function candles(n) { const out = []; let p = 100; for (let i = 0; i < n; i++) { const o = p; p = p * (1 + Math.sin(i / 4) * 0.004); out.push({ time: now - (n - i) * 900, open: o, high: Math.max(o, p) * 1.002, low: Math.min(o, p) * 0.998, close: p }); } return out; }
const FULL = {
  "/api/pro/overview": { now, initial: 1000, breadth: 58, portfolio: { equity: 1042.5, cash_balance: 700, open_margin: 300, unrealized_pnl: 12.3, realized_pnl: 30.2, open_count: 1, open_risk: 14 },
    risk: { daily_change: 11.2, daily_limit_hit: false, daily_loss_limit: 30, equity: 1042.5, max_portfolio_risk_pct: 10, open_risk: 14, risk_cap: 104.25, risk_remaining: 90 },
    perf: { total_trades: 6, wins: 4, losses: 2, win_rate: 66.7, profit_factor: 2.4, net_pnl: 30.2, gross_profit: 50, gross_loss: 20, avg_r: 0.6, total_fees: 3.1, total_funding: 0.4 },
    status: { running: true, paused: false, last_scan: now - 20, last_error: null, mode: "PAPER SIMULATION", compass: { spot: "BULLISH", futures: "NEUTRAL" }, data_ok: true, data_reason: "", ws_connected: true },
    positions: [{ id: "p1", symbol: "SOLUSDT", source: "futures", side: "LONG", entry: 100, price: 103, stop: 98, initial_stop: 97, target: 106, qty: 3, margin: 300, risk: 14, risk_initial: 14, pnl: 9, realized_partial: 0, funding: 0.1, leverage: 1, liquidation: null, scaled_out: false, pnl_pct: 3, r: 1, opened: now - 3700, strategy: "trend", score: 72, regime: "TREND" }] },
  "/api/pro/equity": Array.from({ length: 60 }, (_, i) => ({ t: now - (60 - i) * 600, v: 1000 + i * 0.7 + Math.sin(i) * 3 })),
  "/api/pro/history": [
    { id: "h1", symbol: "BTCUSDT", source: "futures", side: "LONG", entry: 60000, exit: 60600, pnl: 8, gross: 9, fees: 1, funding: 0, r: 0.8, reason: "TAKE_PROFIT", opened: now - 90000, closed: now - 86000, strategy: "trend" },
    { id: "h2", symbol: "ETHUSDT", source: "spot", side: "LONG", entry: 3000, exit: 2950, pnl: -6, gross: -5, fees: 1, funding: 0, r: -1.1, reason: "STOP_LOSS", opened: now - 50000, closed: now - 40000, strategy: "breakout" },
    { id: "h3", symbol: "SOLUSDT", source: "futures", side: "SHORT", entry: 150, exit: 146, pnl: 5, gross: 6, fees: 1, funding: 0.2, r: 0.7, reason: "TRAILING_STOP", opened: now - 8000, closed: now - 3000, strategy: "trend" }],
  "/api/pro/signals": [
    { symbol: "SOLUSDT", source: "futures", action: "BUY", score: 72, reason: "[trend] EMA aligned", t: now - 3700 },
    { symbol: "BTCUSDT", source: "futures", action: "HOLD", score: 40, reason: "Blocked: Correlation data unavailable for BTCUSDT | RSI too high (81)", t: now - 100 },
    { symbol: "ETHUSDT", source: "spot", action: "HOLD", score: 38, reason: "No setup", t: now - 200 },
    { symbol: "XRPUSDT", source: "futures", action: "SELL", score: 61, reason: "[dip_buyer] pump fade", t: now - 5000 }],
  "/api/pro/system": { version: "7.2.0", status: {}, ml: { present: true, valid: true, accuracy: 0.57, baseline: 0.52, rows: 9000, age_hours: 12.5 }, protection: { blocked: false, reason: "" },
    strategies: { trend: true, breakout: true, dip_buyer: false }, symbols: 50, scan_every: 180, storage: { path: "/data/x.db", fallback_used: false, persistent: true, on_mount: true },
    integrity: { cash_minus_ledger: 0, cash_margin_identity: 0, realized_minus_trades: 0 }, telegram: true,
    risk: { per_trade: 2, portfolio: 10, daily_limit: 3, max_drawdown: 15, max_positions: 5 }, auto: { strategy: "trend", rsi: 14, ema: 21 } },
  "/api/live_tickers": ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA"].map((s, i) => ({ symbol: s, price: 100 + i * 7.5, change: (i % 2 ? -1 : 1) * (i + 0.4), volume: 1e9 / (i + 1) })),
  "/api/market_klines": candles(100), "/api/run_backtest": { success: true, report: "ok" }, "/api/toggle_pause": { paused: true }
};
const EMPTY = JSON.parse(JSON.stringify(FULL));
EMPTY["/api/pro/overview"].positions = []; EMPTY["/api/pro/overview"].perf = { total_trades: 0, wins: 0, losses: 0, win_rate: 0, profit_factor: 0, net_pnl: 0, gross_profit: 0, gross_loss: 0, avg_r: 0, total_fees: 0, total_funding: 0 };
EMPTY["/api/pro/overview"].breadth = null; EMPTY["/api/pro/overview"].status.compass = {}; EMPTY["/api/pro/equity"] = []; EMPTY["/api/pro/history"] = []; EMPTY["/api/pro/signals"] = []; EMPTY["/api/live_tickers"] = [];
EMPTY["/api/pro/system"].ml = { present: false }; delete EMPTY["/api/pro/system"].telegram;
let DATA = FULL, DOWN = false;
globalThis.fetch = async (url) => {
  const p = String(url).split("?")[0];
  if (DOWN) throw new Error("network down");
  if (!(p in DATA)) return { status: 404, ok: false, json: async () => ({ error: "nf " + p }) };
  return { status: 200, ok: true, json: async () => JSON.parse(JSON.stringify(DATA[p])) };
};

/* ---------- load the real modules in the real order ---------- */
const order = ["pro_i18n", "pro_core", "pro_charts", "pro_overview", "pro_markets", "pro_trades", "pro_signals", "pro_tools", "pro_more"];
order.forEach((m) => vm.runInThisContext(fs.readFileSync(path.join(ROOT, m + ".js"), "utf8"), { filename: m + ".js" }));
const Q = window.Q, mods = window.__mods;
["i18n", "core", "charts", "overview", "markets", "trades", "signals", "tools", "more"].forEach((m) => { if (!mods.includes(m)) fail("module did not register: " + m); });

/* track paints into containers that do not exist */
const origPaint = Q.paint;
Q.paint = function (id, html) { if (!registry.has(id)) fail("paint into missing element #" + id + " (view " + Q.S.tab + ", lang " + Q.S.lang + ")"); return origPaint.call(this, id, html); };
const origC = Q.charts;
["area", "bars", "candles"].forEach((k) => { const f = origC[k]; origC[k] = function (cv) { if (!cv) fail("chart " + k + " called without canvas (view " + Q.S.tab + ")"); return f.apply(this, arguments); }; });

function leaks(where) {
  for (const e of all) {
    const h = e._html || "";
    for (const bad of ["undefined", "NaN", "[object", "null</", ">null"]) if (h.includes(bad)) { fail("'" + bad + "' leaked into markup in " + where + ": " + (e.id || e.tag) + " ..." + h.slice(Math.max(0, h.indexOf(bad) - 60), h.indexOf(bad) + 40).replace(/\s+/g, " ")); return; }
  }
}
const VIEWS = ["overview", "markets", "signals", "positions", "more", "history", "analytics", "health", "tools", "settings"];
const tgt = (attrs) => ({ attrs, closest(sel) { const m = /\[([\w-]+)\]/.exec(sel); return m && attrs[m[1]] !== undefined ? this : null; }, getAttribute(n) { return attrs[n]; }, value: attrs.value || "" });
const click = async (act, v, extra) => { const r = registry.get("view"); const t = tgt(Object.assign({ "data-act": act, "data-v": v }, extra || {})); if (r.onclick) r.onclick({ target: t }); await new Promise((x) => setImmediate(x)); await Q.refresh(); };
const sleep = () => new Promise((x) => setImmediate(x));

(async () => {
  Q.start(); await sleep(); await sleep();
  const afterStart = { docL: docListenerCount, iv: intervalCount };
  for (const lang of ["en", "ar"]) {
    Q.S.lang = lang;
    for (const [label, data] of [["full", FULL], ["empty", EMPTY]]) {
      DATA = data; DOWN = false; Q._last = {}; Q.S.ov = null; Q.S.hist = null; Q.S.sig = null; Q.S.sys = null; Q.S.eq = []; Q.S.tk = [];
      for (const v of VIEWS) {
        try { await Q.go(v); await sleep(); await Q.refresh(); } catch (e) { fail("view " + v + " [" + lang + "/" + label + "] threw: " + (e && e.stack || e)); continue; }
        if (!registry.get("view")._html.length) fail("view " + v + " rendered nothing [" + lang + "/" + label + "]");
        leaks(v + " [" + lang + "/" + label + "]");
      }
    }
  }
  /* interactions on full data */
  Q.S.lang = "en"; DATA = FULL; DOWN = false; Q._last = {}; Q.S.ov = null; Q.S.hist = null; Q.S.sig = null; Q.S.sys = null; Q.S.eq = []; Q.S.tk = [];
  try {
    await Q.go("signals"); for (const s of ["signals", "model", "alerts", "all"]) { await click("sgseg", s); leaks("signals/" + s); }
    await Q.go("signals"); await click("sgseg", "signals"); for (const f of ["entries", "blocked", "nodata", "all"]) await click("sf", f);
    const keyOpen = Object.keys(Q.S.open).length; await click("sgx", "sg:" + FULL["/api/pro/signals"][0].t + "SOLUSDT"); if (Object.keys(Q.S.open).length <= keyOpen) fail("signal card did not expand");
    await Q.go("markets"); for (const s of ["gain", "loss", "name", "volume"]) await click("msort", s); await click("mrow", "SOL"); await click("mrow", "SOL"); await click("mtf", "1h"); leaks("markets/interact");
    await Q.go("positions"); await click("ptx", null, { "data-id": "p1" }); if (!/pt open/.test(registry.get("po-list")._html)) fail("position card did not expand");
    await Q.go("history"); for (const f of ["wins", "losses", "long", "short", "all"]) await click("hf", f); await click("htx", null, { "data-id": "h1" }); if (!/sg open/.test(registry.get("hi-list")._html)) fail("history row did not expand");
    Q.S.hq = "SOL"; registry.get("view").oninput({ target: { id: "hi-q", value: "SOL" } }); if (/BTC/.test(registry.get("hi-list")._html.replace(/BTCUSDT/g, "X")) && /BTC/.test(registry.get("hi-list")._html)) { /* search filter keeps only SOL rows */ }
    const rows = (registry.get("hi-list")._html.match(/data-act="htx"/g) || []).length; if (rows !== 1) fail("history search should leave exactly 1 row for SOL, got " + rows);
    await Q.go("analytics"); await click("adr", "7"); await click("adr", "30"); await click("eqr", "7d");
    await Q.go("overview"); await click("eqr", "6h"); await click("sym", "ETHUSDT"); await click("tf", "1h");
    docL.click({ target: tgt({ "data-act": "bell" }) }); if (!registry.get("sheet").className.includes("open")) fail("bell did not open the sheet"); Q.closeSheet();
    docL.click({ target: tgt({ "data-act": "profile" }) }); if (!registry.get("sheet").className.includes("open")) fail("profile sheet did not open"); Q.closeSheet();
    docL.click({ target: tgt({ "data-tab": "markets" }) }); await sleep(); if (Q.S.tab !== "markets") fail("bottom nav did not navigate");
    docL.click({ target: tgt({ "data-act": "settings" }) }); await sleep(); if (Q.S.tab !== "settings") fail("settings button did not navigate");
    docL.click({ target: tgt({ "data-act": "back" }) }); await sleep(); if (Q.S.tab !== "more") fail("back button did not return to More");
    if (!/aria-current="page"/.test(registry.get("tabs")._html) || !/data-tab="more"[^>]*aria-current|aria-current="page"[^>]*>[^<]*<svg[\s\S]*?<span class="l">(More|المزيد)/.test(registry.get("tabs")._html)) notes.push("nav highlight check is approximate");
    /* profile: name + photo */
    Q.saveProfile("  Fedi Tl  ", "data:image/jpeg;base64,/9j/4AAQSkZJRg=="); if (Q.S.name !== "Fedi Tl" || !Q.S.avatar) fail("valid profile not saved");
    if (!/<img[^>]+src="data:image\/jpeg;base64,/.test(registry.get("top")._html)) fail("avatar not rendered in header");
    Q.saveProfile("Fedi Tl", 'javascript:alert(1)"><script>'); if (Q.S.avatar) fail("malicious avatar string was accepted");
    Q.saveProfile("<img src=x onerror=alert(1)>", ""); if (/<img src=x/.test(registry.get("top")._html)) fail("profile name was not escaped");
    Q.saveProfile("", ""); if (Q.S.name !== "Fedi Tl") fail("empty name should fall back to Fedi Tl");
    if (!/Fedi Tl/.test(registry.get("top")._html)) fail("greeting must contain the name Fedi Tl");
    /* profile through the REAL sheet buttons (the Save button used to throw after the sheet emptied itself) */
    const sheetBtns = () => registry.get("sh-act")._opts;
    Q.profileSheet(); registry.get("pf-name").value = "Fedi Tl";
    await registry.get("pf-file").l.change({ target: { files: [{ type: "image/png", size: 5000 }] } }); await sleep(); await sleep();
    if (!/<img/.test(registry.get("pf-av")._html)) fail("photo preview not shown after choosing a file");
    try { sheetBtns()[sheetBtns().length - 1].l.click(); } catch (e) { fail("Save button threw: " + e.message); }
    if (!Q.S.avatar) fail("photo was not saved through the sheet Save button");
    if (registry.get("sheet").className.includes("open")) fail("sheet should close after Save");
    if (!/<img[^>]+src="data:image\/jpeg/.test(registry.get("top")._html)) fail("saved photo not shown in the header");
    Q.profileSheet(); await registry.get("pf-file").l.change({ target: { files: [{ type: "text/plain", size: 10 }] } }); await sleep();
    sheetBtns()[2].l.click(); if (!Q.S.avatar) fail("a non-image file must not remove the saved photo");
    Q.profileSheet(); sheetBtns()[1].l.click(); sheetBtns()[2].l.click(); if (Q.S.avatar) fail("Remove photo + Save should clear the photo");
    /* gauge: empty arcs draw nothing; dash pattern must not repeat (it painted stray dots at both ends) */
    const svg = Q.charts.arcs([{ pct: 0, color: "#d6ff1f" }, { pct: 0, color: "#ff6b6b" }, { pct: 100, color: "#999999" }], "x");
    if ((svg.match(/class="fg"/g) || []).length !== 1 || (svg.match(/<circle/g) || []).length !== 1) fail("empty gauge arcs must not render foreground/dot");
    if (/stroke-dasharray="[\d.]+ 100"/.test(svg)) fail("gauge dash gap must exceed the path length");
    /* language switch */
    Q.setLang("ar"); await sleep(); if (!/أهلاً/.test(registry.get("top")._html)) fail("Arabic greeting missing"); Q.setLang("en"); await sleep();
    /* alerts derive from real state */
    Q.S.ov.status.paused = true; Q.S.ov.status.data_ok = false; Q.S.ov.status.data_reason = "stale"; const al = Q.alerts().map((a) => a.t).join("|"); if (!/paused/i.test(al) || !/data/i.test(al)) fail("alerts missing for paused/data problem: " + al);
  } catch (e) { fail("interaction threw: " + (e && e.stack || e)); }
  /* server down: error state with retry, no exception */
  DOWN = true; Q._last = {}; Q.S.ov = null; Q.S.online = true;
  for (const v of VIEWS) { try { await Q.go(v); await Q.refresh(); } catch (e) { fail("view " + v + " threw while server down: " + e); } if (v !== "tools" && v !== "settings" && v !== "more" && !/data-act="retry"/.test(registry.get("view")._html + [...all].map((e) => e._html).join(""))) notes.push("no retry button seen for " + v + " while offline"); }
  if (Q.S.online !== false) fail("online flag should be false when fetch fails");
  /* no duplicated global listeners / timers after many navigations */
  if (docListenerCount !== afterStart.docL || intervalCount !== afterStart.iv) fail("listeners/intervals grew after navigation: " + JSON.stringify({ afterStart, docListenerCount, intervalCount }));
  /* i18n coverage for every literal key */
  const src = order.slice(1).map((m) => fs.readFileSync(path.join(ROOT, m + ".js"), "utf8")).join("\n"), I = window.QI18N;
  const used = new Set([...src.matchAll(/Q\.t\("([A-Za-z_0-9]+)"\)/g)].map((m) => m[1]));
  ["overview", "markets", "signals", "positions", "more"].forEach((k) => used.add("nav_" + k)); ["history", "analytics", "health", "tools", "settings"].forEach((k) => used.add("sub_" + k));
  ["6h", "1d", "7d", "all"].forEach((k) => used.add("r" + k)); ["bullish", "bearish", "neutral", "long", "short"].forEach((k) => used.add(k));
  [...src.matchAll(/\["[a-z]+",\s*"([a-z]+_[a-z_]+)"\]/g)].forEach((m) => used.add(m[1]));
  const missing = [...used].filter((k) => !(k in I.en) || !(k in I.ar)); if (missing.length) fail("missing translations: " + missing.join(", "));
  const onlyOne = Object.keys(I.en).filter((k) => !(k in I.ar)).concat(Object.keys(I.ar).filter((k) => !(k in I.en))); if (onlyOne.length) fail("keys not in both languages: " + onlyOne.join(", "));
  console.log(JSON.stringify({ views: VIEWS.length, languages: 2, scenarios: ["full", "empty", "server-down", "interactions"], translations: Object.keys(I.en).length, notes, failures: fails }, null, 1));
  process.exit(fails.length ? 1 : 0);
})().catch((e) => { console.log(JSON.stringify({ crash: String(e && e.stack || e), failures: fails }, null, 1)); process.exit(2); });
