"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;
  var RANGES = { "6h": 21600, "1d": 86400, "7d": 604800, all: 0 };

  V.overview = {
    mount: function (root) {
      root.innerHTML =
        '<div class="card hero"><div id="ov-hero"></div><div class="cvwrap"><canvas id="cv-eq" class="cv"></canvas></div><div id="ov-rng" style="margin-top:10px"></div></div>' +
        '<div id="ov-kpi" class="grid4"></div><div id="ov-risk" class="card"></div><div id="ov-perf" class="card"></div>' +
        '<div id="ov-mkt" class="card"></div>' +
        '<div class="card"><div id="ov-chh"></div><div class="cvwrap tall"><canvas id="cv-ch" class="cv"></canvas></div></div>' +
        '<div class="card"><div id="ov-mov"></div></div>';

      root.onclick = function (e) {
        var b = e.target.closest ? e.target.closest("[data-act]") : null;
        if (!b) return;
        var a = b.getAttribute("data-act"), v = b.getAttribute("data-v");
        if (a === "eqr") {
          Q.S.eqr = v;
          V.overview.update();
        }
        if (a === "sym") {
          Q.S.sym = v;
          Q._last.kl = 0;
          V.overview.reloadChart();
        }
        if (a === "tf") {
          Q.S.tf = v;
          Q._last.kl = 0;
          V.overview.reloadChart();
        }
      };
    },

    reloadChart: async function () {
      await V.overview.loadChart();
      V.overview.update();
    },

    loadChart: async function () {
      try {
        Q.S.kl = await Q.api(
          "/api/market_klines?symbol=" +
          encodeURIComponent(Q.S.sym) +
          "&interval=" + Q.S.tf
        );
      } catch (e) {
        Q.S.kl = [];
      }
    },

    load: async function () {
      await Q.every("eq", 30000, async function () {
        Q.S.eq = await Q.api("/api/pro/equity");
      });

      await Q.every("tk", 30000, async function () {
        Q.S.tk = await Q.api("/api/live_tickers");
      });

      await Q.every("kl", 15000, V.overview.loadChart);
    },

    eqPoints: function () {
      var pts = Q.S.eq || [], sec = RANGES[Q.S.eqr];
      if (!sec || !pts.length) return pts;

      var from = pts[pts.length - 1].t - sec;
      var f = pts.filter(function (p) {
        return p.t >= from;
      });

      return f.length >= 2 ? f : pts.slice(-2);
    },

    update: function () {
      var ov = Q.S.ov;

      if (!ov) {
        Q.paint("ov-hero",
          '<div class="sk" style="width:60%;height:34px"></div>'
        );
        return;
      }

      var p = ov.portfolio,
          r = ov.risk,
          perf = ov.perf,
          eq = p.equity,
          base = ov.initial || 0;

      var chg = eq - base;
      var chgPct = base ? (chg / base) * 100 : 0;

      Q.paint("ov-hero",
        '<div class="lbl">' + Q.t("equity") +
        '</div><div class="big num">$' + Q.n(eq) +
        '</div><div class="chg num ' + Q.cls(chg) + '">' +
        (chg >= 0 ? "&#9650; " : "&#9660; ") +
        Q.sg(chg) + " (" + Q.sg(chgPct) +
        '%) <span class="mu">' +
        Q.t("since_start") + "</span></div>"
      );

      var pts = V.overview.eqPoints();

      Q.paint("ov-rng",
        '<div class="chips">' +
        ["6h", "1d", "7d", "all"].map(function (k) {
          return '<button class="chip' +
            (Q.S.eqr === k ? " on" : "") +
            '" data-act="eqr" data-v="' + k + '">' +
            Q.t("r" + k) + "</button>";
        }).join("") +
        "</div>"
      );

      C.area(Q.$("cv-eq"), pts, {
        base: base,
        empty: Q.t("no_data")
      });

      Q.paint("ov-kpi",
        tile(Q.t("cash"), "$" + Q.n(p.cash_balance), "") +
        tile(Q.t("floating"), Q.sg(p.unrealized_pnl), Q.cls(p.unrealized_pnl)) +
        tile(Q.t("in_trades"), "$" + Q.n(p.open_margin), "") +
        tile(Q.t("open_risk"), "$" + Q.n(r.open_risk), "")
      );

      var cap = r.risk_cap || 0;
      var heat = cap ? (r.open_risk / cap) * 100 : 0;

      var lim = r.daily_loss_limit || 0;
      var usedPct = lim && r.daily_change < 0
        ? (-r.daily_change / lim) * 100
        : 0;

      var all = Q.S.eq || [];
      var peak = 0, maxdd = 0, i;

      for (i = 0; i < all.length; i++) {
        peak = Math.max(peak, all[i].v);
        if (peak) {
          maxdd = Math.max(
            maxdd,
            ((peak - all[i].v) / peak) * 100
          );
        }
      }

      var dd = peak
        ? Math.max(0, ((peak - eq) / peak) * 100)
        : 0;

      Q.paint("ov-risk",
        '<div class="h"><h3>' + Q.t("risk_heat") + "</h3></div>" +

        meter(
          Q.t("open_risk"),
          Q.n(r.open_risk) + " / " + Q.n(cap),
          heat,
          heat > 85 ? COL.dn : heat > 60 ? COL.wa : COL.cy
        ) +

        meter(
          Q.t("daily_pnl") + " " + Q.sg(r.daily_change),
          Q.t("daily_limit") + " " + Q.n(lim) +
          " (" + usedPct.toFixed(0) + "% " + Q.t("used") + ")",
          usedPct,
          usedPct >= 100 ? COL.dn :
          usedPct > 60 ? COL.wa : COL.up
        ) +

        meter(
          Q.t("drawdown") + " " + dd.toFixed(2) + "%",
          Q.t("max_dd") + " " + maxdd.toFixed(2) + "%",
          Math.min(100, (dd / 15) * 100),
          dd > 10 ? COL.dn : dd > 5 ? COL.wa : COL.vi
        ) +

        (r.daily_limit_hit
          ? '<div class="alert">' + Q.t("limit_hit") + "</div>"
          : "")
      );

      var pf = perf.profit_factor;
      var pfTxt = pf == null ? "INF" : Q.n(pf);
      var pfPct = pf == null ? 100 : Math.min(100, (pf / 3) * 100);

      var aw = perf.wins ? perf.gross_profit / perf.wins : 0;
      var al = perf.losses ? perf.gross_loss / perf.losses : 0;

      Q.paint("ov-perf",
        '<div class="rings"><div>' +
        C.ring(
          perf.win_rate,
          COL.up,
          perf.win_rate.toFixed(0) + "%",
          "W " + perf.wins + " / L " + perf.losses
        ) +
        '<div class="lbl" style="text-align:center">' +
        Q.t("win_rate") + "</div></div><div>" +

        C.ring(
          pfPct,
          COL.cy,
          pfTxt,
          "GP " + Q.n(perf.gross_profit, 1) +
          " / GL " + Q.n(perf.gross_loss, 1)
        ) +

        '<div class="lbl" style="text-align:center">' +
        Q.t("profit_factor") +
        "</div></div></div>" +

        '<div class="kv"><div><span>' +
        Q.t("trades") +
        '</span><b class="num">' +
        perf.total_trades +
        "</b></div><div><span>" +

        Q.t("net") +
        '</span><b class="num ' +
        Q.cls(perf.net_pnl) + '">' +
        Q.sg(perf.net_pnl) +
        "</b></div><div><span>" +

        Q.t("expectancy") +
        '</span><b class="num ' +
        Q.cls(perf.net_pnl) + '">' +
        Q.sg(
          perf.total_trades
            ? perf.net_pnl / perf.total_trades
            : 0
        ) +
        "</b></div><div><span>" +

        Q.t("payoff") +
        '</span><b class="num">' +
        (al ? Q.n(aw / al) : "-") +
        "</b></div><div><span>" +

        Q.t("avg_win") +
        '</span><b class="num up">' +
        Q.n(aw) +
        "</b></div><div><span>" +

        Q.t("avg_loss") +
        '</span><b class="num down">-' +
        Q.n(al) +
        "</b></div></div>"
      );

      var st = ov.status || {};
      var comp = st.compass || {};
      var br = ov.breadth;

      Q.paint("ov-mkt",
        '<div class="h"><h3>' +
        Q.t("market") +
        '</h3><span class="mu num">' +
        Q.t("last_scan") + " " +

        (st.last_scan
          ? Q.dur(ov.now - st.last_scan) + " " + Q.t("ago")
          : "-") +

        "</span></div>" +

        '<div class="chips">' +

        ["spot", "futures"].map(function (s) {
          var c = comp[s] || "NEUTRAL";

          var k = c === "BULLISH"
            ? "up"
            : c === "BEARISH"
              ? "down"
              : "flat";

          return '<span class="chip ' + k + '">' +
            s + " &middot; " +
            Q.t(c.toLowerCase()) +
            "</span>";
        }).join("") +

        "</div>" +

        (br == null
          ? ""
          : meter(
              Q.t("breadth"),
              Q.n(br, 0) + "%",
              br,
              br > 60 ? COL.up :
              br < 40 ? COL.dn : COL.wa
            ))
      );

      var syms = ["BTCUSDT", "ETHUSDT"];

      (ov.positions || []).forEach(function (x) {
        if (syms.indexOf(x.symbol) < 0) {
          syms.push(x.symbol);
        }
      });

      Q.paint("ov-chh",
        '<div class="h"><h3>' +
        Q.t("chart") + " &middot; " +
        Q.esc(Q.S.sym.replace("USDT", "")) +
        '</h3><div class="chips">' +

        ["15m", "1h", "4h"].map(function (k) {
          return '<button class="chip' +
            (Q.S.tf === k ? " on" : "") +
            '" data-act="tf" data-v="' + k + '">' +
            k + "</button>";
        }).join("") +

        '</div></div><div class="chips" style="margin-bottom:6px">' +

        syms.map(function (s) {
          return '<button class="chip' +
            (Q.S.sym === s ? " on" : "") +
            '" data-act="sym" data-v="' + s + '">' +
            Q.esc(s.replace("USDT", "")) +
            "</button>";
        }).join("") +

        "</div>"
      );

      var lines = [];

      (ov.positions || []).forEach(function (x) {
        if (x.symbol !== Q.S.sym) return;

        lines.push(
          {
            price: x.entry,
            color: "#8fb4ff",
            label: Q.t("entry")
          },
          {
            price: x.stop,
            color: COL.dn,
            label: Q.t("stop")
          },
          {
            price: x.target,
            color: COL.up,
            label: Q.t("target")
          }
        );
      });

      C.candles(Q.$("cv-ch"), Q.S.kl, lines, {
        empty: Q.t("no_data")
      });

      var tk = (Q.S.tk || []).slice().sort(function (a, b) {
        return b.change - a.change;
      });

      var g = tk.slice(0, 4);
      var l = tk.slice(-4).reverse();

      Q.paint(
        "ov-mov",
        tk.length
          ? '<div class="h"><h3>' +
            Q.t("movers") +
            '</h3></div><div class="grid2"><div>' +
            movers(g) +
            "</div><div>" +
            movers(l) +
            "</div></div>"
          : ""
      );
    }
  };

  function tile(label, value, cls) {
    return '<div class="tile"><div class="lbl">' +
      label +
      '</div><div class="v num ' +
      cls + '">' +
      value +
      "</div></div>";
  }

  function meter(a, b, pct, color) {
    return '<div class="meter"><div class="row"><span class="num">' +
      a +
      '</span><span class="mu num">' +
      b +
      "</span></div>" +
      C.bar(pct, color) +
      "</div>";
  }

  function movers(list) {
    return list.map(function (x) {
      return '<div class="it" style="padding:7px 0"><div class="m"><b>' +
        Q.esc(x.symbol) +
        '</b></div><div class="e num ' +
        Q.cls(x.change) +
        '">' +
        Q.sg(x.change) +
        "%</div></div>";
    }).join("");
  }

  (window.__mods = window.__mods || []).push("overview");
})();
