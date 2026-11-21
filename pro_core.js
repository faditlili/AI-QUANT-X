"use strict";
(function () {
  var I = window.QI18N || { en: {}, ar: {} };
  var Q = window.Q = {
    S: { lang: "ar", tab: "overview", ov: null, eq: [], eqr: "1d", tk: [], kl: [], sym: "BTCUSDT", tf: "15m", hist: null, sig: null, sys: null,
         hf: "all", sf: "all", sq: "", hq: "", online: true, t: 0, err: "", name: "Fedi Tl", avatar: "", open: {}, mq: "", ms: "volume", sg: "all" },
    views: {}, charts: {}, _last: {}
  };
  var DEFAULT_NAME = "Fedi Tl", AVATAR_RE = /^data:image\/jpeg;base64,[A-Za-z0-9+\/=]+$/;
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); return true; } catch (e) { return false; } }
  var sl = lsGet("aiqx_lang"); if (sl === "en" || sl === "ar") Q.S.lang = sl;
  var sn = lsGet("aiqx_name"); if (sn && sn.trim()) Q.S.name = sn.trim().slice(0, 24);
  var sa = lsGet("aiqx_avatar"); if (sa && AVATAR_RE.test(sa)) Q.S.avatar = sa;

  Q.t = function (k) { return (I[Q.S.lang] && I[Q.S.lang][k]) || (I.en && I.en[k]) || k; };
  Q.$ = function (id) { return document.getElementById(id); };
  Q.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  };
  function fmt(v, d) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  Q.n = function (v, d) { return fmt(v, d == null ? 2 : d); };
  Q.sg = function (v, d) { v = Number(v); if (!isFinite(v)) return "-"; return (v > 0 ? "+" : v < 0 ? "-" : "") + fmt(Math.abs(v), d == null ? 2 : d); };
  Q.price = function (v) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    var a = Math.abs(v);
    return fmt(v, a >= 1000 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 5 : 8);
  };
  Q.compact = function (v) {
    v = Number(v);
    if (!isFinite(v)) return "-";
    var a = Math.abs(v);
    return a >= 1e9 ? fmt(v / 1e9, 2) + "B" : a >= 1e6 ? fmt(v / 1e6, 1) + "M" : a >= 1e3 ? fmt(v / 1e3, 1) + "K" : fmt(v, 0);
  };
  Q.cls = function (v) { return v > 0 ? "up" : v < 0 ? "down" : "flat"; };
  Q.dur = function (sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    if (sec < 60) return sec + Q.t("sec");
    if (sec < 3600) return Math.floor(sec / 60) + Q.t("min");
    if (sec < 86400) return Math.floor(sec / 3600) + Q.t("hours") + " " + Math.floor((sec % 3600) / 60) + Q.t("min");
    return Math.floor(sec / 86400) + "d " + Math.floor((sec % 86400) / 3600) + Q.t("hours");
  };
  Q.now = function () { return Q.S.ov && Q.S.ov.now ? Q.S.ov.now : Math.floor(Date.now() / 1000); };
  Q.ago = function (ts) { return ts ? Q.dur(Q.now() - ts) : "-"; };
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

  /* ---------- icons ---------- */
  var ICON = {
    overview: '<path d="M3 11.5L12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>',
    markets: '<path d="M7 3v4M7 17v4M17 5v3M17 18v3"/><rect x="5" y="7" width="4" height="10" rx="1.2"/><rect x="15" y="8" width="4" height="10" rx="1.2"/>',
    signals: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    positions: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    more: '<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="2"/>',
    bell: '<path d="M6 16.5V11a6 6 0 1112 0v5.5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 004 0"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 00-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 00-2-1.2L14 3h-4l-.6 2.7a7 7 0 00-2 1.2l-2.3-1-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 002 1.2L10 21h4l.6-2.7a7 7 0 002-1.2l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"/>',
    arrow: '<path d="M7 17L17 7M8.5 7H17v8.5"/>', back: '<path d="M15 5l-7 7 7 7"/>', chev: '<path d="M6 9l6 6 6-6"/>',
    pause: '<path d="M8 5v14M16 5v14"/>', play: '<path d="M7 4l13 8-13 8z"/>',
    lang: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    history: '<path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.4M3 4v4h4M12 7v5l3 2"/>',
    analytics: '<path d="M5 20V11M12 20V5M19 20v-7"/>', health: '<path d="M3 12h4l2.5-6 4 12 2.5-6h5"/>',
    tools: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    camera: '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    trash: '<path d="M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4.5M12 17.5v.5"/>',
    wallet: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M16 12.5h2.5M3 10h18"/>',
    shield: '<path d="M12 3l7.5 3v5.5c0 4.5-3 7.5-7.5 9.5-4.5-2-7.5-5-7.5-9.5V6z"/>',
    chart: '<path d="M3 17l5-6 4 3 8-9"/>',
    db: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    send: '<path d="M21 4L3 11l6 2.5L11.5 20l3-4.5L19 18z"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="3"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    scan: '<circle cx="12" cy="12" r="9"/><path d="M12 12l5-5"/>'
  };
  Q.icon = function (k) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICON[k] || "") + "</svg>";
  };
  /* section header in the reference layout: title pill + round arrow button */
  Q.head = function (icon, title, go) {
    return '<div class="shd"><div class="pillh"><span class="ci">' + Q.icon(icon) + '</span><span class="t">' + Q.esc(title) + "</span></div>" +
      (go ? '<button class="go" data-go="' + go + '" aria-label="' + Q.esc(title) + '">' + Q.icon("arrow") + "</button>" : "") + "</div>";
  };
  Q.empty = function (icon, text) { return '<div class="empty"><div class="ico">' + Q.icon(icon) + "</div>" + Q.esc(text) + "</div>"; };
  Q.wait = function () {                                    // skeleton while loading, error card (with retry) when the API is unreachable
    if (Q.S.online === false && !Q.S.ov) {
      return '<div class="err">' + Q.esc(Q.t("err_load")) + (Q.S.err ? ": " + Q.esc(Q.S.err) : "") +
        '</div><button class="btn pri blk" data-act="retry">' + Q.esc(Q.t("retry")) + "</button>";
    }
    return '<div class="skc"></div><div class="skc" style="height:90px"></div><div class="skc"></div>';
  };

  /* ---------- sheets ---------- */
  Q.sheetHtml = function (title, html, actions, rich) {
    var s = Q.$("sheet");
    s.innerHTML = '<div class="sh-back" id="sh-back"></div><div class="sh-box" role="dialog" aria-modal="true"><div class="sh-grip"></div><h3>' +
      Q.esc(title) + '</h3><div class="sh-body' + (rich ? " rich" : "") + '" id="sh-body">' + html + '</div><div class="sh-act" id="sh-act"></div></div>';
    var box = Q.$("sh-act");
    (actions || [{ label: Q.t("cancel") }]).forEach(function (a) {
      var b = document.createElement("button");
      b.className = "btn " + (a.kind || "");
      b.textContent = a.label;
      b.addEventListener("click", function () { if (a.keep) { if (a.fn) a.fn(); return; } Q.closeSheet(); if (a.fn) a.fn(); });
      box.appendChild(b);
    });
    Q.$("sh-back").addEventListener("click", Q.closeSheet);
    s.className = "open";
  };
  Q.sheet = function (title, body, actions) { Q.sheetHtml(title, Q.esc(body), actions, false); };
  Q.closeSheet = function () { var s = Q.$("sheet"); if (s) { s.className = ""; s.innerHTML = ""; } };

  /* ---------- profile: name and photo live only in this browser ---------- */
  Q.initials = function () {
    var p = String(Q.S.name || DEFAULT_NAME).trim().split(/\s+/).slice(0, 2);
    return p.map(function (w) { return w.charAt(0).toUpperCase(); }).join("") || "FT";
  };
  Q.avatar = function (cls) {
    return '<span class="av ' + (cls || "") + '">' + (Q.S.avatar && AVATAR_RE.test(Q.S.avatar) ? '<img alt="" src="' + Q.S.avatar + '">' : Q.esc(Q.initials())) + "</span>";
  };
  Q.saveProfile = function (name, avatar) {
    name = String(name || "").trim().slice(0, 24) || DEFAULT_NAME;
    Q.S.name = name; lsSet("aiqx_name", name);
    if (avatar !== undefined) {
      if (avatar && !AVATAR_RE.test(avatar)) avatar = "";   // never store or render anything but our own JPEG data URL
      Q.S.avatar = avatar || "";
      if (!lsSet("aiqx_avatar", avatar || null) && avatar) Q.toast(Q.t("photo_big"), "err");
    }
    Q.drawTop();
  };
  Q.cropPhoto = function (file, done) {
    if (!file || !/^image\//.test(file.type) || file.size > 12 * 1024 * 1024) { done(null); return; }
    var fr = new FileReader();
    fr.onerror = function () { done(null); };
    fr.onload = function () {
      var img = new Image();
      img.onerror = function () { done(null); };
      img.onload = function () {
        var c = document.createElement("canvas"), g, s = Math.min(img.width, img.height);
        c.width = c.height = 192; g = c.getContext("2d");
        g.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, 192, 192);
        done(c.toDataURL("image/jpeg", 0.86));
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  };
  Q.profileSheet = function () {
    var pending;                                            // undefined = keep, "" = remove, data URL = new photo
    Q.sheetHtml(Q.t("profile"),
      '<div style="text-align:center" id="pf-av">' + Q.avatar("xl") + '</div>' +
      '<div class="field"><input id="pf-name" maxlength="24" autocomplete="off" aria-label="' + Q.esc(Q.t("your_name")) + '" value="' + Q.esc(Q.S.name) + '"></div>' +
      '<input id="pf-file" type="file" accept="image/*" hidden>' +
      '<div class="mu" style="font-size:12px;margin-top:6px">' + Q.esc(Q.t("photo_note")) + "</div>",
      [
        { label: Q.t("choose_photo"), kind: "pri", keep: true, fn: function () { Q.$("pf-file").click(); } },
        { label: Q.t("remove_photo"), keep: true, fn: function () { pending = ""; Q.$("pf-av").innerHTML = '<span class="av xl">' + Q.esc(Q.initials()) + "</span>"; } },
        { label: Q.t("save"), kind: "pri", keep: true, fn: function () {          // read the fields first: closing the sheet empties it
          var name = Q.$("pf-name") ? Q.$("pf-name").value : Q.S.name;
          Q.saveProfile(name, pending);
          Q.closeSheet();
        } }
      ], true);
    Q.$("pf-file").addEventListener("change", function (e) {
      var f = e.target.files && e.target.files[0];
      Q.cropPhoto(f, function (url) {
        if (!url) { Q.toast(Q.t("photo_bad"), "err"); return; }
        pending = url;
        Q.$("pf-av").innerHTML = '<span class="av xl"><img alt="" src="' + url + '"></span>';
      });
    });
  };

  /* ---------- alerts: derived only from real engine / risk / system state ---------- */
  Q.alerts = function () {
    var out = [], ov = Q.S.ov, st = ov && ov.status, rk = ov && ov.risk, sys = Q.S.sys;
    if (!Q.S.online) out.push({ k: "bad", t: Q.t("al_offline"), x: Q.S.err || "" });
    if (st) {
      if (st.paused) out.push({ k: "warn", t: Q.t("al_paused"), x: Q.t("al_paused_x") });
      if (st.data_ok === false) out.push({ k: "bad", t: Q.t("al_data"), x: st.data_reason || "" });
      if (st.last_error) out.push({ k: "warn", t: Q.t("al_error"), x: String(st.last_error) });
      if (!st.ws_connected && Q.S.online) out.push({ k: "info", t: Q.t("al_ws"), x: Q.t("al_ws_x") });
      var every = sys && sys.scan_every;
      if (every && st.last_scan && ov.now - st.last_scan > every * 3 + 60) out.push({ k: "warn", t: Q.t("al_scan"), x: Q.dur(ov.now - st.last_scan) + " " + Q.t("ago") });
    }
    if (rk && rk.daily_limit_hit) out.push({ k: "bad", t: Q.t("al_daily"), x: Q.t("limit_hit") });
    if (sys && sys.protection && sys.protection.blocked) out.push({ k: "bad", t: Q.t("protection"), x: sys.protection.reason });
    if (sys && sys.storage && sys.storage.fallback_used) out.push({ k: "warn", t: Q.t("al_storage"), x: Q.t("al_storage_x") });
    return out;
  };
  Q.alertsSheet = function () {
    var a = Q.alerts();
    Q.sheetHtml(Q.t("notifications"), a.length ? a.map(function (x) {
      return '<div class="al"><span class="st ' + (x.k === "bad" ? "bad" : x.k === "warn" ? "off" : "") + '" style="margin-top:5px"></span><div><b>' + Q.esc(x.t) + "</b><small>" + Q.esc(x.x) + "</small></div></div>";
    }).join("") : Q.empty("check", Q.t("all_clear_n")), [{ label: Q.t("close") }], true);
  };

  /* ---------- header, status strip, navigation ---------- */
  var TABS = ["overview", "markets", "signals", "positions", "more"];
  var SUBS = { history: 1, analytics: 1, health: 1, tools: 1, settings: 1 };
  Q.navOf = function (tab) { return SUBS[tab] ? "more" : tab; };
  Q.drawNav = function () {
    var n = Q.S.ov && Q.S.ov.positions ? Q.S.ov.positions.length : 0, cur = Q.navOf(Q.S.tab);
    Q.paint("tabs", TABS.map(function (k) {
      return '<button class="tab' + (cur === k ? " on" : "") + '" data-tab="' + k + '" aria-label="' + Q.esc(Q.t("nav_" + k)) + '"' + (cur === k ? ' aria-current="page"' : "") + ">" + Q.icon(k) +
        '<span class="l">' + Q.t("nav_" + k) + "</span>" + (k === "positions" && n ? '<span class="bd">' + n + "</span>" : "") + "</button>";
    }).join(""));
  };
  Q.strip = function () {
    var ov = Q.S.ov, st = ov && ov.status, cls = "off", label = "...";
    if (!Q.S.online) { cls = "bad"; label = Q.t("offline"); }
    else if (st) { cls = st.paused ? "off" : (st.running ? "on" : "bad"); label = st.paused ? Q.t("paused") : (st.running ? Q.t("running") : Q.t("offline")); }
    var comp = st && st.compass ? (st.compass.futures || st.compass.spot || "") : "", mk = "";
    if (comp) mk = '<span class="sc ' + (comp === "BULLISH" ? "on" : comp === "BEARISH" ? "bad" : "") + '">' + (comp === "BULLISH" ? "&#9650; " : comp === "BEARISH" ? "&#9660; " : "&#9670; ") + Q.t(comp.toLowerCase()) + "</span>";
    var feed = !Q.S.online ? '<span class="sc bad"><i class="dot"></i>' + Q.t("no_link") + "</span>"
      : (st && st.ws_connected ? '<span class="sc on"><i class="dot"></i>' + Q.t("feed_ws") + "</span>" : '<span class="sc off"><i class="dot"></i>' + Q.t("feed_rest") + "</span>");
    var upd = Q.S.t ? Math.max(0, Math.round((Date.now() - Q.S.t) / 1000)) : null;
    return '<span class="sc ' + cls + '"><i class="dot"></i>' + label + "</span>" + mk + feed +
      '<span class="sc num">' + (Q._busy ? '<i class="spin" style="width:10px;height:10px"></i>' : "&#8635;") + " " + (upd == null ? "-" : upd + Q.t("sec")) + "</span>" +
      '<span class="sc paper">' + Q.t("paper_s") + "</span>";
  };
  Q.drawTop = function () {
    var n = Q.alerts().filter(function (a) { return a.k !== "info"; }).length;
    Q.paint("top",
      '<div class="hrow"><div class="hi"><small>' + Q.t("welcome") + "</small><b>" + Q.t("hi") + " " + Q.esc(Q.S.name) + "</b></div>" +
      '<button class="ib" data-act="bell" aria-label="' + Q.esc(Q.t("notifications")) + '">' + Q.icon("bell") + (n ? '<i class="bdg"></i>' : "") + "</button>" +
      '<button class="ib" data-act="settings" aria-label="' + Q.esc(Q.t("settings")) + '">' + Q.icon("gear") + "</button>" +
      '<button class="av" data-act="profile" aria-label="' + Q.esc(Q.t("profile")) + '">' + (Q.S.avatar && AVATAR_RE.test(Q.S.avatar) ? '<img alt="" src="' + Q.S.avatar + '">' : Q.esc(Q.initials())) + "</button></div>" +
      '<div id="strip"></div>');
    Q.tick();
  };
  Q.tick = function () { Q.paint("strip", Q.strip()); };
  Q.drawSub = function () {
    Q.paint("sub", SUBS[Q.S.tab]
      ? '<div class="back"><button class="go" data-act="back" aria-label="' + Q.esc(Q.t("back")) + '">' + Q.icon("back") + "</button><b>" + Q.esc(Q.t("sub_" + Q.S.tab)) + "</b></div>" : "");
  };
  Q.setLang = function (l) {
    Q.S.lang = l; lsSet("aiqx_lang", l);
    document.documentElement.lang = l;
    document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
    Q._h = null; Q.$("top")._h = null; Q.$("tabs")._h = null;
    Q.drawNav(); Q.drawTop(); Q.go(Q.S.tab);
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
    try {
      try { Q.S.ov = await Q.api("/api/pro/overview"); Q.S.online = true; Q.S.err = ""; Q.S.t = Date.now(); }
      catch (e) { Q.S.online = false; Q.S.err = String(e && e.message || e); }
      await Q.every("sys", 30000, async function () { Q.S.sys = await Q.api("/api/pro/system"); });
      try { var v = Q.views[Q.S.tab]; if (v && v.load) await v.load(); } catch (e) { Q.S.err = String(e && e.message || e); }
      try { Q.drawTop(); Q.drawNav(); Q.drawSub(); var w = Q.views[Q.S.tab]; if (w) w.update(); } catch (e) { if (window.console) console.error(e); }
    } finally { Q._busy = false; Q.tick(); }
  };
  Q.go = async function (tab) {
    if (!Q.views[tab]) tab = "overview";
    Q.S.tab = tab;
    Q._last = {};
    try { history.replaceState(null, "", "#" + tab); } catch (e) {}
    Q.drawNav(); Q.drawSub();
    var root = Q.$("view");
    root.innerHTML = ""; root._h = null; root.onclick = null; root.oninput = null;
    root.className = ""; try { void root.offsetWidth; } catch (e) {}
    root.className = "vin";
    Q.views[tab].mount(root);
    try { window.scrollTo(0, 0); } catch (e) {}
    Q._busy = false;
    await Q.refresh();
  };
  Q.start = function () {
    document.documentElement.lang = Q.S.lang;
    document.documentElement.dir = Q.S.lang === "ar" ? "rtl" : "ltr";
    document.addEventListener("click", function (e) {      // ONE delegated listener for the whole app
      var t = e.target && e.target.closest ? e.target : null;
      if (!t) return;
      var b = t.closest("[data-tab]");
      if (b) { Q.go(b.getAttribute("data-tab")); return; }
      b = t.closest("[data-go]");
      if (b) { Q.go(b.getAttribute("data-go")); return; }
      b = t.closest("[data-act]");
      if (!b) return;
      var a = b.getAttribute("data-act");
      if (a === "pause") Q.togglePause();
      else if (a === "lang") Q.setLang(Q.S.lang === "ar" ? "en" : "ar");
      else if (a === "bell") Q.alertsSheet();
      else if (a === "settings") Q.go("settings");
      else if (a === "profile") Q.profileSheet();
      else if (a === "back") Q.go("more");
      else if (a === "retry") Q.refresh();
    });
    var h = (location.hash || "").slice(1);
    Q.drawTop(); Q.drawNav();
    Q.go(Q.views[h] ? h : "overview");
    setInterval(function () { if (document.visibilityState !== "hidden") Q.refresh(); }, 4000);
    setInterval(function () { if (document.visibilityState !== "hidden") Q.tick(); }, 1000);
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") Q.refresh(); });
  };
  Q.views_list = function () { return Object.keys(Q.views); };
  (window.__mods = window.__mods || []).push("core");
})();
