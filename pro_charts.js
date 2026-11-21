"use strict";
(function () {
  var Q = window.Q, C = Q.charts;
  var COL = { up: "#c9f53b", dn: "#ff6b6b", cy: "#ffffff", vi: "#9a9a9a", wa: "#ffb84d", lime: "#d6ff1f", bar: "#262626",
              grid: "rgba(255,255,255,.07)", tx: "rgba(255,255,255,.55)" };
  C.COL = COL;

  function setup(cv) {
    var dpr = Math.min(window.devicePixelRatio || 1, 3);
    var r = cv.getBoundingClientRect();
    var w = Math.max(10, Math.floor(r.width)), h = Math.max(10, Math.floor(r.height));
    if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
    var g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.font = "10px ui-monospace,Menlo,Consolas,monospace";
    return { g: g, w: w, h: h };
  }
  function rr(g, x, y, w, h, r) {                       // rounded rectangle without relying on ctx.roundRect
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    g.beginPath();
    g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.arcTo(x + w, y, x + w, y + r, r);
    g.lineTo(x + w, y + h - r); g.arcTo(x + w, y + h, x + w - r, y + h, r);
    g.lineTo(x + r, y + h); g.arcTo(x, y + h, x, y + h - r, r);
    g.lineTo(x, y + r); g.arcTo(x, y, x + r, y, r); g.closePath();
  }
  function bind(cv) {
    if (cv._bound) return;
    cv._bound = true;
    function pos(e) { var r = cv.getBoundingClientRect(); return e.clientX - r.left; }
    var bars = function () { return cv._d && cv._d.k === "bars"; };
    cv.addEventListener("pointerdown", function (e) { cv._x = pos(e); if (bars()) cv._sel = barAt(cv, cv._x); draw(cv); });
    cv.addEventListener("pointermove", function (e) { if (cv._x != null) { cv._x = pos(e); if (bars()) cv._sel = barAt(cv, cv._x); draw(cv); } });
    var end = function () { cv._x = null; draw(cv); };       // chart selections (bars) stay; crosshairs go away
    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointerleave", end);
    cv.addEventListener("pointercancel", end);
  }
  function draw(cv) {
    if (!cv || !cv._d) return;
    var k = cv._d.k;
    if (k === "area") drawArea(cv); else if (k === "bars") drawBars(cv); else drawCandles(cv);
  }
  function tip(g, w, text, x, y) {
    var tw = g.measureText(text).width + 14;
    var tx = Math.min(Math.max(x - tw / 2, 2), w - tw - 2), ty = y == null ? 2 : y;
    g.fillStyle = COL.lime; rr(g, tx, ty, tw, 19, 9.5); g.fill();
    g.fillStyle = "#000"; g.fillText(text, tx + 7, ty + 13);
  }

  /* ---------- area / equity curve ---------- */
  C.area = function (cv, pts, opt) {
    if (!cv) return;
    cv._d = { k: "area", pts: pts || [], opt: opt || {} };
    bind(cv); draw(cv);
  };
  function drawArea(cv) {
    var s = setup(cv), g = s.g, w = s.w, h = s.h, d = cv._d, pts = d.pts, o = d.opt;
    if (pts.length < 2) { g.fillStyle = COL.tx; g.fillText(o.empty || "", 8, h / 2); return; }
    var padT = 26, padB = 14, padR = 46, pw = w - padR, ph = h - padT - padB, mn = Infinity, mx = -Infinity, i;
    for (i = 0; i < pts.length; i++) { mn = Math.min(mn, pts[i].v); mx = Math.max(mx, pts[i].v); }
    if (o.base != null) { mn = Math.min(mn, o.base); mx = Math.max(mx, o.base); }
    if (mx - mn < 1e-9) { mx += 1; mn -= 1; }
    var pad = (mx - mn) * 0.14; mn -= pad; mx += pad;
    function X(k) { return (k / (pts.length - 1)) * pw; }
    function Y(v) { return padT + (1 - (v - mn) / (mx - mn)) * ph; }
    g.strokeStyle = COL.grid; g.lineWidth = 1; g.fillStyle = COL.tx;
    for (i = 0; i < 3; i++) {
      var yy = padT + (ph * i) / 2; g.beginPath(); g.moveTo(0, yy); g.lineTo(pw, yy); g.stroke();
      g.fillText(Q.n(mx - ((mx - mn) * i) / 2, 2), pw + 5, yy + 3);
    }
    var up = pts[pts.length - 1].v >= pts[0].v, col = up ? COL.lime : COL.dn;
    if (o.base != null) {
      g.setLineDash([4, 4]); g.strokeStyle = "rgba(255,255,255,.28)"; g.beginPath(); g.moveTo(0, Y(o.base)); g.lineTo(pw, Y(o.base)); g.stroke(); g.setLineDash([]);
    }
    if (cv._x != null) {                                   // highlighted column, as in the reference
      var kk = Math.max(0, Math.min(pts.length - 1, Math.round((cv._x / pw) * (pts.length - 1))));
      g.fillStyle = up ? "rgba(214,255,31,.10)" : "rgba(255,107,107,.10)";
      g.fillRect(Math.max(0, X(kk) - 14), padT, 28, ph);
    }
    var grad = g.createLinearGradient(0, padT, 0, h);
    grad.addColorStop(0, up ? "rgba(214,255,31,.32)" : "rgba(255,107,107,.30)"); grad.addColorStop(1, "rgba(0,0,0,0)");
    g.beginPath(); g.moveTo(X(0), Y(pts[0].v));
    for (i = 1; i < pts.length; i++) g.lineTo(X(i), Y(pts[i].v));
    g.lineTo(X(pts.length - 1), h - padB); g.lineTo(X(0), h - padB); g.closePath(); g.fillStyle = grad; g.fill();
    g.beginPath(); g.moveTo(X(0), Y(pts[0].v));
    for (i = 1; i < pts.length; i++) g.lineTo(X(i), Y(pts[i].v));
    g.strokeStyle = col; g.lineWidth = 2.2; g.lineJoin = "round"; g.stroke();
    var lx = X(pts.length - 1), ly = Y(pts[pts.length - 1].v);
    g.fillStyle = "#000"; g.beginPath(); g.arc(lx, ly, 5, 0, 6.2832); g.fill();
    g.strokeStyle = col; g.lineWidth = 2.5; g.beginPath(); g.arc(lx, ly, 4, 0, 6.2832); g.stroke();
    if (cv._x != null) {
      var k = Math.max(0, Math.min(pts.length - 1, Math.round((cv._x / pw) * (pts.length - 1))));
      var px = X(k), py = Y(pts[k].v);
      g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 1; g.beginPath(); g.moveTo(px, padT); g.lineTo(px, h - padB); g.stroke();
      g.fillStyle = "#fff"; g.beginPath(); g.arc(px, py, 4, 0, 6.2832); g.fill();
      var dt = new Date(pts[k].t * 1000);
      tip(g, w, Q.n(pts[k].v, 2) + "  " + dt.getHours() + ":" + ("0" + dt.getMinutes()).slice(-2) + " " + dt.getDate() + "/" + (dt.getMonth() + 1), px);
    }
  }

  /* ---------- rounded bars with a striped highlight and value bubble ---------- */
  C.bars = function (cv, items, opt) {
    if (!cv) return;
    cv._d = { k: "bars", items: items || [], opt: opt || {} };
    if (cv._sel == null || cv._sel >= cv._d.items.length) cv._sel = null;
    bind(cv); draw(cv);
  };
  function barGeom(cv) {
    var d = cv._d, o = d.opt, w = cv.getBoundingClientRect().width, padL = 44, n = d.items.length || 1;
    return { padL: padL, slot: Math.max(1, (w - padL - 4) / n) };
  }
  function barAt(cv, x) {
    var gm = barGeom(cv), n = cv._d.items.length;
    return Math.max(0, Math.min(n - 1, Math.floor((x - gm.padL) / gm.slot)));
  }
  function drawBars(cv) {
    var s = setup(cv), g = s.g, w = s.w, h = s.h, d = cv._d, items = d.items, o = d.opt, i;
    if (!items.length) { g.fillStyle = COL.tx; g.fillText(o.empty || "", 8, h / 2); return; }
    var padL = 44, padT = 38, padB = 20, pw = w - padL - 4, ph = h - padT - padB, n = items.length, slot = pw / n;
    var mn = 0, mx = 0;
    for (i = 0; i < n; i++) { mn = Math.min(mn, items[i].v); mx = Math.max(mx, items[i].v); }
    if (mx - mn < 1e-9) mx = mn + 1;
    function Y(v) { return padT + (1 - (v - mn) / (mx - mn)) * ph; }
    var y0 = Y(0), sel = cv._sel != null ? cv._sel : (o.hi != null && o.hi < n ? o.hi : n - 1);
    g.fillStyle = COL.tx; g.strokeStyle = COL.grid; g.lineWidth = 1;
    for (i = 0; i < 3; i++) {
      var v = mx - ((mx - mn) * i) / 2, gy = Y(v);
      g.fillText(o.fmt ? o.fmt(v) : Q.n(v, 0), 0, gy + 3);
    }
    if (o.ref != null) {
      g.setLineDash([4, 4]); g.strokeStyle = "rgba(255,255,255,.3)"; g.beginPath(); g.moveTo(padL, Y(o.ref)); g.lineTo(w, Y(o.ref)); g.stroke(); g.setLineDash([]);
    }
    var bw = Math.max(8, Math.min(34, slot * 0.62));
    for (i = 0; i < n; i++) {
      var it = items[i], cx = padL + i * slot + slot / 2, top = Y(Math.max(it.v, 0)), bot = Y(Math.min(it.v, 0));
      var bh = Math.max(bw, bot - top);                        // pill bars never shrink below their own width
      var y = it.v >= 0 ? y0 - bh : y0, x = cx - bw / 2;
      if (it.v === 0) { y = y0 - bh; }
      if (i === sel) {
        g.save(); rr(g, x, y, bw, bh, bw / 2); g.clip();
        g.fillStyle = it.v >= 0 ? COL.lime : COL.dn; g.fillRect(x, y, bw, bh);
        g.strokeStyle = "rgba(0,0,0,.22)"; g.lineWidth = 2;
        for (var k = -bh; k < bw + bh; k += 6) { g.beginPath(); g.moveTo(x + k, y + bh); g.lineTo(x + k + bh, y); g.stroke(); }
        g.restore();
      } else {
        g.fillStyle = COL.bar; rr(g, x, y, bw, bh, bw / 2); g.fill();
      }
      g.fillStyle = it.v >= 0 ? COL.lime : COL.dn;
      g.beginPath(); g.arc(cx, it.v >= 0 ? y + 5 : y + bh - 5, 2.4, 0, 6.2832); g.fill();
      g.fillStyle = i === sel ? "#fff" : COL.tx;
      var lb = String(it.label == null ? "" : it.label);
      g.fillText(lb, cx - g.measureText(lb).width / 2, h - 5);
    }
    var si = items[sel], sx = padL + sel * slot + slot / 2, sy = si.v >= 0 ? Y(si.v) : Y(0) - 4;
    tip(g, w, o.fmt ? o.fmt(si.v) : Q.n(si.v, 2), sx, Math.max(2, Math.min(sy - 30, h - padB - 24)));
  }

  /* ---------- candles ---------- */
  C.candles = function (cv, candles, lines, opt) {
    if (!cv) return;
    cv._d = { k: "candles", c: candles || [], lines: lines || [], opt: opt || {} };
    bind(cv); draw(cv);
  };
  function drawCandles(cv) {
    var s = setup(cv), g = s.g, w = s.w, h = s.h, d = cv._d, all = d.c, lines = d.lines;
    if (all.length < 3) { g.fillStyle = COL.tx; g.fillText(d.opt.empty || "", 8, h / 2); return; }
    var n = Math.min(all.length, d.opt.n || 70), c = all.slice(all.length - n);
    var padR = 58, padT = 26, padB = 8, pw = w - padR, ph = h - padT - padB, i;
    var mn = Infinity, mx = -Infinity;
    for (i = 0; i < c.length; i++) { mn = Math.min(mn, c[i].low); mx = Math.max(mx, c[i].high); }
    var span = mx - mn || 1;
    for (i = 0; i < lines.length; i++) {
      var p = lines[i].price;
      if (p > mn - span * 0.6 && p < mx + span * 0.6) { mn = Math.min(mn, p); mx = Math.max(mx, p); }
    }
    span = mx - mn || 1; mn -= span * 0.04; mx += span * 0.04; span = mx - mn;
    function Y(v) { return padT + (1 - (v - mn) / span) * ph; }
    var cw = pw / c.length;
    g.strokeStyle = COL.grid; g.lineWidth = 1; g.fillStyle = COL.tx;
    for (i = 0; i < 5; i++) {
      var gy = padT + (ph * i) / 4; g.beginPath(); g.moveTo(0, gy); g.lineTo(pw, gy); g.stroke();
      g.fillText(Q.price(mx - (span * i) / 4), pw + 4, gy + 3);
    }
    for (i = 0; i < c.length; i++) {
      var k = c[i], x = i * cw + cw / 2, col = k.close >= k.open ? COL.lime : COL.dn;
      g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x, Y(k.high)); g.lineTo(x, Y(k.low)); g.stroke();
      var top = Y(Math.max(k.open, k.close)), bh = Math.max(1, Math.abs(Y(k.open) - Y(k.close)));
      g.fillRect(x - Math.max(1, cw * 0.36), top, Math.max(2, cw * 0.72), bh);
    }
    for (i = 0; i < lines.length; i++) {
      var L = lines[i], ly = Y(L.price);
      if (ly < padT - 2 || ly > h - padB + 2) continue;
      g.strokeStyle = L.color; g.fillStyle = L.color; g.lineWidth = 1; g.setLineDash([5, 4]);
      g.beginPath(); g.moveTo(0, ly); g.lineTo(pw, ly); g.stroke(); g.setLineDash([]);
      g.fillText(L.label, 4, ly - 3);
    }
    var last = c[c.length - 1], lc = last.close >= last.open ? COL.lime : COL.dn, lyy = Y(last.close);
    g.strokeStyle = lc; g.setLineDash([2, 3]); g.beginPath(); g.moveTo(0, lyy); g.lineTo(pw, lyy); g.stroke(); g.setLineDash([]);
    g.fillStyle = lc; g.fillRect(pw, lyy - 8, padR, 16); g.fillStyle = "#000"; g.fillText(Q.price(last.close), pw + 3, lyy + 3);
    if (cv._x != null) {
      var idx = Math.max(0, Math.min(c.length - 1, Math.floor(cv._x / cw))), q = c[idx], cx = idx * cw + cw / 2;
      g.strokeStyle = "rgba(255,255,255,.35)"; g.beginPath(); g.moveTo(cx, padT); g.lineTo(cx, h - padB); g.stroke();
      tip(g, w, "O " + Q.price(q.open) + "  H " + Q.price(q.high) + "  L " + Q.price(q.low) + "  C " + Q.price(q.close), cx);
    }
  }

  /* ---------- SVG helpers ---------- */
  C.ring = function (pct, color, center, sub) {
    pct = Math.max(0, Math.min(100, Number(pct) || 0));
    var R = 42, len = 2 * Math.PI * R;
    return '<svg viewBox="0 0 100 100" class="ring" role="img" aria-label="' + Q.esc(center) + '"><circle cx="50" cy="50" r="42" class="ring-bg"/><circle cx="50" cy="50" r="42" class="ring-fg" style="stroke:' +
      color + ";stroke-dasharray:" + len.toFixed(1) + ";stroke-dashoffset:" + (len * (1 - pct / 100)).toFixed(1) + '"/><text x="50" y="55" class="ring-t">' +
      Q.esc(center) + "</text>" + (sub ? '<text x="50" y="70" class="ring-s">' + Q.esc(sub) + "</text>" : "") + "</svg>";
  };
  C.arcs = function (items, label) {                       // concentric half-circles, outermost first (reference: allocation / rebalance)
    var cx = 100, cy = 100, out = "";
    items.forEach(function (it, i) {
      var R = 84 - i * 21, pct = Math.max(0, Math.min(100, Number(it.pct) || 0));
      var a = Math.PI * (1 - pct / 100), dx = cx + R * Math.cos(a), dy = cy - R * Math.sin(a);
      var lx = Math.max(14, Math.min(186, cx + (R + 15) * Math.cos(a))), ly = Math.max(10, cy - (R + 15) * Math.sin(a) + 3);
      var d = "M " + (cx - R) + " " + cy + " A " + R + " " + R + " 0 0 1 " + (cx + R) + " " + cy;
      out += '<path class="tk" stroke-width="13" d="' + d + '"/>';
      if (pct < 0.5) return;                                // an empty arc draws nothing (a zero dash with round caps paints a dot)
      out += '<path class="fg" pathLength="100" stroke="' + it.color + '" stroke-width="13" stroke-dasharray="' + pct.toFixed(2) + ' 1000" d="' + d + '"/>' +   // gap > path: the pattern never repeats
        '<circle cx="' + dx.toFixed(1) + '" cy="' + dy.toFixed(1) + '" r="4.5" fill="#000" stroke="' + it.color + '" stroke-width="2.5"/>' +
        '<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="middle">' + Math.round(pct) + "%</text>";
    });
    return '<svg viewBox="0 0 200 112" class="gauge" role="img" aria-label="' + Q.esc(label || "") + '">' + out + "</svg>";
  };
  C.bar = function (pct, color) {
    pct = Math.max(0, Math.min(100, Number(pct) || 0));
    return '<div class="bar"><i style="width:' + pct.toFixed(1) + "%;background:" + color + '"></i></div>';
  };
  C.spark = function (vals, color, w, h) {
    w = w || 120; h = h || 34;
    if (!vals || vals.length < 2) return "";
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), sp = mx - mn || 1;
    var pts = vals.map(function (v, i) { return ((i / (vals.length - 1)) * w).toFixed(1) + "," + (h - 3 - ((v - mn) / sp) * (h - 6)).toFixed(1); }).join(" ");
    return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" height="' + h + '" preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke="' + color +
      '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="' + pts + '"/></svg>';
  };
  (window.__mods = window.__mods || []).push("charts");
})();
