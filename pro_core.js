"use strict";
(function () {
  var I = window.QI18N || { en: {}, ar: {} };
  var Q = window.Q = {
    S: { lang: "ar", tab: "overview", ov: null, eq: [], eqr: "1d", tk: [], kl: [], sym: "BTCUSDT", tf: "15m",
         hist: null, sig: null, sys: null, hf: "all", sf: "all", sq: "", online: true },
    views: {}, charts: {}, _last: {}
  };
  try { var sl = localStorage.getItem("aiqx_lang"); if (sl === "en" || sl === "ar") Q.S.lang = sl; } catch (e) {}

  Q.t = function (k) { return (I[Q.S.lang] && I[Q.S.lang][k]) || (I.en && I.en[k]) || k; };
  Q.$ = function (id) { return document.getElementById(id); };
  Q.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  function fmt(v, d) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  Q.n = function (v, d) { return fmt(v, d == null ? 2 : d); };
  Q.sg = function (v, d) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    return (v > 0 ? "+" : v < 0 ? "-" : "") + fmt(Math.abs(v), d == null ? 2 : d);
  };
  Q.price = function (v) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    var a = Math.abs(v);
    return fmt(v, a >= 1000 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 5 : 8);
  };
  Q.cls = function (v) { return v > 0 ? "up" : v < 0 ? "down" : "flat"; };
  Q.dur = function (sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    if (sec < 60) return sec + Q.t("sec");
    if (sec < 3600) return Math.floor(sec / 60) + Q.t("min");
    if (sec < 86400) return Math.floor(sec / 3600) + Q.t("hours") + " " + Math.floor((sec % 3600) / 60) + Q.t("min");
    return Math.floor(sec / 86400) + "d " + Math.floor((sec % 86400) / 3600) + Q.t("hours");
  };
  Q.ago = function (ts) {
    if (!ts) return "-";
    var now = Q.S.ov && Q.S.ov.now ? Q.S.ov.now : Math.floor(Date.now() / 1000);
    return Q.dur(now - ts);
  };
  Q.paint = function (id, html) {
    var el = Q.$(id);
    if (!el) return;
    if (el._h !== html) { el.innerHTML = html; el._h = html; }
  };
  Q.every = async function (key, ms, fn) {
    var now = Date.now();
    if (Q._last[key] && now - Q._last[key] < ms) return;
    Q._last[key] = now;
    try { await fn(); } catch (e) { Q.S.err = String(e && e.message || e); }
  };
  Q.api = async function (path, opt) {
    var r = await fetch(path, Object.assign({ credentials: "same-origin", cache: "no-store" }, opt || {}));
    if (r.status === 401) { location.href = "/login"; throw new Error("unauthorized"); }
    var j = null;
    try { j = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error((j && (j.error || j.detail)) || ("HTTP " + r.status));
    return j;
  };
  Q.toast = function (msg, kind) {
    var el = Q.$("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "show" + (kind === "err" ? " err" : "");
    clearTimeout(Q._tt);
    Q._tt = setTimeout(function () { el.className = ""; }, 2600);
  };
  Q.sheet = function (title, body, actions) {
    var s = Q.$("sheet");
    s.innerHTML = '<div class="sh-back" id="sh-back"></div><div class="sh-box"><div class="sh-grip"></div><h3>' +
      Q.esc(title) + '</h3><div class="sh-body">' + Q.esc(body) + '</div><div class="sh-act" id="sh-act"></div></div>';
    var box = Q.$("sh-act");
    (actions || [{ label: Q.t("cancel") }]).forEach(function (a) {
      var b = document.createElement("button");
      b.className = "btn " + (a.kind || "");
      b.textContent = a.label;
      b.addEventListener("click", function () { Q.closeSheet(); if (a.fn) a.fn(); });
      box.appendChild(b);
    });
    Q.$("sh-back").addEventListener("click", Q.closeSheet);
    s.className = "open";
  };
  Q.closeSheet = function () { var s = Q.$("sheet"); if (s) { s.className = ""; s.innerHTML = ""; } };

  var ICON = {
    overview: '<path d="M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10"/>',
    positions: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
    history: '<path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.4M3 4v4h4M12 7v5l3 2"/>',
    signals: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    tools: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 00-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 00-2-1.2L14 3h-4l-.6 2.7a7 7 0 00-2 1.2l-2.3-1-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 002 1.2L10 21h4l.6-2.7a7 7 0 002-1.2l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"/>',
    pause: '<path d="M8 5v14M16 5v14"/>', play: '<path d="M7 4l13 8-13 8z"/>', lang: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>'
  };
  Q.icon = function (k) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + ICON[k] + "</svg>";
  };

  var TABS = ["overview", "positions", "history", "signals", "tools"];
  Q.drawNav = function () {
    var n = Q.S.ov && Q.S.ov.positions ? Q.S.ov.positions.length : 0;
    Q.paint("tabs", TABS.map(function (k) {
      return '<button class="tab' + (Q.S.tab === k ? " on" : "") + '" data-tab="' + k + '">' + Q.icon(k) +
        "<span>" + Q.t("nav_" + k) + "</span>" + (k === "positions" && n ? '<span class="bd">' + n + "</span>" : "") + "</button>";
    }).join(""));
  };
  Q.drawTop = function () {
    var ov = Q.S.ov, st = ov && ov.status, state = "off", label = Q.t("offline");
    if (Q.S.online && st) { state = st.paused ? "off" : (st.running ? "on" : "bad"); label = st.paused ? Q.t("paused") : (st.running ? Q.t("running") : Q.t("offline")); }
    else if (Q.S.online) { label = "..."; }
    else { state = "bad"; }
    var paused = st && st.paused;
    Q.paint("top",
      '<span class="brand">AI QUANT <b>X</b></span><span class="pill ' + state + '"><i class="dot"></i>' + label + "</span>" +
      '<span class="sp"></span>' +
      '<button class="ib" data-act="lang" aria-label="language">' + Q.icon("lang") + "</button>" +
      '<button class="ib" data-act="pause" aria-label="pause">' + Q.icon(paused ? "play" : "pause") + "</button>");
  };
  Q.setLang = function (l) {
    Q.S.lang = l;
    try { localStorage.setItem("aiqx_lang", l); } catch (e) {}
    document.documentElement.lang = l;
    document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
    Q.drawNav(); Q.drawTop();
    Q.go(Q.S.tab);
  };
  Q.togglePause = async function () {
    try {
      var r = await Q.api("/api/toggle_pause", { method: "POST" });
      Q.toast(r.paused ? Q.t("paused") : Q.t("running"));
      await Q.refresh();
    } catch (e) { Q.toast(e.message, "err"); }
  };
  Q.refresh = async function () {
    if (Q._busy) return;
    Q._busy = true;
    try { Q.S.ov = await Q.api("/api/pro/overview"); Q.S.online = true; Q.S.err = ""; }
    catch (e) { Q.S.online = false; Q.S.err = String(e && e.message || e); }
    try { var v = Q.views[Q.S.tab]; if (v && v.load) await v.load(); } catch (e) { Q.S.err = String(e && e.message || e); }
    try { Q.drawTop(); Q.drawNav(); var w = Q.views[Q.S.tab]; if (w) w.update(); } catch (e) { if (window.console) console.error(e); }
    Q._busy = false;
  };
  Q.go = async function (tab) {
    if (!Q.views[tab]) tab = "overview";
    Q.S.tab = tab;
    Q._last = {};
    try { history.replaceState(null, "", "#" + tab); } catch (e) {}
    Q.drawNav();
    var root = Q.$("view");
    root.innerHTML = "";
    root._h = null;
    Q.views[tab].mount(root);
    try { window.scrollTo(0, 0); } catch (e) {}
    Q._busy = false;
    await Q.refresh();
  };
  Q.start = function () {
    document.documentElement.lang = Q.S.lang;
    document.documentElement.dir = Q.S.lang === "ar" ? "rtl" : "ltr";
    Q.$("tabs").addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("[data-tab]") : null;
      if (b) Q.go(b.getAttribute("data-tab"));
    });
    Q.$("top").addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("[data-act]") : null;
      if (!b) return;
      var a = b.getAttribute("data-act");
      if (a === "pause") Q.togglePause();
      if (a === "lang") Q.setLang(Q.S.lang === "ar" ? "en" : "ar");
    });
    var h = (location.hash || "").slice(1);
    Q.drawTop(); Q.drawNav();
    Q.go(TABS.indexOf(h) >= 0 ? h : "overview");
    setInterval(function () { if (document.visibilityState !== "hidden") Q.refresh(); }, 4000);
  };
  (window.__mods = window.__mods || []).push("core");
})();
