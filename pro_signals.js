
"use strict";
(function () {
  var Q = window.Q, C = Q.charts, COL = C.COL, V = Q.views;

  function blockers(list) {
    var count = {};

    list.forEach(function (d) {
      if (d.action !== "HOLD") return;

      var txt = String(d.reason || "")
        .replace(/^\[[^\]]*\]\s*/, "")
        .replace(/^Blocked:\s*/i, "");

      txt.split(/ \| |; /).forEach(function (part) {
        var k = part
          .replace(/\([^)]*\)/g, "")
          .replace(/\d+(\.\d+)?/g, "#")
          .replace(/\s+/g, " ")
          .trim();

        if (k) count[k] = (count[k] || 0) + 1;
      });
    });

    return Object.keys(count)
      .map(function (k) {
        return [k, count[k]];
      })
      .sort(function (a, b) {
        return b[1] - a[1];
      })
      .slice(0, 8);
  }

  V.signals = {
    mount: function (root) {
      root.innerHTML =
        '<div id="sg-sum" class="card"></div>' +
        '<div id="sg-why" class="card"></div>' +
        '<div class="card"><div id="sg-fl"></div>' +
        '<div id="sg-list" class="list"></div></div>';

      root.onclick = function (e) {
        var b = e.target.closest
          ? e.target.closest("[data-act]")
          : null;

        if (b && b.getAttribute("data-act") === "sf") {
          Q.S.sf = b.getAttribute("data-v");
          V.signals.update();
        }
      };

      root.oninput = function (e) {
        if (e.target && e.target.id === "sg-q") {
          Q.S.sq = e.target.value || "";
          V.signals.paintList();
        }
      };
    },

    load: async function () {
      await Q.every("sig", 10000, async function () {
        Q.S.sig = await Q.api("/api/pro/signals");
      });
    },

    update: function () {
      var s = Q.S.sig;
      if (!s) return;

      var entries = s.filter(function (d) {
        return d.action !== "HOLD";
      });

      var last = entries[0];

      Q.paint(
        "sg-sum",
        '<div class="grid2"><div><div class="lbl">' +
        Q.t("decisions") +
        '</div><div class="big num" style="font-size:26px">' +
        s.length +
        '</div></div><div><div class="lbl">' +
        Q.t("entries_n") +
        '</div><div class="big num up" style="font-size:26px">' +
        entries.length +
        ' <span class="mu" style="font-size:14px">' +
        (s.length
          ? (entries.length / s.length * 100).toFixed(1)
          : "0") +
        "%" +
        (last ? " &middot; " + Q.ago(last.t) : "") +
        "</span></div></div></div>"
      );

      var b = blockers(s);
      var mx = b.length ? b[0][1] : 1;

      Q.paint(
        "sg-why",
        '<div class="h"><h3>' +
        Q.t("why_none") +
        '</h3></div><div class="mu" style="font-size:12px;margin-bottom:6px">' +
        Q.t("top_blockers") +
        "</div>" +

        (b.length
          ? b.map(function (x) {
              return '<div class="brow"><span class="n" title="' +
                Q.esc(x[0]) +
                '">' +
                Q.esc(x[0]) +
                "</span>" +
                C.bar(x[1] / mx * 100, COL.vi) +
                '<span class="c num">' +
                x[1] +
                "</span></div>";
            }).join("")
          : '<div class="empty">' +
            Q.t("all_clear") +
            "</div>")
      );

      Q.paint(
        "sg-fl",
        '<div class="chips" style="margin-bottom:8px">' +

        [
          ["all", "f_all"],
          ["entries", "f_entries"],
          ["blocked", "f_blocked"]
        ].map(function (f) {
          return '<button class="chip' +
            (Q.S.sf === f[0] ? " on" : "") +
            '" data-act="sf" data-v="' +
            f[0] +
            '">' +
            Q.t(f[1]) +
            "</button>";
        }).join("") +

        '</div><div class="field"><input id="sg-q" placeholder="' +
        Q.esc(Q.t("search")) +
        '" value="' +
        Q.esc(Q.S.sq) +
        '"></div>'
      );

      V.signals.paintList();
    },

    paintList: function () {
      var s = Q.S.sig || [];
      var q = Q.S.sq.trim().toUpperCase();

      var rows = s.filter(function (d) {
        if (Q.S.sf === "entries" && d.action === "HOLD") {
          return false;
        }

        if (Q.S.sf === "blocked" && d.action !== "HOLD") {
          return false;
        }

        return !q ||
          String(d.symbol).toUpperCase().indexOf(q) >= 0;
      }).slice(0, 80);

      Q.paint(
        "sg-list",
        rows.length
          ? rows.map(function (d) {
              var k = d.action === "HOLD"
                ? "hold"
                : (/SELL|SHORT/.test(d.action) ? "sell" : "buy");

              return '<div class="it"><div class="m"><b>' +
                Q.esc(String(d.symbol).replace("USDT", "")) +
                ' <span class="tag ' +
                k +
                '">' +
                Q.esc(d.action) +
                '</span> <span class="tag src">' +
                Q.esc(d.source) +
                "</span></b><small>" +
                Q.esc(d.reason) +
                '</small></div><div class="e num mu">' +
                Q.n(d.score, 0) +
                "<small>" +
                Q.ago(d.t) +
                "</small></div></div>";
            }).join("")
          : '<div class="empty">' +
            Q.t("no_signals") +
            "</div>"
      );
    }
  };

  (window.__mods = window.__mods || []).push("signals");
})();
