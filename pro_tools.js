
"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;

  function kv(k, v, cls) {
    return "<div><span>" + k +
      '</span><b class="num ' + (cls || "") +
      '">' + v + "</b></div>";
  }

  V.tools = {
    mount: function (root) {
      root.innerHTML =
        '<div id="tl-eng" class="card"></div>' +
        '<div id="tl-ml" class="card"></div>' +
        '<div id="tl-rk" class="card"></div>' +
        '<div class="card"><div class="h"><h3>' +
        Q.t("backtest") +
        '</h3></div><div class="field"><input id="bt-sym" value="BTCUSDT" autocapitalize="characters" aria-label="symbol">' +
        '<select id="bt-str" aria-label="strategy"><option value="all">all</option></select></div>' +
        '<button class="btn pri blk" data-act="bt" id="bt-go">' +
        Q.t("run") +
        '</button><pre class="out" id="bt-out" style="display:none"></pre></div>' +
        '<div class="card"><div class="h"><h3>' +
        Q.t("autotune") +
        '</h3></div><button class="btn pri blk" data-act="tune" id="at-go">' +
        Q.t("autotune") +
        "</button></div>" +
        '<div class="card"><div class="kv">' +
        kv(Q.t("version"), '<span id="tl-ver">-</span>') +
        kv(Q.t("language"), Q.S.lang.toUpperCase()) +
        "</div></div>";

      root.onclick = function (e) {
        var b = e.target.closest
          ? e.target.closest("[data-act]")
          : null;

        if (!b) return;

        var a = b.getAttribute("data-act");

        if (a === "bt") V.tools.backtest();
        if (a === "tune") V.tools.tune();
      };
    },

    load: async function () {
      await Q.every("sys", 20000, async function () {
        Q.S.sys = await Q.api("/api/pro/system");
      });
    },

    update: function () {
      var s = Q.S.sys;
      if (!s) return;

      var st = s.status || {},
          ml = s.ml || {},
          rk = s.risk || {},
          names = Object.keys(s.strategies || {});

      var sel = Q.$("bt-str");

      if (sel && sel.options.length <= 1) {
        names.forEach(function (n) {
          var o = document.createElement("option");
          o.value = n;
          o.textContent = n;
          sel.appendChild(o);
        });
      }

      var ver = Q.$("tl-ver");
      if (ver) ver.textContent = s.version;

      Q.paint(
        "tl-eng",
        '<div class="h"><h3>' +
        Q.t("engine") +
        '</h3><span class="pill ' +
        (st.paused ? "off" : "on") +
        '"><i class="dot"></i>' +
        (st.paused ? Q.t("paused") : Q.t("running")) +
        "</span></div>" +

        '<div class="chips" style="margin-bottom:10px">' +

        names.map(function (n) {
          return '<span class="chip ' +
            (s.strategies[n] ? "up" : "down") +
            '">' + Q.esc(n) +
            " &middot; " +
            (s.strategies[n]
              ? Q.t("healthy")
              : Q.t("paused_s")) +
            "</span>";
        }).join("") +

        '</div><div class="kv">' +

        kv(Q.t("symbols"), s.symbols) +

        kv(
          Q.t("scan_every"),
          s.scan_every + Q.t("sec")
        ) +

        kv(
          Q.t("protection"),
          s.protection.blocked
            ? Q.esc(s.protection.reason)
            : Q.t("ok"),
          s.protection.blocked ? "down" : "up"
        ) +

        kv(
          Q.t("auto_active"),
          s.auto && s.auto.strategy
            ? Q.esc(s.auto.strategy) + " " +
              Q.esc(s.auto.rsi) + "/" +
              Q.esc(s.auto.ema)
            : "-"
        ) +

        "</div>"
      );

      var mlTxt = !ml.present
        ? Q.t("ml_none")
        : ml.valid
          ? Q.t("ml_on")
          : Q.t("ml_off");

      Q.paint(
        "tl-ml",
        '<div class="h"><h3>' +
        Q.t("ml") +
        '</h3><span class="pill ' +
        (ml.valid ? "on" : "off") +
        '"><i class="dot"></i>' +
        (ml.valid ? Q.t("ml_on") : "OFF") +
        '</span></div><div class="mu" style="font-size:12.5px">' +
        mlTxt +
        "</div>" +

        (ml.present
          ? '<div class="kv">' +
            kv(Q.t("accuracy"), (ml.accuracy * 100).toFixed(1) + "%") +
            kv(Q.t("baseline"), (ml.baseline * 100).toFixed(1) + "%") +
            kv(Q.t("age"), ml.age_hours == null
              ? "-"
              : ml.age_hours.toFixed(1) + Q.t("hours")) +
            kv(Q.t("trades"), ml.rows) +
            "</div>"
          : "")
      );

      Q.paint(
        "tl-rk",
        '<div class="h"><h3>' +
        Q.t("risk_cfg") +
        '</h3></div><div class="kv">' +
        kv(Q.t("per_trade"), rk.per_trade + "%") +
        kv(Q.t("portfolio"), rk.portfolio + "%") +
        kv(Q.t("daily_limit"), rk.daily_limit + "%") +
        kv(Q.t("max_dd"), rk.max_drawdown + "%") +
        kv(Q.t("max_pos"), rk.max_positions) +
        "</div>"
      );
    },

    backtest: async function () {
      var btn = Q.$("bt-go"),
          out = Q.$("bt-out");

      var sym = (
        Q.$("bt-sym").value || "BTCUSDT"
      ).trim().toUpperCase();

      var str = Q.$("bt-str").value || "all";

      btn.disabled = true;
      btn.textContent = Q.t("working");
      out.style.display = "block";
      out.textContent = "...";

      try {
        var r = await Q.api(
          "/api/run_backtest?symbol=" +
          encodeURIComponent(sym) +
          "&strategy=" +
          encodeURIComponent(str),
          { method: "POST" }
        );

        out.textContent = r.success
          ? r.report
          : (r.error || "error");

      } catch (e) {
        out.textContent = e.message;
      }

      btn.disabled = false;
      btn.textContent = Q.t("run");
    },

    tune: async function () {
      var btn = Q.$("at-go");

      btn.disabled = true;
      btn.textContent = Q.t("working");

      try {
        var r = await Q.api(
          "/api/auto_tune?symbol=BTCUSDT",
          { method: "POST" }
        );

        if (r.success) {
          var b = r.best_params;

          Q.sheet(
            Q.t("tune_ok"),
            b.strategy +
            " | RSI " + b.RSI +
            " | EMA " + b.EMA +
            "\n" +
            Q.t("trades") + ": " + r.trades +
            " | " +
            Q.t("net") + ": " +
            Q.sg(r.return_pct) +
            "%\n" +
            (r.note || "")
          );

          Q.S.sys = null;
          Q._last.sys = 0;

        } else {
          Q.sheet(
            Q.t("tune_fail"),
            r.error || "error"
          );
        }

      } catch (e) {
        Q.toast(e.message, "err");
      }

      btn.disabled = false;
      btn.textContent = Q.t("autotune");
    }
  };

  (window.__mods = window.__mods || []).push("tools");
})();
