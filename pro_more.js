"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;
  var RANGES = { "6h": 21600, "1d": 86400, "7d": 604800, all: 0 };
  function kv(k, v, cls) { return "<div><span>" + k + '</span><b class="num ' + (cls || "") + '">' + v + "</b></div>"; }
  function tile(label, value, cls, sub) { return '<div class="tile"><div class="lbl">' + label + '</div><div class="v num ' + (cls || "") + '">' + value + "</div>" + (sub ? "<small>" + sub + "</small>" : "") + "</div>"; }
  function hl(dot, title, sub, val, cls) { return '<div class="hl"><i class="st ' + dot + '"></i><div class="m"><b>' + title + "</b><small>" + sub + '</small></div><b class="num ' + (cls || "") + '">' + val + "</b></div>"; }

  /* ---------- More: hub ---------- */
  V.more = {
    mount: function (root) {
      root.innerHTML = '<div id="mo-top" class="card"></div><div id="mo-list"></div>';
    },
    update: function () {
      var ov = Q.S.ov, sys = Q.S.sys, a = Q.alerts().filter(function (x) { return x.k !== "info"; }).length;
      Q.paint("mo-top", '<div style="display:flex;align-items:center;gap:14px">' + Q.avatar("xl") + '<div style="min-width:0"><div class="lbl">' + Q.t("welcome") + '</div><div style="font-size:22px;font-weight:700;letter-spacing:-.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + Q.esc(Q.S.name) +
        '</div><span class="tag paper" style="margin-top:6px">' + Q.t("paper") + '</span> <span class="mu num" style="font-size:12px">' + (sys ? "v" + Q.esc(sys.version) : "") + "</span></div></div>");
      var items = [["history", "history", Q.t("sub_history"), Q.t("d_history")], ["analytics", "analytics", Q.t("sub_analytics"), Q.t("d_analytics")], ["health", "health", Q.t("sub_health"), a ? a + " " + Q.t("alerts_n") : Q.t("d_health")],
                   ["tools", "tools", Q.t("sub_tools"), Q.t("d_tools")], ["settings", "gear", Q.t("sub_settings"), Q.t("d_settings")]];
      Q.paint("mo-list", items.map(function (x) {
        return '<button class="hub" data-go="' + x[0] + '"><span class="ico">' + Q.icon(x[1]) + '</span><span class="m"><b>' + x[2] + "</b><small>" + x[3] + '</small></span><span class="go" style="width:38px;height:38px;background:var(--card2)">' + Q.icon("arrow") + "</span></button>";
      }).join(""));
    }
  };

  /* ---------- Analytics ---------- */
  V.analytics = {
    mount: function (root) {
      root.innerHTML =
        '<div class="sec"><div id="an-h1"></div><div class="card"><div id="an-eqt"></div><div class="cvwrap"><canvas id="cv-an-eq" class="cv" role="img" aria-label="Equity curve"></canvas></div><div id="an-rng" style="margin-top:12px"></div></div></div>' +
        '<div id="an-kpi" class="grid4"></div>' +
        '<div class="sec"><div id="an-h2"></div><div class="card"><div id="an-dr" style="margin-bottom:6px"></div><div id="an-bw" class="cvwrap" style="display:none"><canvas id="cv-an-d" class="cv" role="img" aria-label="Daily performance"></canvas></div><div id="an-be"></div></div></div>' +
        '<div class="sec"><div id="an-h3"></div><div class="card"><div id="an-aw" class="cvwrap short" style="display:none"><canvas id="cv-an-a" class="cv" role="img" aria-label="Trading activity"></canvas></div><div id="an-ae"></div></div></div>' +
        '<div class="sec"><div id="an-h4"></div><div id="an-str" class="card"></div></div><div id="an-note" class="mu" style="font-size:11.5px;text-align:center;margin:4px 0 12px"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), v = b.getAttribute("data-v");
        if (a === "eqr") { Q.S.eqr = v; V.analytics.update(); }
        if (a === "adr") { Q.S.ad = Number(v); V.analytics.update(); }
      };
    },
    load: async function () {
      await Q.every("eq", 30000, async function () { Q.S.eq = await Q.api("/api/pro/equity"); });
      await Q.every("hist", 20000, async function () { Q.S.hist = await Q.api("/api/pro/history"); });
    },
    update: function () {
      var ov = Q.S.ov;
      if (!ov) { Q.paint("an-h1", Q.wait()); return; }
      var perf = ov.perf, p = ov.portfolio, base = ov.initial || 0, h = Q.S.hist || [], n = Q.S.ad || 14;
      var all = Q.S.eq || [], sec = RANGES[Q.S.eqr], pts = all;
      if (sec && all.length) { var from = all[all.length - 1].t - sec; pts = all.filter(function (x) { return x.t >= from; }); if (pts.length < 2) pts = all.slice(-2); }
      var peak = 0, maxdd = 0, i;
      for (i = 0; i < all.length; i++) { peak = Math.max(peak, all[i].v); if (peak) maxdd = Math.max(maxdd, ((peak - all[i].v) / peak) * 100); }
      Q.paint("an-h1", Q.head("chart", Q.t("equity_curve"), null));
      Q.paint("an-eqt", '<div class="big num" style="font-size:30px">$' + Q.n(p.equity) + '</div><div class="chg num ' + Q.cls(p.equity - base) + '">' + Q.sg(p.equity - base) + " (" + Q.sg(base ? (p.equity - base) / base * 100 : 0) + "%)</div>");
      Q.paint("an-rng", '<div class="chips">' + ["6h", "1d", "7d", "all"].map(function (k) { return '<button class="chip' + (Q.S.eqr === k ? " on" : "") + '" data-act="eqr" data-v="' + k + '">' + Q.t("r" + k) + "</button>"; }).join("") + "</div>");
      C.area(Q.$("cv-an-eq"), pts, { base: base, empty: Q.t("no_data") });

      var pf = perf.profit_factor, aw = perf.wins ? perf.gross_profit / perf.wins : 0, al = perf.losses ? perf.gross_loss / perf.losses : 0;
      Q.paint("an-kpi",
        tile(Q.t("win_rate"), perf.total_trades ? perf.win_rate.toFixed(1) + "%" : "-", perf.total_trades ? "up" : "mu", "W " + perf.wins + " / L " + perf.losses) +
        tile(Q.t("profit_factor"), pf == null ? "INF" : Q.n(pf), pf == null || pf >= 1 ? "up" : "down", "GP " + Q.n(perf.gross_profit, 1) + " / GL " + Q.n(perf.gross_loss, 1)) +
        tile(Q.t("max_dd"), maxdd.toFixed(2) + "%", maxdd > 10 ? "down" : maxdd > 5 ? "wa" : "up", all.length ? all.length + " " + Q.t("snapshots") : Q.t("na")) +
        tile(Q.t("expectancy"), Q.sg(perf.total_trades ? perf.net_pnl / perf.total_trades : 0), Q.cls(perf.net_pnl), Q.t("avg_r") + " " + Q.sg(perf.avg_r, 2) + "R") +
        tile(Q.t("avg_win"), Q.n(aw), "up", "") + tile(Q.t("avg_loss"), "-" + Q.n(al), "down", Q.t("payoff") + " " + (al ? Q.n(aw / al) : "-")) +
        tile(Q.t("fees"), "-" + Q.n(perf.total_fees), "", "") + tile(Q.t("funding"), Q.sg(-perf.total_funding), "", ""));

      var days = Q.dailyPnl(n), any = days.some(function (d) { return d.has; });
      Q.paint("an-h2", Q.head("analytics", Q.t("daily_perf"), null));
      Q.paint("an-dr", '<div class="chips">' + [7, 14, 30].map(function (k) { return '<button class="chip' + (n === k ? " on" : "") + '" data-act="adr" data-v="' + k + '">' + k + Q.t("d") + "</button>"; }).join("") + "</div>");
      Q.$("an-bw").style.display = any ? "block" : "none";
      Q.paint("an-be", any ? "" : (Q.S.hist == null ? '<div class="sk" style="width:60%"></div>' : Q.empty("analytics", Q.t("no_trades"))));
      if (any) C.bars(Q.$("cv-an-d"), days.map(function (d, k) { return { v: d.v, label: n > 14 ? (k % 3 === 0 ? d.label : "") : d.label }; }), { fmt: function (v) { return Q.sg(v, Math.abs(v) >= 100 ? 0 : 2); }, empty: Q.t("no_data") });

      var act = Q.dailyPnl(n).map(function (d) { return { v: 0, label: d.label, day: d.day }; }), cnt = {};
      h.forEach(function (t) { if (t.closed) { var k = Math.floor(t.closed / 86400); cnt[k] = (cnt[k] || 0) + 1; } });
      act.forEach(function (d, k) { d.v = cnt[d.day] || 0; if (n > 14 && k % 3) d.label = ""; });
      var anyA = act.some(function (d) { return d.v > 0; });
      Q.paint("an-h3", Q.head("scan", Q.t("activity"), null));
      Q.$("an-aw").style.display = anyA ? "block" : "none";
      Q.paint("an-ae", anyA ? "" : (Q.S.hist == null ? "" : Q.empty("scan", Q.t("no_trades"))));
      if (anyA) C.bars(Q.$("cv-an-a"), act, { fmt: function (v) { return String(Math.round(v)); }, empty: Q.t("no_data") });

      var by = {}, mx = 0, k;
      h.forEach(function (t) { var s = by[t.strategy] = by[t.strategy] || { n: 0, w: 0, net: 0, r: 0 }; s.n++; s.net += t.pnl; s.r += t.r; if (t.pnl > 0) s.w++; });
      for (k in by) mx = Math.max(mx, Math.abs(by[k].net));
      Q.paint("an-h4", Q.head("positions", Q.t("strat_perf"), null));
      Q.paint("an-str", Object.keys(by).length ? Object.keys(by).sort(function (a, b) { return by[b].net - by[a].net; }).map(function (s) {
        var x = by[s];
        return '<div class="meter"><div class="row"><b>' + Q.esc(s) + '</b><span class="num ' + Q.cls(x.net) + '">' + Q.sg(x.net) + "</span></div>" + C.bar(mx ? Math.abs(x.net) / mx * 100 : 0, x.net >= 0 ? COL.lime : COL.dn) +
          '<div class="mu num" style="font-size:11.5px;margin-top:5px">' + x.n + " " + Q.t("trades") + " &middot; " + Q.t("win_rate") + " " + (x.w / x.n * 100).toFixed(0) + "% &middot; " + Q.t("avg_r") + " " + Q.sg(x.r / x.n, 2) + "R</div></div>";
      }).join("") : Q.empty("positions", Q.t("no_trades")));
      Q.paint("an-note", h.length ? Q.t("based_on") + " " + h.length + " " + Q.t("recent_trades") : "");
    }
  };

  /* ---------- System health ---------- */
  V.health = {
    mount: function (root) { root.innerHTML = '<div id="hl-body"></div>'; },
    load: async function () { await Q.every("sys", 15000, async function () { Q.S.sys = await Q.api("/api/pro/system"); }); },
    update: function () {
      var ov = Q.S.ov, sys = Q.S.sys;
      if (!ov) { Q.paint("hl-body", Q.wait()); return; }
      var st = ov.status || {}, ml = (sys && sys.ml) || {}, sto = sys && sys.storage, ig = sys && sys.integrity;
      var igOk = ig ? Math.abs(ig.cash_minus_ledger) < 0.01 && Math.abs(ig.cash_margin_identity) < 0.01 && Math.abs(ig.realized_minus_trades) < 0.01 : null;
      var healthy = sys ? Object.keys(sys.strategies || {}).filter(function (k) { return sys.strategies[k]; }).length : 0, total = sys ? Object.keys(sys.strategies || {}).length : 0;
      var rows = [
        hl(!Q.S.online ? "bad" : st.paused ? "off" : st.running ? "on" : "bad", Q.t("engine"), Q.esc(Q.t("last_scan") + ": " + (st.last_scan ? Q.dur(ov.now - st.last_scan) + " " + Q.t("ago") : "-") + (sys ? " \u00b7 " + Q.t("scan_every") + " " + sys.scan_every + Q.t("sec") : "")), !Q.S.online ? Q.t("offline") : st.paused ? Q.t("paused") : st.running ? Q.t("running") : Q.t("offline")),
        hl(!Q.S.online ? "bad" : st.data_ok === false ? "bad" : "on", Q.t("market_data"), Q.esc(st.data_ok === false ? (st.data_reason || "") : Q.t("data_ok_x")), !Q.S.online ? Q.t("no_link") : st.data_ok === false ? Q.t("al_data") : Q.t("ok"), st.data_ok === false || !Q.S.online ? "down" : "up"),
        hl(st.ws_connected ? "on" : "off", Q.t("price_feed"), Q.esc(st.ws_connected ? Q.t("feed_ws_x") : Q.t("al_ws_x")), st.ws_connected ? "WebSocket" : "REST", st.ws_connected ? "up" : "wa"),
        hl(!sto ? "" : sto.persistent ? "on" : "off", Q.t("database"), Q.esc(!sto ? Q.t("loading") : sto.persistent ? Q.t("db_ok_x") : Q.t("al_storage_x")), !sto ? "..." : sto.persistent ? Q.t("persistent") : Q.t("temporary"), !sto ? "mu" : sto.persistent ? "up" : "wa"),
        hl(igOk == null ? "" : igOk ? "on" : "bad", Q.t("ledger"), Q.esc(ig ? "\u0394 " + Q.n(ig.cash_minus_ledger, 4) + " / " + Q.n(ig.cash_margin_identity, 4) + " / " + Q.n(ig.realized_minus_trades, 4) : Q.t("loading")), igOk == null ? "..." : igOk ? Q.t("reconciled") : Q.t("mismatch"), igOk == null ? "mu" : igOk ? "up" : "down"),
        hl(!sys ? "" : ml.present && ml.valid ? "on" : "off", Q.t("ai_sub"), Q.esc(!sys ? Q.t("loading") : !ml.present ? Q.t("ml_none") : ml.valid ? Q.t("ml_on") : Q.t("ml_off")), sys ? healthy + "/" + total + " " + Q.t("strategies") : "...", "mu"),
        hl(!sys || sys.telegram == null ? "" : sys.telegram ? "on" : "off", "Telegram", Q.esc(!sys || sys.telegram == null ? Q.t("na") : sys.telegram ? Q.t("tg_on_x") : Q.t("tg_off_x")), !sys || sys.telegram == null ? Q.t("na") : sys.telegram ? Q.t("configured") : Q.t("not_configured"), "mu"),
        hl(sys && sys.protection && sys.protection.blocked ? "bad" : "on", Q.t("protection"), Q.esc(sys && sys.protection && sys.protection.blocked ? sys.protection.reason : Q.t("ok")), sys && sys.protection && sys.protection.blocked ? Q.t("blocked") : Q.t("ok"), sys && sys.protection && sys.protection.blocked ? "down" : "up"),
        hl(st.last_error ? "off" : "on", Q.t("errors"), Q.esc(st.last_error ? String(st.last_error) : Q.t("no_errors")), st.last_error ? "!" : "0", st.last_error ? "wa" : "up")
      ];
      Q.paint("hl-body", '<div class="sec">' + Q.head("health", Q.t("sub_health"), null) + '<div class="card">' + rows.join("") + "</div></div>" +
        '<div class="sec">' + Q.head("shield", Q.t("mode"), null) + '<div class="card"><div class="h"><span class="tag paper">' + Q.t("paper") + '</span></div><div class="mu" style="font-size:12.5px">' + Q.esc(Q.t("paper_x")) + "</div>" +
        '<div class="kv">' + kv(Q.t("version"), sys ? Q.esc(sys.version) : "-") + kv(Q.t("mode"), Q.esc(st.mode || "PAPER")) + "</div></div></div>");
    }
  };

  /* ---------- Settings & profile ---------- */
  V.settings = {
    mount: function (root) {
      root.innerHTML = '<div id="se-body"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act");
        if (a === "lang-set") Q.setLang(b.getAttribute("data-v"));
      };
    },
    update: function () {
      var ov = Q.S.ov, sys = Q.S.sys, st = (ov && ov.status) || {}, rk = (sys && sys.risk) || null;
      Q.paint("se-body",
        '<div class="sec">' + Q.head("user", Q.t("profile"), null) + '<div class="card" style="text-align:center"><div>' + Q.avatar("xl") + '</div><div style="font-size:22px;font-weight:700;margin:10px 0 2px">' + Q.esc(Q.S.name) + '</div><div class="mu" style="font-size:12px">' + Q.esc(Q.t("photo_note")) +
        '</div><button class="btn pri blk" data-act="profile">' + Q.icon("camera") + Q.t("edit_profile") + "</button></div></div>" +
        '<div class="sec">' + Q.head("lang", Q.t("language"), null) + '<div class="card"><div class="chips"><button class="chip' + (Q.S.lang === "ar" ? " on" : "") + '" data-act="lang-set" data-v="ar">العربية</button><button class="chip' + (Q.S.lang === "en" ? " on" : "") + '" data-act="lang-set" data-v="en">English</button></div></div></div>' +
        '<div class="sec">' + Q.head("cpu", Q.t("engine"), null) + '<div class="card"><div class="h"><span class="sc ' + (st.paused ? "off" : "on") + '"><i class="dot"></i>' + (st.paused ? Q.t("paused") : Q.t("running")) + '</span></div><div class="mu" style="font-size:12.5px">' + Q.esc(Q.t("pause_x")) +
        '</div><button class="btn blk" data-act="pause">' + Q.icon(st.paused ? "play" : "pause") + (st.paused ? Q.t("resume") : Q.t("pause")) + "</button></div></div>" +
        '<div class="sec">' + Q.head("shield", Q.t("risk_cfg"), "tools") + '<div class="card">' + (rk ? '<div class="kv" style="margin-top:0">' + kv(Q.t("per_trade"), rk.per_trade + "%") + kv(Q.t("portfolio"), rk.portfolio + "%") + kv(Q.t("daily_limit"), rk.daily_limit + "%") + kv(Q.t("max_dd"), rk.max_drawdown + "%") + kv(Q.t("max_pos"), rk.max_positions) + "</div>" : '<div class="sk"></div>') +
        '<div class="mu" style="font-size:11.5px;margin-top:10px">' + Q.esc(Q.t("risk_ro")) + "</div></div></div>");
    }
  };
  (window.__mods = window.__mods || []).push("more");
})();
