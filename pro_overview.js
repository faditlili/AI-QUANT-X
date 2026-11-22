"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;
  var RANGES = { "6h": 21600, "1d": 86400, "7d": 604800, all: 0 };

  /* net P&L per UTC day from the closed-trade history (real data only) */
  Q.dailyPnl = function (n) {
    var h = Q.S.hist || [], today = Math.floor(Q.now() / 86400), map = {}, out = [], i;
    h.forEach(function (t) { if (t.closed) { var k = Math.floor(t.closed / 86400); map[k] = (map[k] || 0) + t.pnl; } });
    for (i = n - 1; i >= 0; i--) {
      var d = today - i;
      out.push({ v: map[d] || 0, has: map[d] != null, day: d,
                 label: new Date(d * 86400000).toLocaleDateString(Q.S.lang === "ar" ? "ar" : "en-US", { weekday: "short", timeZone: "UTC" }) });
    }
    return out;
  };

  function tile(label, value, cls, sub) {
    return '<div class="tile"><div class="lbl">' + label + '</div><div class="v num ' + cls + '">' + value + "</div>" + (sub ? "<small>" + sub + "</small>" : "") + "</div>";
  }
  function meter(a, b, pct, color) {
    return '<div class="meter"><div class="row"><span class="num">' + a + '</span><span class="mu num">' + b + "</span></div>" + C.bar(pct, color) + "</div>";
  }
  function movers(list) {
    return list.map(function (x) {
      return '<div class="it" style="padding:8px 0"><div class="m"><b>' + Q.esc(x.symbol) + '</b></div><div class="e num ' + Q.cls(x.change) + '">' + Q.sg(x.change) + "%</div></div>";
    }).join("");
  }

  V.overview = {
    mount: function (root) {
      root.innerHTML =
        '<div class="qa" id="ov-qa"></div>' +
        '<div class="sec"><div id="ov-h1"></div><div class="card"><div id="ov-hero"></div><div class="cvwrap"><canvas id="cv-eq" class="cv" role="img" aria-label="Equity curve"></canvas></div>' +
        '<div id="ov-rng" style="margin-top:12px"></div><div id="ov-sub"></div></div></div>' +
        '<div class="sec"><div id="ov-h2"></div><div class="card"><div id="ov-bars-w" class="cvwrap" style="display:none"><canvas id="cv-bars" class="cv" role="img" aria-label="Daily P&L"></canvas></div><div id="ov-bars-e"></div></div></div>' +
        '<div id="ov-split" class="split"></div><div id="ov-kpi" class="grid4"></div>' +
        '<div class="sec"><div id="ov-h3"></div><div id="ov-risk" class="card"></div></div>' +
        '<div class="sec"><div id="ov-h4"></div><div id="ov-perf" class="card"></div></div>' +
        '<div class="sec"><div id="ov-h5"></div><div id="ov-mkt" class="card"></div></div>' +
        '<div class="sec"><div id="ov-h6"></div><div class="card"><div id="ov-chh"></div><div class="cvwrap tall"><canvas id="cv-ch" class="cv" role="img" aria-label="Price chart"></canvas></div></div></div>' +
        '<div id="ov-mov-s"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), v = b.getAttribute("data-v");
        if (a === "eqr") { Q.S.eqr = v; V.overview.update(); }
        if (a === "sym") { Q.S.sym = v; Q._last.kl = 0; V.overview.reloadChart(); }
        if (a === "tf") { Q.S.tf = v; Q._last.kl = 0; V.overview.reloadChart(); }
      };
    },
    reloadChart: async function () { await V.overview.loadChart(); V.overview.update(); },
    loadChart: async function () {
      try { Q.S.kl = await Q.api("/api/market_klines?symbol=" + encodeURIComponent(Q.S.sym) + "&interval=" + Q.S.tf); }
      catch (e) { Q.S.kl = []; }
    },
    load: async function () {
      await Q.every("eq", 30000, async function () { Q.S.eq = await Q.api("/api/pro/equity"); });
      await Q.every("tk", 30000, async function () { Q.S.tk = await Q.api("/api/live_tickers"); });
      await Q.every("hist", 20000, async function () { Q.S.hist = await Q.api("/api/pro/history"); });
      await Q.every("kl", 15000, V.overview.loadChart);
    },
    eqPoints: function () {
      var pts = Q.S.eq || [], sec = RANGES[Q.S.eqr];
      if (!sec || !pts.length) return pts;
      var from = pts[pts.length - 1].t - sec;
      var f = pts.filter(function (p) { return p.t >= from; });
      return f.length >= 2 ? f : pts.slice(-2);
    },
    update: function () {
      var ov = Q.S.ov;
      if (!ov) { Q.paint("ov-h1", Q.wait()); return; }
      var p = ov.portfolio, r = ov.risk, perf = ov.perf, eq = p.equity, base = ov.initial || 0, st = ov.status || {};
      var chg = eq - base, chgPct = base ? (chg / base) * 100 : 0;
      var dayBase = eq - r.daily_change, dayPct = dayBase ? (r.daily_change / dayBase) * 100 : 0;

      Q.paint("ov-qa",
        '<button class="qb pri" data-act="pause">' + Q.icon(st.paused ? "play" : "pause") + (st.paused ? Q.t("resume") : Q.t("pause")) + "</button>" +
        [["markets", "nav_markets"], ["signals", "nav_signals"], ["positions", "nav_positions"], ["analytics", "sub_analytics"]].map(function (x) {
          return '<button class="qb" data-go="' + x[0] + '">' + Q.icon(x[0]) + Q.t(x[1]) + "</button>";
        }).join(""));

      Q.paint("ov-h1", Q.head("chart", Q.t("portfolio_perf"), "analytics"));
      Q.paint("ov-hero",
        '<div class="row2"><div class="lbl">' + Q.t("equity") + '</div>' + Q.ecg() + '<span class="tag paper">' + Q.t("paper") + "</span></div>" +
        '<div class="big num ' + (chg >= 0 ? "glow-up" : "glow-down") + '">' + Q.cnt(eq, { pre: "$", key: "eq", intro: true }) + '</div><div class="chg num ' + Q.cls(chg) + '">' + (chg >= 0 ? "&#9650; " : "&#9660; ") + Q.cnt(chg, { sign: true, key: "chg" }) + " (" + Q.cnt(chgPct, { sign: true, suf: "%", key: "chgp" }) + ') <span class="mu">' + Q.t("since_start") + "</span></div>");
      Q.paint("ov-rng", '<div class="chips">' + ["6h", "1d", "7d", "all"].map(function (k) {
        return '<button class="chip' + (Q.S.eqr === k ? " on" : "") + '" data-act="eqr" data-v="' + k + '">' + Q.t("r" + k) + "</button>";
      }).join("") + "</div>");
      C.area(Q.$("cv-eq"), V.overview.eqPoints(), { base: base, empty: Q.t("no_data") });
      Q.paint("ov-sub",
        '<div class="kv"><div><span>' + Q.t("today") + '</span><b class="num ' + Q.cls(r.daily_change) + '">' + Q.cnt(r.daily_change, { sign: true, key: "day" }) + " (" + Q.cnt(dayPct, { sign: true, suf: "%", key: "dayp" }) + ')</b></div>' +
        "<div><span>" + Q.t("total") + '</span><b class="num ' + Q.cls(chg) + '">' + Q.cnt(chg, { sign: true, key: "tot" }) + " (" + Q.cnt(chgPct, { sign: true, suf: "%", key: "totp" }) + ")</b></div></div>");

      /* daily P&L bars */
      var days = Q.dailyPnl(7), any = days.some(function (d) { return d.has; });
      Q.paint("ov-h2", Q.head("analytics", Q.t("daily_pnl_t"), "analytics"));
      var bw = Q.$("ov-bars-w");
      if (bw) bw.style.display = any ? "block" : "none";
      Q.paint("ov-bars-e", any ? "" : (Q.S.hist == null ? '<div class="sk" style="width:60%"></div>' : Q.empty("analytics", Q.t("no_trades"))));
      if (any) C.bars(Q.$("cv-bars"), days, { fmt: function (v) { return Q.sg(v, Math.abs(v) >= 100 ? 0 : 2); }, empty: Q.t("no_data") });

      /* allocation gauge + win-rate + risk-heat tiles (reference: asset allocation / goal / risk) */
      var cap = r.risk_cap || 0, heat = cap ? (r.open_risk / cap) * 100 : 0;
      var cashPct = eq > 0 ? Math.max(0, Math.min(100, p.cash_balance / eq * 100)) : 0, invPct = eq > 0 ? Math.max(0, Math.min(100, 100 - cashPct)) : 0;
      Q.paint("ov-split",
        '<div class="tile"><div class="lbl">' + Q.t("allocation") + "</div>" + C.arcs([{ pct: cashPct, color: "#ffffff" }, { pct: invPct, color: "#d6ff1f" }], Q.t("allocation")) +
        '<div class="legend"><span><i style="background:#fff"></i>' + Q.t("cash") + '</span><span><i style="background:#d6ff1f"></i>' + Q.t("invested") + "</span></div></div>" +
        '<div class="stack">' +
        tile(Q.t("win_rate"), perf.total_trades ? perf.win_rate.toFixed(0) + "%" : "-", perf.total_trades ? "up" : "mu", perf.total_trades ? "W " + perf.wins + " / L " + perf.losses : Q.t("no_trades")) +
        tile(Q.t("risk_heat"), heat.toFixed(0) + "%", heat > 75 ? "down" : heat > 40 ? "wa" : "up", (heat > 75 ? Q.t("high") : heat > 40 ? Q.t("moderate") : Q.t("low")) + " &middot; $" + Q.n(r.open_risk, 0) + " / $" + Q.n(cap, 0)) +
        "</div>");

      Q.paint("ov-kpi",
        tile(Q.t("available"), Q.cnt(p.cash_balance, { pre: "$", key: "cash" }), "", Q.t("virtual")) +
        tile(Q.t("unrealized"), Q.cnt(p.unrealized_pnl, { sign: true, key: "unr" }), Q.cls(p.unrealized_pnl), "$" + Q.n(p.open_margin) + " " + Q.t("in_trades")) +
        tile(Q.t("realized"), Q.cnt(p.realized_pnl, { sign: true, key: "rea" }), Q.cls(p.realized_pnl), perf.total_trades + " " + Q.t("trades")) +
        tile(Q.t("today"), Q.cnt(r.daily_change, { sign: true, key: "day2" }), Q.cls(r.daily_change), Q.sg(dayPct) + "%"));

      /* risk controls */
      var lim = r.daily_loss_limit || 0, used = lim && r.daily_change < 0 ? (-r.daily_change / lim) * 100 : 0;
      var all = Q.S.eq || [], peak = 0, maxdd = 0, i;
      for (i = 0; i < all.length; i++) { peak = Math.max(peak, all[i].v); if (peak) maxdd = Math.max(maxdd, ((peak - all[i].v) / peak) * 100); }
      var dd = peak ? Math.max(0, ((peak - eq) / peak) * 100) : 0;
      Q.paint("ov-h3", Q.head("shield", Q.t("risk_ctl"), "health"));
      Q.paint("ov-risk",
        meter(Q.t("open_risk"), Q.n(r.open_risk) + " / " + Q.n(cap), heat, heat > 85 ? COL.dn : heat > 60 ? COL.wa : COL.lime) +
        meter(Q.t("daily_pnl") + " " + Q.sg(r.daily_change), Q.t("daily_limit") + " " + Q.n(lim) + " (" + used.toFixed(0) + "% " + Q.t("used") + ")", used, used >= 100 ? COL.dn : used > 60 ? COL.wa : COL.lime) +
        meter(Q.t("drawdown") + " " + dd.toFixed(2) + "%", Q.t("max_dd") + " " + maxdd.toFixed(2) + "%", Math.min(100, (dd / 15) * 100), dd > 10 ? COL.dn : dd > 5 ? COL.wa : "#ffffff") +
        (r.daily_limit_hit ? '<div class="alert">' + Q.t("limit_hit") + "</div>" : ""));

      /* performance */
      var pf = perf.profit_factor, pfTxt = pf == null ? "INF" : Q.n(pf), pfPct = pf == null ? 100 : Math.min(100, (pf / 3) * 100);
      var aw = perf.wins ? perf.gross_profit / perf.wins : 0, al = perf.losses ? perf.gross_loss / perf.losses : 0;
      Q.paint("ov-h4", Q.head("analytics", Q.t("performance"), "analytics"));
      Q.paint("ov-perf",
        '<div class="rings"><div>' + C.ring(perf.win_rate, COL.lime, perf.win_rate.toFixed(0) + "%", "W " + perf.wins + " / L " + perf.losses) + '<div class="lbl" style="text-align:center">' + Q.t("win_rate") +
        "</div></div><div>" + C.ring(pfPct, "#ffffff", pfTxt, "GP " + Q.n(perf.gross_profit, 1) + " / GL " + Q.n(perf.gross_loss, 1)) + '<div class="lbl" style="text-align:center">' + Q.t("profit_factor") + "</div></div></div>" +
        '<div class="kv"><div><span>' + Q.t("trades") + '</span><b class="num">' + perf.total_trades + "</b></div><div><span>" + Q.t("net") + '</span><b class="num ' + Q.cls(perf.net_pnl) + '">' + Q.sg(perf.net_pnl) +
        "</b></div><div><span>" + Q.t("expectancy") + '</span><b class="num ' + Q.cls(perf.net_pnl) + '">' + Q.sg(perf.total_trades ? perf.net_pnl / perf.total_trades : 0) + "</b></div><div><span>" + Q.t("payoff") +
        '</span><b class="num">' + (al ? Q.n(aw / al) : "-") + "</b></div><div><span>" + Q.t("avg_win") + '</span><b class="num up">' + Q.n(aw) + "</b></div><div><span>" + Q.t("avg_loss") + '</span><b class="num down">-' + Q.n(al) + "</b></div></div>");

      /* market pulse */
      var comp = st.compass || {}, br = ov.breadth;
      Q.paint("ov-h5", Q.head("markets", Q.t("market"), "markets"));
      Q.paint("ov-mkt",
        '<div class="h"><span class="lbl">' + Q.t("last_scan") + '</span><span class="mu num">' + (st.last_scan ? Q.dur(ov.now - st.last_scan) + " " + Q.t("ago") : "-") + "</span></div>" +
        '<div class="chips">' + ["spot", "futures"].map(function (s) {
          var c = comp[s] || "NEUTRAL", k = c === "BULLISH" ? "up" : c === "BEARISH" ? "down" : "flat";
          return '<span class="chip ' + k + '">' + s + " &middot; " + Q.t(c.toLowerCase()) + "</span>";
        }).join("") + "</div>" + (br == null ? "" : meter(Q.t("breadth"), Q.n(br, 0) + "%", br, br > 60 ? COL.lime : br < 40 ? COL.dn : COL.wa)));

      /* price chart */
      var syms = ["BTCUSDT", "ETHUSDT"];
      (ov.positions || []).forEach(function (x) { if (syms.indexOf(x.symbol) < 0) syms.push(x.symbol); });
      Q.paint("ov-h6", Q.head("chart", Q.t("chart") + " \u00b7 " + Q.S.sym.replace("USDT", ""), "markets"));
      Q.paint("ov-chh",
        '<div class="chips" style="margin-bottom:8px">' + ["15m", "1h", "4h"].map(function (k) {
          return '<button class="chip' + (Q.S.tf === k ? " on" : "") + '" data-act="tf" data-v="' + k + '">' + k + "</button>";
        }).join("") + '</div><div class="chips" style="margin-bottom:6px">' + syms.map(function (s) {
          return '<button class="chip' + (Q.S.sym === s ? " on" : "") + '" data-act="sym" data-v="' + s + '">' + Q.esc(s.replace("USDT", "")) + "</button>";
        }).join("") + "</div>");
      var lines = [];
      (ov.positions || []).forEach(function (x) {
        if (x.symbol !== Q.S.sym) return;
        lines.push({ price: x.entry, color: "#bdbdbd", label: Q.t("entry") }, { price: x.stop, color: COL.dn, label: Q.t("stop") }, { price: x.target, color: COL.lime, label: Q.t("target") });
      });
      C.candles(Q.$("cv-ch"), Q.S.kl, lines, { empty: Q.t("no_data") });

      var tk = (Q.S.tk || []).slice().sort(function (a, b) { return b.change - a.change; });
      Q.paint("ov-mov-s", tk.length
        ? '<div class="sec">' + Q.head("scan", Q.t("movers"), "markets") + '<div class="card"><div class="grid2"><div><div class="lbl">' + Q.t("gainers") + "</div>" + movers(tk.slice(0, 4)) +
          '</div><div><div class="lbl">' + Q.t("losers") + "</div>" + movers(tk.slice(-4).reverse()) + "</div></div></div></div>" : "");
    }
  };
  (window.__mods = window.__mods || []).push("overview");
})();
