"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;

  function rbar(p) {
    var vals = [p.stop, p.target, p.entry, p.price], lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), sp = hi - lo || 1;
    function at(v) { return Math.max(0, Math.min(100, ((v - lo) / sp) * 100)); }
    var a = at(p.stop), e = at(p.entry), t = at(p.target);
    return '<div class="rbar" role="img" aria-label="stop / entry / target"><div class="z1" style="left:' + Math.min(a, e) + "%;width:" + Math.abs(e - a) + '%"></div><div class="z2" style="left:' + Math.min(e, t) + "%;width:" + Math.abs(e - t) +
      '%"></div><i class="mk" style="left:' + e + '%"></i><i class="mk now" style="left:' + at(p.price) + '%"></i></div>';
  }
  function kv(k, v, cls) { return "<div><span>" + k + '</span><b class="num ' + (cls || "") + '">' + v + "</b></div>"; }
  function when(ts) { return ts ? new Date(ts * 1000).toLocaleString(Q.S.lang === "ar" ? "ar" : "en-GB", { dateStyle: "medium", timeStyle: "short" }) : "-"; }

  V.positions = {
    mount: function (root) {
      root.innerHTML = '<div class="sec"><div id="po-h"></div><div id="po-sum" class="card"></div></div><div id="po-list"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), id = b.getAttribute("data-id");
        if (a === "ptx") { Q.S.open["pos:" + id] = !Q.S.open["pos:" + id]; V.positions.update(); }
        if (a !== "close") return;
        Q.sheet(Q.t("close"), Q.t("close_q"), [{ label: Q.t("cancel") }, { label: Q.t("confirm"), kind: "dng", fn: function () { V.positions.close(id); } }]);
      };
    },
    close: async function (id) {
      try { await Q.api("/api/close_position/" + encodeURIComponent(id), { method: "POST" }); Q.toast(Q.t("closed_ok")); await Q.refresh(); }
      catch (e) { Q.toast(e.message, "err"); }
    },
    update: function () {
      var ov = Q.S.ov;
      if (!ov) { Q.paint("po-list", Q.wait()); return; }
      var list = ov.positions || [], eq = ov.portfolio.equity || 0, tot = 0, risk = 0, margin = 0;
      list.forEach(function (p) { tot += p.pnl; risk += p.risk; margin += p.margin; });
      Q.paint("po-h", Q.head("positions", Q.t("open_positions"), null));
      Q.paint("po-sum",
        '<div class="grid2"><div><div class="lbl">' + Q.t("open_pnl") + '</div><div class="big num ' + Q.cls(tot) + '" style="font-size:28px">' + Q.cnt(tot, { sign: true, key: "opnl" }) + "</div></div><div><div class=\"lbl\">" + Q.t("open_count") + '</div><div class="big num" style="font-size:28px">' + list.length + "</div></div></div>" +
        '<div class="kv">' + kv(Q.t("risk_exposure"), "$" + Q.n(risk) + (eq ? " (" + Q.n(risk / eq * 100, 1) + "%)" : "")) + kv(Q.t("in_trades"), "$" + Q.n(margin)) + "</div>");
      Q.paint("po-list", list.length ? list.map(function (p) {
        var sym = Q.esc(p.symbol.replace("USDT", "")), open = !!Q.S.open["pos:" + p.id], id = Q.esc(p.id);
        return '<div class="card pt' + (open ? " open" : "") + '"><button class="pt-top" data-act="ptx" data-id="' + id + '" aria-expanded="' + open + '"><div class="pos-h"><b>' + sym + '</b><span class="tag ' + p.side.toLowerCase() + '">' + Q.t(p.side.toLowerCase()) +
          '</span><span class="tag src">' + Q.esc(p.source) + '</span><span style="flex:1"></span><span class="mu num">' + Q.dur((ov.now || 0) - p.opened) + '</span><span class="chev">' + Q.icon("chev") + '</span></div><div class="pos-pnl num ' + Q.cls(p.pnl) + '">' + Q.cnt(p.pnl, { sign: true, key: "pp" + p.id }) +
          " <small>" + Q.sg(p.pnl_pct, 1) + "% &middot; " + Q.sg(p.r, 2) + "R</small></div></button>" + rbar(p) +
          '<div class="kv">' + kv(Q.t("entry"), Q.price(p.entry)) + kv(Q.t("now"), Q.cnt(p.price, { dec: Q.priceDec(p.price), key: "pn" + p.id, flash: false }), Q.cls(p.pnl)) + kv(Q.t("stop"), Q.price(p.stop), "down") + kv(Q.t("target"), Q.price(p.target), "up") +
          kv(Q.t("size"), "$" + Q.n(p.margin)) + kv(Q.t("risk"), "$" + Q.n(p.risk) + (eq ? " (" + Q.n(p.risk / eq * 100, 2) + "%)" : "")) + "</div>" +
          '<div class="more"><div class="kv">' + kv(Q.t("qty"), Q.n(p.qty, 4)) + kv(Q.t("leverage"), Q.n(p.leverage, 1) + "x") + kv(Q.t("strategy"), Q.esc(p.strategy || "-")) + kv(Q.t("score"), p.score == null ? "-" : Q.n(p.score, 0)) +
          kv(Q.t("regime"), Q.esc(p.regime || "-")) + kv(Q.t("funding"), Q.sg(-p.funding)) + kv(Q.t("partial"), p.scaled_out ? Q.sg(p.realized_partial) : "-") + kv(Q.t("liq"), p.liquidation ? Q.price(p.liquidation) : "-") + "</div></div>" +
          '<button class="btn dng blk" data-act="close" data-id="' + id + '">' + Q.t("close") + "</button></div>";
      }).join("") : '<div class="card">' + Q.empty("positions", Q.t("no_positions")) + "</div>");
    }
  };

  V.history = {
    mount: function (root) {
      root.innerHTML = '<div class="sec"><div id="hi-h"></div><div id="hi-sum" class="card"></div></div><div class="sec"><div id="hi-h2"></div><div id="hi-str" class="card"></div></div><div class="sec"><div id="hi-h3"></div><div id="hi-ex" class="card"></div></div>' +
        '<div class="sec"><div id="hi-h4"></div><div class="card"><div id="hi-fl"></div><div class="field"><input id="hi-q" type="search" autocomplete="off" aria-label="' + Q.esc(Q.t("search")) + '" placeholder="' + Q.esc(Q.t("search_trades")) + '" value="' + Q.esc(Q.S.hq) + '"></div><div id="hi-list" class="list"></div></div></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act");
        if (a === "hf") { Q.S.hf = b.getAttribute("data-v"); V.history.update(); }
        if (a === "htx") { var k = "tr:" + b.getAttribute("data-id"); Q.S.open[k] = !Q.S.open[k]; V.history.paintList(); }
      };
      root.oninput = function (e) { if (e.target && e.target.id === "hi-q") { Q.S.hq = e.target.value || ""; V.history.paintList(); } };
    },
    load: async function () { await Q.every("hist", 20000, async function () { Q.S.hist = await Q.api("/api/pro/history"); }); },
    update: function () {
      var h = Q.S.hist;
      if (!h) { Q.paint("hi-sum", Q.wait()); return; }
      Q.paint("hi-h", Q.head("history", Q.t("cum"), "analytics"));
      if (!h.length) { Q.paint("hi-sum", Q.empty("history", Q.t("no_trades"))); Q.paint("hi-str", ""); Q.paint("hi-ex", ""); Q.paint("hi-fl", ""); Q.paint("hi-list", ""); return; }
      var chron = h.slice().reverse(), cum = [0], run = 0, wins = 0, best = h[0], worst = h[0], fees = 0;
      chron.forEach(function (t) { run += t.pnl; cum.push(run); });
      h.forEach(function (t) { if (t.pnl > 0) wins++; if (t.pnl > best.pnl) best = t; if (t.pnl < worst.pnl) worst = t; fees += t.fees || 0; });
      Q.paint("hi-sum", '<div class="h"><span class="lbl">' + Q.t("net") + '</span><b class="num ' + Q.cls(run) + '">' + Q.sg(run) + "</b></div>" + C.spark(cum, run >= 0 ? COL.lime : COL.dn, 300, 60) +
        '<div class="kv">' + kv(Q.t("trades"), h.length) + kv(Q.t("win_rate"), (wins / h.length * 100).toFixed(0) + "%") + kv(Q.t("best"), Q.sg(best.pnl), "up") + kv(Q.t("worst"), Q.sg(worst.pnl), "down") + kv(Q.t("fees"), "-" + Q.n(fees)) + "</div>");
      var dots = h.slice(0, 30).reverse().map(function (t) { return '<i class="' + (t.pnl > 0 ? "w" : "l") + '"></i>'; }).join(""), by = {}, mx = 0, k;
      h.forEach(function (t) { var s = by[t.strategy] = by[t.strategy] || { n: 0, w: 0, net: 0 }; s.n++; s.net += t.pnl; if (t.pnl > 0) s.w++; });
      for (k in by) mx = Math.max(mx, Math.abs(by[k].net));
      Q.paint("hi-h2", Q.head("analytics", Q.t("by_strategy"), null));
      Q.paint("hi-str", '<div class="lbl" style="margin-bottom:8px">' + Q.t("recent") + '</div><div class="dots">' + dots + "</div><div style=\"height:12px\"></div>" + Object.keys(by).map(function (s) {
        var x = by[s];
        return '<div class="brow"><span class="n">' + Q.esc(s) + "</span>" + C.bar(mx ? Math.abs(x.net) / mx * 100 : 0, x.net >= 0 ? COL.lime : COL.dn) + '<span class="c num ' + Q.cls(x.net) + '">' + Q.sg(x.net, 1) + " (" + x.n + ")</span></div>";
      }).join(""));
      var ex = {};
      h.forEach(function (t) { ex[t.reason || "-"] = (ex[t.reason || "-"] || 0) + 1; });
      var names = Object.keys(ex).sort(function (a, b) { return ex[b] - ex[a]; });
      Q.paint("hi-h3", Q.head("shield", Q.t("exits"), null));
      Q.paint("hi-ex", names.map(function (n) { return '<div class="brow"><span class="n">' + Q.esc(n) + "</span>" + C.bar(ex[n] / h.length * 100, "#ffffff") + '<span class="c num">' + ex[n] + "</span></div>"; }).join(""));
      Q.paint("hi-h4", Q.head("history", Q.t("trade_history"), null));
      Q.paint("hi-fl", '<div class="chips" style="margin-bottom:6px">' + [["all", "f_all"], ["wins", "f_wins"], ["losses", "f_losses"], ["long", "long"], ["short", "short"]].map(function (f) {
        return '<button class="chip' + (Q.S.hf === f[0] ? " on" : "") + '" data-act="hf" data-v="' + f[0] + '">' + Q.t(f[1]) + "</button>";
      }).join("") + "</div>");
      V.history.paintList();
    },
    paintList: function () {
      var h = Q.S.hist || [], q = Q.S.hq.trim().toUpperCase(), f = Q.S.hf;
      var rows = h.filter(function (t) {
        if (f === "wins" && !(t.pnl > 0)) return false;
        if (f === "losses" && !(t.pnl <= 0)) return false;
        if ((f === "long" || f === "short") && t.side.toLowerCase() !== f) return false;
        return !q || (t.symbol + " " + t.strategy + " " + t.reason).toUpperCase().indexOf(q) >= 0;
      }).slice(0, 60);
      Q.paint("hi-list", rows.length ? rows.map(function (t) {
        var key = "tr:" + t.id, open = !!Q.S.open[key];
        return '<div class="sg' + (open ? " open" : "") + '"><button class="sg-top" data-act="htx" data-id="' + Q.esc(t.id) + '" aria-expanded="' + open + '"><span class="m" style="flex:1;min-width:0"><b>' + Q.esc(t.symbol.replace("USDT", "")) + ' <span class="tag ' + t.side.toLowerCase() + '">' + Q.t(t.side.toLowerCase()) +
          '</span></b><small class="mu" style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + Q.esc(t.strategy) + " &middot; " + Q.esc(t.reason) + " &middot; " + Q.ago(t.closed) + '</small></span><span class="e num ' + Q.cls(t.pnl) + '" style="text-align:end"><b>' + Q.sg(t.pnl) +
          '</b><small style="display:block">' + Q.sg(t.r, 2) + 'R</small></span><span class="chev">' + Q.icon("chev") + '</span></button><div class="sg-d"><div class="kv" style="margin:0">' +
          kv(Q.t("entry"), Q.price(t.entry)) + kv(Q.t("exit"), Q.price(t.exit)) + kv(Q.t("gross"), Q.sg(t.gross), Q.cls(t.gross)) + kv(Q.t("fees"), "-" + Q.n(t.fees)) + kv(Q.t("funding"), Q.sg(-t.funding)) + kv(Q.t("net"), Q.sg(t.pnl), Q.cls(t.pnl)) +
          kv(Q.t("duration"), Q.dur(t.closed - t.opened)) + kv(Q.t("closed_at"), when(t.closed)) + "</div></div></div>";
      }).join("") : Q.empty("search", Q.t("no_match")));
    }
  };
  (window.__mods = window.__mods || []).push("trades");
})();
