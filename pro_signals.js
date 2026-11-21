"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;
  var NODATA = /unavailable|insufficient|stale|missing|no data|not enough|failed|timeout|incomplete/i;
  var SEGS = [["all", "sg_all"], ["signals", "sg_signals"], ["model", "sg_model"], ["alerts", "sg_alerts"]];

  function kind(d) {
    if (d.action === "HOLD") return NODATA.test(d.reason || "") ? "nodata" : "hold";
    return /SELL|SHORT/.test(d.action) ? "sell" : "buy";
  }
  function blockers(list) {
    var count = {};
    list.forEach(function (d) {
      if (d.action !== "HOLD") return;
      var txt = String(d.reason || "").replace(/^\[[^\]]*\]\s*/, "").replace(/^Blocked:\s*/i, "");
      txt.split(/ \| |; /).forEach(function (part) {
        var k = part.replace(/\([^)]*\)/g, "").replace(/\d+(\.\d+)?/g, "#").replace(/\s+/g, " ").trim();
        if (k) count[k] = (count[k] || 0) + 1;
      });
    });
    return Object.keys(count).map(function (k) { return [k, count[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 6);
  }
  function match(d) {                                     // link a decision to the position it opened (same symbol/source, opened within 3 min)
    var i, p, t, pos = (Q.S.ov && Q.S.ov.positions) || [], hist = Q.S.hist || [];
    for (i = 0; i < pos.length; i++) { p = pos[i]; if (p.symbol === d.symbol && p.source === d.source && Math.abs(p.opened - d.t) <= 180) return { open: p }; }
    for (i = 0; i < hist.length; i++) { t = hist[i]; if (t.symbol === d.symbol && t.source === d.source && Math.abs(t.opened - d.t) <= 180) return { closed: t }; }
    return {};
  }
  function kvr(k, v, cls) { return "<div><span>" + k + '</span><b class="num ' + (cls || "") + '">' + v + "</b></div>"; }
  function card(d) {
    var k = kind(d), m = match(d), key = "sg:" + d.t + d.symbol, open = !!Q.S.open[key], sym = Q.esc(d.symbol.replace("USDT", "")), p = m.open, c = m.closed;
    var status = p ? '<span class="tag long">' + Q.t("st_open") + "</span>" : c ? '<span class="tag ' + (c.pnl >= 0 ? "long" : "short") + '">' + Q.t("st_closed") + "</span>" : '<span class="tag hold">' + Q.t("st_nopos") + "</span>";
    var levels = "";
    if (p) {
      var risk = p.initial_stop ? Math.abs(p.entry - p.initial_stop) : 0, rr = risk ? Math.abs(p.target - p.entry) / risk : null;
      levels = '<div class="kv">' + kvr(Q.t("entry"), Q.price(p.entry)) + kvr(Q.t("now"), Q.price(p.price), Q.cls(p.pnl)) + kvr(Q.t("stop"), Q.price(p.stop), "down") + kvr(Q.t("target"), Q.price(p.target), "up") +
        kvr(Q.t("rr"), rr == null ? Q.t("na") : "1 : " + rr.toFixed(2)) + kvr(Q.t("pnl"), Q.sg(p.pnl), Q.cls(p.pnl)) + "</div>";
    } else if (c) {
      levels = '<div class="kv">' + kvr(Q.t("entry"), Q.price(c.entry)) + kvr(Q.t("exit"), Q.price(c.exit)) + kvr(Q.t("net"), Q.sg(c.pnl), Q.cls(c.pnl)) + kvr("R", Q.sg(c.r, 2), Q.cls(c.r)) + "</div>";
    } else {
      levels = '<div class="mu" style="font-size:12px;margin-top:8px">' + Q.esc(Q.t("levels_note")) + "</div>";
    }
    return '<div class="sg' + (open ? " open" : "") + '"><button class="sg-top" data-act="sgx" data-v="' + Q.esc(key) + '" aria-expanded="' + open + '"><span class="coin ico">' + sym.slice(0, 3) + '</span><span class="m" style="flex:1;min-width:0"><b>' + sym +
      ' <span class="tag ' + k + '">' + Q.esc(d.action) + '</span></b><small class="mu">' + Q.esc(d.source) + " &middot; " + Q.ago(d.t) + " " + Q.t("ago") + '</small></span><span class="e num" style="text-align:end"><b>' + Q.n(d.score, 0) +
      '</b><small class="mu" style="display:block">' + Q.t("score") + "</small></span>" + '<span class="chev">' + Q.icon("chev") + "</span></button>" +
      '<div style="margin-top:8px">' + status + "</div>" + levels +
      '<div class="sg-d"><b>' + Q.t("why") + "</b><br>" + Q.esc(d.reason || "-") + (p ? "<br><b>" + Q.t("strategy") + ":</b> " + Q.esc(p.strategy || "-") + (p.regime ? " &middot; <b>" + Q.t("regime") + ":</b> " + Q.esc(p.regime) : "") : "") + "</div></div>";
  }
  function row(dot, title, sub, val, cls) {
    return '<div class="hl"><i class="st ' + dot + '"></i><div class="m"><b>' + title + "</b><small>" + sub + '</small></div><b class="num ' + (cls || "") + '">' + val + "</b></div>";
  }

  V.signals = {
    mount: function (root) {
      root.innerHTML =
        '<div class="seg" id="sg-seg" role="tablist"></div>' +
        '<div id="sg-p-all"></div><div id="sg-p-signals" style="display:none"><div class="sec"><div id="sg-hc"></div><div class="card" id="sg-cards"></div></div>' +
        '<div class="sec"><div id="sg-hf"></div><div class="card"><div id="sg-fl"></div><div class="field"><input id="sg-q" type="search" autocomplete="off" aria-label="' + Q.esc(Q.t("search")) + '" placeholder="' + Q.esc(Q.t("search")) + '" value="' + Q.esc(Q.S.sq) + '"></div><div id="sg-list" class="list"></div></div></div></div>' +
        '<div id="sg-p-model" style="display:none"></div><div id="sg-p-alerts" style="display:none"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), v = b.getAttribute("data-v");
        if (a === "sgseg") { Q.S.sg = v; V.signals.update(); }
        if (a === "sf") { Q.S.sf = v; V.signals.update(); }
        if (a === "sgx") { Q.S.open[v] = !Q.S.open[v]; V.signals.update(); }
      };
      root.oninput = function (e) { if (e.target && e.target.id === "sg-q") { Q.S.sq = e.target.value || ""; V.signals.paintList(); } };
    },
    load: async function () {
      await Q.every("sig", 10000, async function () { Q.S.sig = await Q.api("/api/pro/signals"); });
      await Q.every("hist", 20000, async function () { Q.S.hist = await Q.api("/api/pro/history"); });
    },
    update: function () {
      var s = Q.S.sig, ov = Q.S.ov, sys = Q.S.sys, seg = Q.S.sg;
      Q.paint("sg-seg", SEGS.map(function (x) {
        return '<button role="tab" aria-selected="' + (seg === x[0]) + '" class="' + (seg === x[0] ? "on" : "") + '" data-act="sgseg" data-v="' + x[0] + '">' + Q.t(x[1]) + "</button>";
      }).join(""));
      SEGS.forEach(function (x) { var el = Q.$("sg-p-" + x[0]); if (el) el.style.display = seg === x[0] ? "block" : "none"; });
      if (!s || !ov) { Q.paint(seg === "signals" ? "sg-cards" : "sg-p-" + seg, Q.wait()); return; }   // never overwrite the static search/filter markup
      if (seg === "all") V.signals.paintAll(s, ov, sys);
      if (seg === "signals") V.signals.paintSignals(s);
      if (seg === "model") V.signals.paintModel(ov, sys);
      if (seg === "alerts") V.signals.paintAlerts();
    },
    paintAll: function (s, ov, sys) {
      var st = ov.status || {}, ml = (sys && sys.ml) || {}, entries = s.filter(function (d) { return d.action !== "HOLD"; });
      var buy = 0, sell = 0, hold = 0, nod = 0;
      s.forEach(function (d) { var k = kind(d); if (k === "buy") buy++; else if (k === "sell") sell++; else { hold++; if (k === "nodata") nod++; } });
      var n = s.length || 1, comp = st.compass || {}, b = blockers(s), mx = b.length ? b[0][1] : 1;
      var mlState = !sys ? ["", Q.t("loading"), "..."] : !ml.present ? ["off", Q.t("ml_none"), Q.t("na")] : ml.valid ? ["on", Q.t("ml_on"), (ml.accuracy * 100).toFixed(1) + "%"] : ["off", Q.t("ml_off"), (ml.accuracy * 100).toFixed(1) + "%"];
      var html =
        '<div class="sec">' + Q.head("cpu", Q.t("ai_status"), null) + '<div class="card">' +
        row(!Q.S.online ? "bad" : st.paused ? "off" : st.running ? "on" : "bad", Q.t("analysis"), Q.esc(st.paused ? Q.t("al_paused_x") : Q.t("analysis_x")), st.paused ? Q.t("paused") : st.running ? Q.t("running") : Q.t("offline")) +
        row(mlState[0], Q.t("ml"), Q.esc(mlState[1]), mlState[2]) +
        row("", Q.t("consensus"), Q.esc(Q.t("consensus_x")), Q.t("na"), "mu") +
        row(st.data_ok === false ? "bad" : "on", Q.t("data_q"), Q.esc(st.data_ok === false ? (st.data_reason || "") : Q.t("data_ok_x")), st.data_ok === false ? Q.t("al_data") : Q.t("ok"), st.data_ok === false ? "down" : "up") +
        "</div></div>" +
        '<div class="sec">' + Q.head("signals", Q.t("decision_mix"), "signals") + '<div class="card">' +
        (s.length ? C.arcs([{ pct: buy / n * 100, color: "#d6ff1f" }, { pct: sell / n * 100, color: "#ff6b6b" }, { pct: hold / n * 100, color: "#9a9a9a" }], Q.t("decision_mix")) +
          '<div class="legend"><span><i style="background:#d6ff1f"></i>BUY ' + buy + '</span><span><i style="background:#ff6b6b"></i>SELL ' + sell + '</span><span><i style="background:#9a9a9a"></i>HOLD ' + hold + "</span></div>" +
          '<div class="kv">' + kvr(Q.t("decisions"), s.length) + kvr(Q.t("entry_rate"), (entries.length / n * 100).toFixed(1) + "%") + kvr(Q.t("hold_nodata"), nod, nod ? "wa" : "") + kvr(Q.t("hold_rules"), hold - nod) + "</div>"
          : Q.empty("signals", Q.t("no_signals"))) + "</div></div>" +
        '<div class="sec">' + Q.head("scan", Q.t("conditions"), "markets") + '<div class="card"><div class="chips">' + ["spot", "futures"].map(function (x) {
          var c = comp[x] || "", k = c === "BULLISH" ? "up" : c === "BEARISH" ? "down" : "flat";
          return '<span class="chip ' + k + '">' + x + " &middot; " + (c ? Q.t(c.toLowerCase()) : Q.t("na")) + "</span>";
        }).join("") + "</div>" + (ov.breadth == null ? "" : '<div class="meter"><div class="row"><span>' + Q.t("breadth") + '</span><span class="num mu">' + Q.n(ov.breadth, 0) + "%</span></div>" + C.bar(ov.breadth, ov.breadth > 60 ? COL.lime : ov.breadth < 40 ? COL.dn : COL.wa) + "</div>") +
        '<div class="mu" style="font-size:12px;margin:10px 0 4px">' + Q.t("top_blockers") + "</div>" +
        (b.length ? b.map(function (x) { return '<div class="brow"><span class="n" title="' + Q.esc(x[0]) + '">' + Q.esc(x[0]) + "</span>" + C.bar(x[1] / mx * 100, "#ffffff") + '<span class="c num">' + x[1] + "</span></div>"; }).join("") : '<div class="mu" style="padding:8px 0">' + Q.t("all_clear") + "</div>") +
        "</div></div>" +
        '<div class="sec">' + Q.head("signals", Q.t("latest_signals"), "signals") + '<div class="card">' + (entries.length ? entries.slice(0, 3).map(card).join("") : Q.empty("signals", Q.t("no_entries"))) + "</div></div>";
      Q.paint("sg-p-all", html);
    },
    paintSignals: function (s) {
      var entries = s.filter(function (d) { return d.action !== "HOLD"; });
      Q.paint("sg-hc", Q.head("signals", Q.t("trading_signals") + " (" + entries.length + ")", null));
      Q.paint("sg-cards", entries.length ? entries.slice(0, 30).map(card).join("") : Q.empty("signals", Q.t("no_entries")));
      Q.paint("sg-hf", Q.head("history", Q.t("feed"), null));
      Q.paint("sg-fl", '<div class="chips" style="margin-bottom:8px">' + [["all", "f_all"], ["entries", "f_entries"], ["blocked", "f_blocked"], ["nodata", "f_nodata"]].map(function (f) {
        return '<button class="chip' + (Q.S.sf === f[0] ? " on" : "") + '" data-act="sf" data-v="' + f[0] + '">' + Q.t(f[1]) + "</button>";
      }).join("") + "</div>");
      V.signals.paintList();
    },
    paintList: function () {
      var s = Q.S.sig || [], q = Q.S.sq.trim().toUpperCase();
      var rows = s.filter(function (d) {
        var k = kind(d);
        if (Q.S.sf === "entries" && d.action === "HOLD") return false;
        if (Q.S.sf === "blocked" && k !== "hold") return false;
        if (Q.S.sf === "nodata" && k !== "nodata") return false;
        return !q || String(d.symbol).toUpperCase().indexOf(q) >= 0;
      }).slice(0, 80);
      Q.paint("sg-list", rows.length ? rows.map(function (d) {
        var k = kind(d);
        return '<div class="it"><div class="m"><b>' + Q.esc(String(d.symbol).replace("USDT", "")) + ' <span class="tag ' + k + '">' + (k === "nodata" ? Q.t("nodata_tag") : Q.esc(d.action)) + '</span> <span class="tag src">' + Q.esc(d.source) +
          "</span></b><small>" + Q.esc(d.reason) + '</small></div><div class="e num mu">' + Q.n(d.score, 0) + "<small>" + Q.ago(d.t) + "</small></div></div>";
      }).join("") : Q.empty("search", Q.t("no_signals")));
    },
    paintModel: function (ov, sys) {
      if (!sys) { Q.paint("sg-p-model", Q.wait()); return; }
      var ml = sys.ml || {}, names = Object.keys(sys.strategies || {}), edge = ml.present ? (ml.accuracy - ml.baseline) * 100 : 0;
      Q.paint("sg-p-model",
        '<div class="sec">' + Q.head("cpu", Q.t("ml"), null) + '<div class="card"><div class="h"><span class="mu" style="font-size:12.5px">' + Q.esc(!ml.present ? Q.t("ml_none") : ml.valid ? Q.t("ml_on") : Q.t("ml_off")) + "</span>" +
        '<span class="sc ' + (ml.valid ? "on" : "off") + '"><i class="dot"></i>' + (ml.valid ? "ON" : "OFF") + "</span></div>" +
        (ml.present ? '<div class="kv">' + kvr(Q.t("accuracy"), (ml.accuracy * 100).toFixed(1) + "%") + kvr(Q.t("baseline"), (ml.baseline * 100).toFixed(1) + "%") + kvr(Q.t("edge"), Q.sg(edge, 1) + " pp", Q.cls(edge)) +
          kvr(Q.t("age"), ml.age_hours == null ? "-" : ml.age_hours.toFixed(1) + Q.t("hours")) + kvr(Q.t("samples"), ml.rows) + "</div>" : "") + "</div></div>" +
        '<div class="sec">' + Q.head("positions", Q.t("strategies"), null) + '<div class="card"><div class="chips">' + names.map(function (n) {
          return '<span class="chip ' + (sys.strategies[n] ? "up" : "down") + '">' + Q.esc(n) + " &middot; " + (sys.strategies[n] ? Q.t("healthy") : Q.t("paused_s")) + "</span>";
        }).join("") + "</div>" + '<div class="kv">' + kvr(Q.t("auto_active"), sys.auto && sys.auto.strategy ? Q.esc(sys.auto.strategy) + " " + Q.esc(sys.auto.rsi) + "/" + Q.esc(sys.auto.ema) : "-") + kvr(Q.t("symbols"), sys.symbols) + kvr(Q.t("scan_every"), sys.scan_every + Q.t("sec")) + "</div></div></div>");
    },
    paintAlerts: function () {
      var a = Q.alerts();
      Q.paint("sg-p-alerts", '<div class="sec">' + Q.head("bell", Q.t("notifications"), null) + '<div class="card">' + (a.length ? a.map(function (x) {
        return '<div class="al"><span class="st ' + (x.k === "bad" ? "bad" : x.k === "warn" ? "off" : "") + '" style="margin-top:5px"></span><div><b>' + Q.esc(x.t) + "</b><small>" + Q.esc(x.x) + "</small></div></div>";
      }).join("") : Q.empty("check", Q.t("all_clear_n"))) + "</div></div>");
    }
  };
  (window.__mods = window.__mods || []).push("signals");
})();
