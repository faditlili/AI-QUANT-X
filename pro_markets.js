"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;
  var FEATURED = ["BTC", "ETH", "BNB", "SOL", "XRP"];
  var SORTS = [["volume", "s_volume"], ["gain", "s_gainers"], ["loss", "s_losers"], ["name", "s_name"]];

  function ema(vals, n) {
    var k = 2 / (n + 1), e = vals[0], i;
    for (i = 1; i < vals.length; i++) e = vals[i] * k + e * (1 - k);
    return e;
  }
  function analyse(rows) {                                    // 1H trend + volatility from real candles
    if (!rows || rows.length < 30) return null;
    var closes = rows.map(function (r) { return r.close; }), last = rows.slice(-14), atr = 0;
    last.forEach(function (r) { atr += (r.high - r.low) / (r.close || 1) * 100; });
    var f = ema(closes, 9), s = ema(closes, 21);
    return { sp: closes.slice(-48), trend: f > s * 1.001 ? "up" : f < s * 0.999 ? "down" : "side", atr: atr / last.length };
  }
  function wanted() {
    var set = FEATURED.slice();
    ((Q.S.ov && Q.S.ov.positions) || []).forEach(function (p) { var s = p.symbol.replace("USDT", ""); if (set.indexOf(s) < 0) set.push(s); });
    return set;
  }
  function sorted(list) {
    var by = Q.S.ms, l = list.slice();
    l.sort(function (a, b) {
      if (by === "gain") return b.change - a.change;
      if (by === "loss") return a.change - b.change;
      if (by === "name") return a.symbol < b.symbol ? -1 : 1;
      return (b.volume || 0) - (a.volume || 0);
    });
    var fi = FEATURED.map(function (s) { return l.filter(function (x) { return x.symbol === s; })[0]; }).filter(Boolean);
    return fi.concat(l.filter(function (x) { return FEATURED.indexOf(x.symbol) < 0; }));
  }

  V.markets = {
    mount: function (root) {
      root.innerHTML =
        '<div class="sec"><div id="mk-h1"></div><div id="mk-sum" class="card"></div></div>' +
        '<div class="sec"><div id="mk-h2"></div><div class="card"><div id="mk-tf"></div><div class="cvwrap tall"><canvas id="cv-mk" class="cv" role="img" aria-label="Price chart"></canvas></div></div></div>' +
        '<div class="seg" id="mk-seg"></div>' +
        '<div class="field"><input id="mk-q" type="search" autocomplete="off" aria-label="' + Q.esc(Q.t("search")) + '" placeholder="' + Q.esc(Q.t("search")) + '" value="' + Q.esc(Q.S.mq) + '"></div>' +
        '<div class="card" id="mk-list"></div>';
      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), v = b.getAttribute("data-v");
        if (a === "mtf") { Q.S.tf = v; Q._last.kl = 0; V.markets.reload(); }
        if (a === "msort") { Q.S.ms = v; V.markets.update(); }
        if (a === "mrow") {
          var k = "mk:" + v, was = !!Q.S.open[k];
          Q.S.open[k] = !was;
          if (!was) { Q.S.sym = v + "USDT"; Q._last.kl = 0; V.markets.reload(); } else V.markets.paintList();
        }
      };
      root.oninput = function (e) { if (e.target && e.target.id === "mk-q") { Q.S.mq = e.target.value || ""; V.markets.paintList(); } };
    },
    reload: async function () { await V.markets.loadChart(); V.markets.update(); },
    loadChart: async function () {
      try { Q.S.kl = await Q.api("/api/market_klines?symbol=" + encodeURIComponent(Q.S.sym) + "&interval=" + Q.S.tf); }
      catch (e) { Q.S.kl = []; }
    },
    load: async function () {
      await Q.every("tk", 20000, async function () {
        try { Q.S.tk = await Q.api("/api/live_tickers"); Q.S.tkErr = ""; } catch (e) { Q.S.tkErr = String(e.message || e); }
      });
      await Q.every("kl", 15000, V.markets.loadChart);
      await Q.every("mkl", 60000, async function () {
        var syms = wanted(), res = {};
        await Promise.all(syms.map(async function (s) {
          try { res[s] = analyse(await Q.api("/api/market_klines?symbol=" + encodeURIComponent(s + "USDT") + "&interval=1h")); } catch (e) { res[s] = null; }
        }));
        Q.S.mkl = res;
      });
    },
    update: function () {
      var ov = Q.S.ov, tk = Q.S.tk || [];
      var st = (ov && ov.status) || {}, comp = st.compass || {}, br = ov ? ov.breadth : null;
      var up = tk.filter(function (x) { return x.change > 0; }).length;
      Q.paint("mk-h1", Q.head("scan", Q.t("market_intel"), null));
      Q.paint("mk-sum",
        '<div class="chips">' + ["spot", "futures"].map(function (s) {
          var c = comp[s] || "", k = c === "BULLISH" ? "up" : c === "BEARISH" ? "down" : "flat";
          return '<span class="chip ' + k + '">' + s + " &middot; " + (c ? Q.t(c.toLowerCase()) : Q.t("na")) + "</span>";
        }).join("") + "</div>" +
        '<div class="kv"><div><span>' + Q.t("regime") + "</span><b>" + (comp.futures ? Q.t(comp.futures.toLowerCase()) : Q.t("na")) + "</b></div>" +
        "<div><span>" + Q.t("breadth") + '</span><b class="num">' + (br == null ? Q.t("na") : Q.n(br, 0) + "%") + "</b></div>" +
        "<div><span>" + Q.t("rising_24h") + '</span><b class="num">' + (tk.length ? up + " / " + tk.length : Q.t("na")) + "</b></div>" +
        "<div><span>" + Q.t("symbols") + '</span><b class="num">' + (tk.length || Q.t("na")) + "</b></div></div>");

      Q.paint("mk-h2", Q.head("chart", Q.S.sym.replace("USDT", "") + " \u00b7 " + Q.S.tf, null));
      Q.paint("mk-tf", '<div class="chips" style="margin-bottom:6px">' + ["15m", "1h", "4h"].map(function (k) {
        return '<button class="chip' + (Q.S.tf === k ? " on" : "") + '" data-act="mtf" data-v="' + k + '">' + k + "</button>";
      }).join("") + "</div>");
      var lines = [];
      ((ov && ov.positions) || []).forEach(function (x) {
        if (x.symbol !== Q.S.sym) return;
        lines.push({ price: x.entry, color: "#bdbdbd", label: Q.t("entry") }, { price: x.stop, color: COL.dn, label: Q.t("stop") }, { price: x.target, color: COL.lime, label: Q.t("target") });
      });
      C.candles(Q.$("cv-mk"), Q.S.kl, lines, { empty: Q.t("no_data") });

      Q.paint("mk-seg", SORTS.map(function (s) {
        return '<button class="' + (Q.S.ms === s[0] ? "on" : "") + '" data-act="msort" data-v="' + s[0] + '">' + Q.t(s[1]) + "</button>";
      }).join(""));
      V.markets.paintList();
    },
    paintList: function () {
      var tk = Q.S.tk || [], q = Q.S.mq.trim().toUpperCase(), kl = Q.S.mkl || {};
      if (!tk.length) {
        Q.paint("mk-list", Q.S.tkErr ? '<div class="err">' + Q.esc(Q.t("err_load") + ": " + Q.S.tkErr) + '</div><button class="btn pri blk" data-act="retry">' + Q.t("retry") + "</button>"
                                     : '<div class="sk" style="margin:12px 0"></div><div class="sk" style="margin:18px 0;width:80%"></div><div class="sk" style="margin:18px 0;width:60%"></div>');
        return;
      }
      var rows = sorted(tk).filter(function (x) { return !q || x.symbol.indexOf(q) >= 0; });
      Q.paint("mk-list", rows.length ? rows.slice(0, 80).map(function (x) {
        var a = kl[x.symbol], k = "mk:" + x.symbol, open = !!Q.S.open[k], sym = Q.esc(x.symbol);
        var trend = a ? (a.trend === "up" ? Q.t("uptrend") : a.trend === "down" ? Q.t("downtrend") : Q.t("sideways")) : Q.t("na");
        return '<div class="mx-w"><button class="mr" data-act="mrow" data-v="' + sym + '" aria-expanded="' + open + '"><span class="coin">' + sym.slice(0, 4) + '</span><span class="m"><b>' + sym +
          "</b><small>" + (x.volume ? "$" + Q.compact(x.volume) + " " + Q.t("vol") : Q.t("na")) + '</small></span><span class="sp">' +
          (a ? C.spark(a.sp, x.change >= 0 ? COL.lime : COL.dn, 100, 30) : "") + '</span><span class="e num"><b>' + Q.cnt(x.price, { pre: "$", dec: Q.priceDec(x.price), key: "mk" + x.symbol, flash: false }) + '</b><span class="' + Q.cls(x.change) + '">' + Q.sg(x.change) + "%</span></span></button>" +
          (open ? '<div class="mx"><div class="kv"><div><span>' + Q.t("trend_1h") + "</span><b class=\"" + (a ? (a.trend === "up" ? "up" : a.trend === "down" ? "down" : "flat") : "mu") + '">' + trend + "</b></div>" +
            "<div><span>" + Q.t("volatility") + '</span><b class="num">' + (a ? a.atr.toFixed(2) + "%" : Q.t("na")) + "</b></div>" +
            "<div><span>" + Q.t("change_24h") + '</span><b class="num ' + Q.cls(x.change) + '">' + Q.sg(x.change) + "%</b></div>" +
            "<div><span>" + Q.t("volume_24h") + '</span><b class="num">' + (x.volume ? "$" + Q.compact(x.volume) : Q.t("na")) + "</b></div></div></div>" : "") + "</div>";
      }).join("") : Q.empty("search", Q.t("no_match")));
    }
  };
  (window.__mods = window.__mods || []).push("markets");
})();
