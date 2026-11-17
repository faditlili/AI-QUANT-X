
"use strict";
(function () {
  var Q = window.Q, C = Q.charts;
  var COL = {
    up: "#19e6a0",
    dn: "#ff4d6d",
    cy: "#00e5ff",
    vi: "#a855f7",
    wa: "#ffb020",
    grid: "rgba(140,170,255,.10)",
    tx: "rgba(200,212,240,.72)"
  };

  C.COL = COL;

  function setup(cv) {
    var dpr = Math.min(window.devicePixelRatio || 1, 3);
    var r = cv.getBoundingClientRect();
    var w = Math.max(10, Math.floor(r.width));
    var h = Math.max(10, Math.floor(r.height));

    if (cv.width !== w * dpr || cv.height !== h * dpr) {
      cv.width = w * dpr;
      cv.height = h * dpr;
    }

    var g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.font = "10px ui-monospace,Menlo,monospace";

    return { g: g, w: w, h: h };
  }

  function bind(cv) {
    if (cv._bound) return;
    cv._bound = true;

    function pos(e) {
      var r = cv.getBoundingClientRect();
      return e.clientX - r.left;
    }

    cv.addEventListener("pointerdown", function (e) {
      cv._x = pos(e);
      draw(cv);
    });

    cv.addEventListener("pointermove", function (e) {
      if (cv._x != null) {
        cv._x = pos(e);
        draw(cv);
      }
    });

    var end = function () {
      cv._x = null;
      draw(cv);
    };

    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointerleave", end);
    cv.addEventListener("pointercancel", end);
  }

  function draw(cv) {
    if (!cv || !cv._d) return;

    if (cv._d.k === "area") {
      drawArea(cv);
    } else {
      drawCandles(cv);
    }
  }

  function tip(g, w, text, x) {
    var tw = g.measureText(text).width + 12;
    var tx = Math.min(Math.max(x - tw / 2, 2), w - tw - 2);

    g.fillStyle = "rgba(10,15,31,.92)";
    g.fillRect(tx, 2, tw, 18);
    g.fillStyle = "#e8eeff";
    g.fillText(text, tx + 6, 14);
  }

  C.area = function (cv, pts, opt) {
    if (!cv) return;

    cv._d = {
      k: "area",
      pts: pts || [],
      opt: opt || {}
    };

    bind(cv);
    draw(cv);
  };

  function drawArea(cv) {
    var s = setup(cv);
    var g = s.g, w = s.w, h = s.h;
    var d = cv._d, pts = d.pts, o = d.opt;

    if (pts.length < 2) {
      g.fillStyle = COL.tx;
      g.fillText(o.empty || "", 8, h / 2);
      return;
    }

    var padT = 24, padB = 14, padR = 44;
    var pw = w - padR, ph = h - padT - padB;
    var mn = Infinity, mx = -Infinity, i;

    for (i = 0; i < pts.length; i++) {
      mn = Math.min(mn, pts[i].v);
      mx = Math.max(mx, pts[i].v);
    }

    if (o.base != null) {
      mn = Math.min(mn, o.base);
      mx = Math.max(mx, o.base);
    }

    if (mx - mn < 1e-9) {
      mx += 1;
      mn -= 1;
    }

    var pad = (mx - mn) * 0.12;
    mn -= pad;
    mx += pad;

    var t0 = pts[0].t;
    var t1 = pts[pts.length - 1].t || t0 + 1;

    function X(k) {
      return pts.length > 1
        ? (k / (pts.length - 1)) * pw
        : 0;
    }

    function Y(v) {
      return padT + (1 - (v - mn) / (mx - mn)) * ph;
    }

    g.strokeStyle = COL.grid;
    g.lineWidth = 1;
    g.fillStyle = COL.tx;

    for (i = 0; i < 3; i++) {
      var yy = padT + (ph * i) / 2;

      g.beginPath();
      g.moveTo(0, yy);
      g.lineTo(pw, yy);
      g.stroke();

      g.fillText(
        Q.n(mx - ((mx - mn) * i) / 2, 2),
        pw + 4,
        yy + 3
      );
    }

    var up = pts[pts.length - 1].v >= pts[0].v;
    var col = up ? COL.up : COL.dn;

    if (o.base != null) {
      g.setLineDash([4, 4]);
      g.strokeStyle = "rgba(255,255,255,.28)";
      g.beginPath();
      g.moveTo(0, Y(o.base));
      g.lineTo(pw, Y(o.base));
      g.stroke();
      g.setLineDash([]);
    }

    var grad = g.createLinearGradient(0, padT, 0, h);

    grad.addColorStop(
      0,
      up
        ? "rgba(25,230,160,.30)"
        : "rgba(255,77,109,.30)"
    );

    grad.addColorStop(1, "rgba(0,0,0,0)");

    g.beginPath();
    g.moveTo(X(0), Y(pts[0].v));

    for (i = 1; i < pts.length; i++) {
      g.lineTo(X(i), Y(pts[i].v));
    }

    g.lineTo(X(pts.length - 1), h - padB);
    g.lineTo(X(0), h - padB);
    g.closePath();
    g.fillStyle = grad;
    g.fill();

    g.beginPath();
    g.moveTo(X(0), Y(pts[0].v));

    for (i = 1; i < pts.length; i++) {
      g.lineTo(X(i), Y(pts[i].v));
    }

    g.strokeStyle = col;
    g.lineWidth = 2;
    g.lineJoin = "round";
    g.stroke();

    var lx = X(pts.length - 1);
    var ly = Y(pts[pts.length - 1].v);

    g.fillStyle = col;
    g.beginPath();
    g.arc(lx, ly, 3.5, 0, 6.2832);
    g.fill();

    if (cv._x != null) {
      var k = Math.max(
        0,
        Math.min(
          pts.length - 1,
          Math.round((cv._x / pw) * (pts.length - 1))
        )
      );

      var px = X(k);
      var py = Y(pts[k].v);

      g.strokeStyle = "rgba(255,255,255,.35)";
      g.beginPath();
      g.moveTo(px, padT);
      g.lineTo(px, h - padB);
      g.stroke();

      g.fillStyle = "#fff";
      g.beginPath();
      g.arc(px, py, 4, 0, 6.2832);
      g.fill();

      var dt = new Date(pts[k].t * 1000);

      tip(
        g,
        w,
        Q.n(pts[k].v, 2) +
        "  " +
        dt.getHours() +
        ":" +
        ("0" + dt.getMinutes()).slice(-2) +
        " " +
        dt.getDate() +
        "/" +
        (dt.getMonth() + 1),
        px
      );
    }
  }

  C.candles = function (cv, candles, lines, opt) {
    if (!cv) return;

    cv._d = {
      k: "candles",
      c: candles || [],
      lines: lines || [],
      opt: opt || {}
    };

    bind(cv);
    draw(cv);
  };

  function drawCandles(cv) {
    var s = setup(cv);
    var g = s.g, w = s.w, h = s.h;
    var d = cv._d, all = d.c, lines = d.lines;

    if (all.length < 3) {
      g.fillStyle = COL.tx;
      g.fillText(d.opt.empty || "", 8, h / 2);
      return;
    }

    var n = Math.min(all.length, d.opt.n || 70);
    var c = all.slice(all.length - n);

    var padR = 58, padT = 24, padB = 8;
    var pw = w - padR, ph = h - padT - padB;
    var i;

    var mn = Infinity, mx = -Infinity;

    for (i = 0; i < c.length; i++) {
      mn = Math.min(mn, c[i].low);
      mx = Math.max(mx, c[i].high);
    }

    var span = mx - mn || 1;

    for (i = 0; i < lines.length; i++) {
      var p = lines[i].price;

      if (p > mn - span * 0.6 && p < mx + span * 0.6) {
        mn = Math.min(mn, p);
        mx = Math.max(mx, p);
      }
    }

    span = mx - mn || 1;
    mn -= span * 0.04;
    mx += span * 0.04;
    span = mx - mn;

    function Y(v) {
      return padT + (1 - (v - mn) / span) * ph;
    }

    var cw = pw / c.length;

    g.strokeStyle = COL.grid;
    g.lineWidth = 1;
    g.fillStyle = COL.tx;

    for (i = 0; i < 5; i++) {
      var gy = padT + (ph * i) / 4;

      g.beginPath();
      g.moveTo(0, gy);
      g.lineTo(pw, gy);
      g.stroke();

      g.fillText(
        Q.price(mx - (span * i) / 4),
        pw + 4,
        gy + 3
      );
    }

    for (i = 0; i < c.length; i++) {
      var k = c[i];
      var x = i * cw + cw / 2;
      var col = k.close >= k.open ? COL.up : COL.dn;

      g.strokeStyle = col;
      g.fillStyle = col;
      g.lineWidth = 1;

      g.beginPath();
      g.moveTo(x, Y(k.high));
      g.lineTo(x, Y(k.low));
      g.stroke();

      var top = Y(Math.max(k.open, k.close));
      var bh = Math.max(
        1,
        Math.abs(Y(k.open) - Y(k.close))
      );

      g.fillRect(
        x - Math.max(1, cw * 0.36),
        top,
        Math.max(2, cw * 0.72),
        bh
      );
    }

    for (i = 0; i < lines.length; i++) {
      var L = lines[i];
      var ly = Y(L.price);

      if (ly < padT - 2 || ly > h - padB + 2) continue;

      g.strokeStyle = L.color;
      g.fillStyle = L.color;
      g.lineWidth = 1;
      g.setLineDash([5, 4]);

      g.beginPath();
      g.moveTo(0, ly);
      g.lineTo(pw, ly);
      g.stroke();

      g.setLineDash([]);
      g.fillText(L.label, 4, ly - 3);
    }

    var last = c[c.length - 1];
    var lc = last.close >= last.open ? COL.up : COL.dn;
    var lyy = Y(last.close);

    g.strokeStyle = lc;
    g.setLineDash([2, 3]);
    g.beginPath();
    g.moveTo(0, lyy);
    g.lineTo(pw, lyy);
    g.stroke();
    g.setLineDash([]);

    g.fillStyle = lc;
    g.fillRect(pw, lyy - 8, padR, 16);
    g.fillStyle = "#031018";
    g.fillText(Q.price(last.close), pw + 3, lyy + 3);

    if (cv._x != null) {
      var idx = Math.max(
        0,
        Math.min(c.length - 1, Math.floor(cv._x / cw))
      );

      var q = c[idx];
      var cx = idx * cw + cw / 2;

      g.strokeStyle = "rgba(255,255,255,.35)";
      g.beginPath();
      g.moveTo(cx, padT);
      g.lineTo(cx, h - padB);
      g.stroke();

      tip(
        g,
        w,
        "O " + Q.price(q.open) +
        "  H " + Q.price(q.high) +
        "  L " + Q.price(q.low) +
        "  C " + Q.price(q.close),
        cx
      );
    }
  }

  C.ring = function (pct, color, center, sub) {
    pct = Math.max(0, Math.min(100, Number(pct) || 0));

    var R = 42;
    var len = 2 * Math.PI * R;

    return '<svg viewBox="0 0 100 100" class="ring">' +
      '<circle cx="50" cy="50" r="42" class="ring-bg"/>' +
      '<circle cx="50" cy="50" r="42" class="ring-fg" style="stroke:' +
      color +
      ";stroke-dasharray:" +
      len.toFixed(1) +
      ";stroke-dashoffset:" +
      (len * (1 - pct / 100)).toFixed(1) +
      '"/><text x="50" y="55" class="ring-t">' +
      Q.esc(center) +
      "</text>" +
      (sub
        ? '<text x="50" y="70" class="ring-s">' +
          Q.esc(sub) +
          "</text>"
        : "") +
      "</svg>";
  };

  C.bar = function (pct, color) {
    pct = Math.max(0, Math.min(100, Number(pct) || 0));

    return '<div class="bar"><i style="width:' +
      pct.toFixed(1) +
      "%;background:" +
      color +
      '"></i></div>';
  };

  C.spark = function (vals, color, w, h) {
    w = w || 120;
    h = h || 34;

    if (!vals || vals.length < 2) return "";

    var mn = Math.min.apply(null, vals);
    var mx = Math.max.apply(null, vals);
    var sp = mx - mn || 1;

    var pts = vals.map(function (v, i) {
      return (
        ((i / (vals.length - 1)) * w).toFixed(1) +
        "," +
        (h - 3 - ((v - mn) / sp) * (h - 6)).toFixed(1)
      );
    }).join(" ");

    return '<svg viewBox="0 0 ' +
      w +
      " " +
      h +
      '" width="100%" height="' +
      h +
      '" preserveAspectRatio="none"><polyline fill="none" stroke="' +
      color +
      '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="' +
      pts +
      '"/></svg>';
  };

  (window.__mods = window.__mods || []).push("charts");
})();
