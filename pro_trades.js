"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;

  function rbar(p) {
    var vals = [p.stop, p.target, p.entry, p.price], lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), sp = hi - lo || 1;
    function at(v) { return Math.max(0, Math.min(100, ((v - lo) / sp) * 100)); }
    var a = at(p.stop), e = at(p.entry), t = at(p.target);
    return '<div class="rbar"><div class="z1" style="left:' + Math.min(a, e) + "%;width:" + Math.abs(e - a) + '%"></div><div class="z2" style="left:' +
      Math.min(e, t) + "%;width:" + Math.abs(e - t) + '%"></div><i class="mk" style="left:' + e + '%"></i><i class="mk now" style="left:' + at(p.price) + '%"></i></div>';
  }
  function kv(k, v, cls) { return "<div><span>" + k + '</span><b class="num ' + (cls || "") + '">' + v + "</b></div>"; }

  V.positions = {
    mount: function (root) {
      root.innerHTML = '<div id="po-sum" class="card"></div><div id="po-list"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b || b.getAttribute("data-act") !== "close") return;
        var id = b.getAttribute("data-id");
        Q.sheet(Q.t("close"), Q.t("close_q"), [{ label: Q.t("cancel") }, { label: Q.t("confirm"), kind: "dng", fn: function () { V.positions.close(id); } }]);
      };
    },
    close: async function (id) {
      try { await Q.api("/api/close_position/" + encodeURIComponent(id), { method: "POST" }); Q.toast(Q.t("closed_ok")); await Q.refresh(); }
      catch (e) { Q.toast(e.message, "err"); }
    },
    update: function () {
      var ov = Q.S.ov;
      if (!ov) return;
      var list = ov.positions || [], tot = 0, risk = 0;
      list.forEach(function (p) { tot += p.pnl; risk += p.risk; });
      Q.paint("po-sum", '<div class="grid2"><div><div class="lbl">' + Q.t("open_pnl") + '</div><div class="big num ' + Q.cls(tot) + '" style="font-size:26px">' + Q.sg(tot) +
        '</div></div><div><div class="lbl">' + Q.t("open_count") + " / " + Q.t("open_risk") + '</div><div class="big num" style="font-size:26px">' + list.length + ' <span class="mu" style="font-size:15px">$' + Q.n(risk) + "</span></div></div></div>");
      Q.paint("po-list", list.length ? list.map(function (p) {
        var sym = Q.esc(p.symbol.replace("USDT", ""));
        return '<div class="card"><div class="pos-h"><b>' + sym + '</b><span class="tag ' + p.side.toLowerCase() + '">' + Q.t(p.side.toLowerCase()) + '</span><span class="tag src">' + p.source +
          '</span><span class="sp"></span><span class="mu num">' + Q.dur((ov.now || 0) - p.opened) + '</span></div><div class="pos-pnl num ' + Q.cls(p.pnl) + '">' + Q.sg(p.pnl) +
          ' <small>' + Q.sg(p.pnl_pct, 1) + "% &middot; " + Q.sg(p.r, 2) + "R</small></div>" + rbar(p) + '<div class="kv">' +
          kv(Q.t("entry"), Q.price(p.entry)) + kv(Q.t("now"), Q.price(p.price), Q.cls(p.pnl)) + kv(Q.t("stop"), Q.price(p.stop), "down") + kv(Q.t("target"), Q.price(p.target), "up") +
          kv(Q.t("size"), "$" + Q.n(p.margin)) + kv(Q.t("risk"), "$" + Q.n(p.risk)) + "</div>" +
          '<button class="btn dng blk" data-act="close" data-id="' + p.id + '">' + Q.t("close") + "</button></div>";
      }).join("") : '<div class="card empty">' + Q.t("no_positions") + "</div>");
    }
  };

  V.history = {
    mount: function (root) {
      root.innerHTML = '<div id="hi-sum" class="card"></div><div id="hi-str" class="card"></div><div id="hi-ex" class="card"></div><div class="card"><div id="hi-fl"></div><div id="hi-list" class="list"></div></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (b && b.getAttribute("data-act") === "hf") { Q.S.hf = b.getAttribute("data-v"); V.history.update(); }
      };
    },
    load: async function () { await Q.every("hist", 20000, async function () { Q.S.hist = await Q.api("/api/pro/history"); }); },
    update: function () {
      var h = Q.S.hist;
      if (!h) return;
      if (!h.length) { Q.paint("hi-sum", '<div class="empty">' + Q.t("no_trades") + "</div>"); return; }
      var chron = h.slice().reverse(), cum = [0], run = 0, wins = 0, best = h[0], worst = h[0];
      chron.forEach(function (t) { run += t.pnl; cum.push(run); });
      h.forEach(function (t) { if (t.pnl > 0) wins++; if (t.pnl > best.pnl) best = t; if (t.pnl < worst.pnl) worst = t; });
      Q.paint("hi-sum", '<div class="h"><h3>' + Q.t("cum") + '</h3><b class="num ' + Q.cls(run) + '">' + Q.sg(run) + "</b></div>" + C.spark(cum, run >= 0 ? COL.up : COL.dn, 300, 60) +
        '<div class="kv">' + kv(Q.t("trades"), h.length) + kv(Q.t("win_rate"), (wins / h.length * 100).toFixed(0) + "%") +
        kv(Q.t("best"), Q.sg(best.pnl), "up") + kv(Q.t("worst"), Q.sg(worst.pnl), "down") + "</div>");

      var dots = h.slice(0, 30).reverse().map(function (t) { return '<i class="' + (t.pnl > 0 ? "w" : "l") + '"></i>'; }).join("");
      var by = {};
      h.forEach(function (t) { var s = by[t.strategy] = by[t.strategy] || { n: 0, w: 0, net: 0 }; s.n++; s.net += t.pnl; if (t.pnl > 0) s.w++; });
      var mx = 0, k;
      for (k in by) mx = Math.max(mx, Math.abs(by[k].net));
      Q.paint("hi-str", '<div class="h"><h3>' + Q.t("recent") + '</h3></div><div class="dots">' + dots + '</div><div class="h" style="margin-top:14px"><h3>' + Q.t("by_strategy") + "</h3></div>" +
        Object.keys(by).map(function (s) {
          var x = by[s];
          return '<div class="brow"><span class="n">' + Q.esc(s) + "</span>" + C.bar(mx ? Math.abs(x.net) / mx * 100 : 0, x.net >= 0 ? COL.up : COL.dn) + '<span class="c num ' + Q.cls(x.net) + '">' + Q.sg(x.net, 1) + " (" + x.n + ")</span></div>";
        }).join(""));

      var ex = {};
      h.forEach(function (t) { ex[t.reason || "-"] = (ex[t.reason || "-"] || 0) + 1; });
      var names = Object.keys(ex).sort(function (a, b) { return ex[b] - ex[a]; });
      Q.paint("hi-ex", '<div class="h"><h3>' + Q.t("exits") + "</h3></div>" + names.map(function (n) {
        return '<div class="brow"><span class="n">' + Q.esc(n) + "</span>" + C.bar(ex[n] / h.length * 100, COL.cy) + '<span class="c num">' + ex[n] + "</span></div>";
      }).join(""));

      Q.paint("hi-fl", '<div class="chips" style="margin-bottom:6px">' + [["all", "f_all"], ["wins", "f_wins"], ["losses", "f_losses"]].map(function (f) {
        return '<button class="chip' + (Q.S.hf === f[0] ? " on" : "") + '" data-act="hf" data-v="' + f[0] + '">' + Q.t(f[1]) + "</button>";
      }).join("") + "</div>");
      var rows = h.filter(function (t) { return Q.S.hf === "all" || (Q.S.hf === "wins" ? t.pnl > 0 : t.pnl <= 0); }).slice(0, 60);
      Q.paint("hi-list", rows.map(function (t) {
        return '<div class="it"><div class="m"><b>' + Q.esc(t.symbol.replace("USDT", "")) + ' <span class="tag ' + t.side.toLowerCase() + '">' + Q.t(t.side.toLowerCase()) + "</span></b><small>" +
          Q.esc(t.strategy) + " &middot; " + Q.esc(t.reason) + " &middot; " + Q.ago(t.closed) + '</small></div><div class="e num ' + Q.cls(t.pnl) + '"><b>' + Q.sg(t.pnl) + "</b><small>" + Q.sg(t.r, 2) + "R</small></div></div>";
      }).join(""));
    }
  };
  (window.__mods = window.__mods || []).push("trades");
})();
