<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#02030a">
<title>AI QUANT X | Command Deck</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#02030a; --bg2:#070a18;
  --cyan:#00f3ff; --cyan-rgb:0,243,255;
  --purple:#b026ff; --purple-rgb:176,38,255;
  --up:#00ffa3; --up-rgb:0,255,163;
  --down:#ff3b6b; --down-rgb:255,59,107;
  --warn:#ffb020;
  --text:#e6f1ff; --muted:#7f8db0;
  --glass:rgba(12,16,38,.55);
  --radius:20px;
  --font-display:'Orbitron',sans-serif;
  --font-mono:'Share Tech Mono',ui-monospace,monospace;
  --font-body:'Inter',system-ui,sans-serif;
  --glow-cyan:0 0 14px rgba(0,243,255,.55);
  --glow-purple:0 0 14px rgba(176,38,255,.55);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{background:var(--bg)}
body{
  margin:0;min-height:100vh;color:var(--text);font-family:var(--font-body);
  background:
    radial-gradient(1100px 560px at 85% -10%,rgba(var(--purple-rgb),.18),transparent 60%),
    radial-gradient(900px 500px at -10% 8%,rgba(var(--cyan-rgb),.13),transparent 55%),
    var(--bg);
  padding-bottom:calc(92px + env(safe-area-inset-bottom,0px));
  overflow-x:hidden;
}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(var(--cyan-rgb),.045) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--cyan-rgb),.045) 1px,transparent 1px);
  background-size:38px 38px;
  -webkit-mask-image:radial-gradient(ellipse at 50% 0%,#000 15%,transparent 72%);
  mask-image:radial-gradient(ellipse at 50% 0%,#000 15%,transparent 72%);
}
.orb{position:fixed;border-radius:50%;filter:blur(90px);pointer-events:none;z-index:0;opacity:.35}
.orb.o1{width:260px;height:260px;background:var(--purple);top:30%;left:-90px;animation:drift 14s ease-in-out infinite}
.orb.o2{width:240px;height:240px;background:var(--cyan);bottom:5%;right:-90px;animation:drift 18s ease-in-out infinite reverse}
@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(40px,-60px)}}

.mono{font-family:var(--font-mono)}
.hidden{display:none!important}
.wrap{position:relative;z-index:1;max-width:720px;margin:0 auto;padding:14px 12px 0}

/* ---------- top bar ---------- */
.nav{position:sticky;top:0;z-index:40;padding-top:env(safe-area-inset-top,0px);
  background:linear-gradient(to bottom,rgba(2,3,10,.94),rgba(2,3,10,.62));
  backdrop-filter:blur(16px) saturate(150%);-webkit-backdrop-filter:blur(16px) saturate(150%)}
.nav-inner{max-width:720px;margin:0 auto;display:flex;align-items:center;gap:8px;padding:10px 12px}
.brand{display:flex;align-items:center;gap:6px;color:var(--cyan);font-family:var(--font-display);font-weight:900;
  letter-spacing:.08em;font-size:12px;text-shadow:var(--glow-cyan);white-space:nowrap}
.brand b{color:var(--purple);text-shadow:var(--glow-purple)}
.brand svg{width:18px;height:18px;filter:drop-shadow(0 0 6px var(--cyan))}
.nav-bal{margin-left:auto;display:flex;align-items:center;gap:5px;font-family:var(--font-mono);font-size:13px;
  padding:6px 10px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid rgba(var(--cyan-rgb),.18);white-space:nowrap}
.nav-bal svg{width:14px;height:14px;color:var(--cyan)}
.nav-actions{display:flex;gap:6px}
.nav-line{height:1px;background:linear-gradient(90deg,transparent,var(--cyan),var(--purple),transparent);opacity:.65;animation:pulseline 4s ease-in-out infinite}
@keyframes pulseline{0%,100%{opacity:.35}50%{opacity:.9}}

/* ---------- buttons ---------- */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:34px;padding:0 11px;border-radius:12px;
  font-family:var(--font-display);font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--cyan);cursor:pointer;
  background:linear-gradient(145deg,rgba(var(--cyan-rgb),.15),rgba(var(--cyan-rgb),.04));
  border:1px solid rgba(var(--cyan-rgb),.38);
  box-shadow:0 0 14px rgba(var(--cyan-rgb),.18),inset 0 1px 0 rgba(255,255,255,.12);
  transition:transform .15s,box-shadow .2s,opacity .2s;white-space:nowrap}
.btn:active{transform:scale(.94)}
.btn svg{width:15px;height:15px;flex:none}
.btn-purple{color:#ecd2ff;border-color:rgba(var(--purple-rgb),.55);
  background:linear-gradient(145deg,rgba(var(--purple-rgb),.28),rgba(var(--purple-rgb),.06));
  box-shadow:0 0 16px rgba(var(--purple-rgb),.32),inset 0 1px 0 rgba(255,255,255,.12)}
.btn-up{color:var(--up);border-color:rgba(var(--up-rgb),.45);background:linear-gradient(145deg,rgba(var(--up-rgb),.16),rgba(var(--up-rgb),.03));box-shadow:0 0 14px rgba(var(--up-rgb),.2),inset 0 1px 0 rgba(255,255,255,.1)}
.btn-down{color:var(--down);border-color:rgba(var(--down-rgb),.5);background:linear-gradient(145deg,rgba(var(--down-rgb),.18),rgba(var(--down-rgb),.03));box-shadow:0 0 14px rgba(var(--down-rgb),.22),inset 0 1px 0 rgba(255,255,255,.1)}
.btn[disabled]{opacity:.55;pointer-events:none}
.btn-wide{width:100%;height:40px;font-size:11px}
@media(max-width:380px){.btn .lbl{display:none}.btn{padding:0 10px}}

/* ---------- glass cards ---------- */
.glass{position:relative;overflow:hidden;border-radius:var(--radius);padding:16px;
  background:linear-gradient(145deg,rgba(255,255,255,.075),rgba(255,255,255,.012)),var(--glass);
  backdrop-filter:blur(20px) saturate(150%);-webkit-backdrop-filter:blur(20px) saturate(150%);
  border:1px solid rgba(var(--cyan-rgb),.16);
  box-shadow:0 24px 50px -14px rgba(0,0,0,.85),0 0 0 1px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.09),0 0 36px -14px rgba(var(--cyan-rgb),.35)}
.glass::before{content:'';position:absolute;left:12%;right:12%;top:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--cyan),var(--purple),transparent);opacity:.85}
.glass::after{content:'';position:absolute;left:0;right:0;top:-40%;height:40%;pointer-events:none;
  background:linear-gradient(to bottom,transparent,rgba(var(--cyan-rgb),.075),transparent);
  animation:scan 7s linear infinite}
@keyframes scan{from{transform:translateY(0)}to{transform:translateY(360%)}}
.glass.violet{border-color:rgba(var(--purple-rgb),.22);box-shadow:0 24px 50px -14px rgba(0,0,0,.85),0 0 0 1px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.09),0 0 36px -14px rgba(var(--purple-rgb),.45)}
.glass.violet::after{animation-delay:-3s}
.stack>*+*{margin-top:12px}

.label{display:flex;align-items:center;gap:6px;font-family:var(--font-display);font-size:10px;letter-spacing:.16em;color:var(--muted);text-transform:uppercase}
.label svg{width:13px;height:13px;color:var(--cyan)}
.chip{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:999px;font-family:var(--font-mono);font-size:11px;
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:var(--text)}
.chip svg{width:12px;height:12px}
.chip.cy{color:var(--cyan);border-color:rgba(var(--cyan-rgb),.35);background:rgba(var(--cyan-rgb),.08)}
.chip.pu{color:#d9a8ff;border-color:rgba(var(--purple-rgb),.4);background:rgba(var(--purple-rgb),.1)}
.chip.up{color:var(--up);border-color:rgba(var(--up-rgb),.4);background:rgba(var(--up-rgb),.09)}
.chip.dn{color:var(--down);border-color:rgba(var(--down-rgb),.45);background:rgba(var(--down-rgb),.09)}
.up{color:var(--up)} .dn{color:var(--down)} .muted{color:var(--muted)}

.big-num{display:flex;align-items:baseline;gap:6px;margin-top:8px;font-family:var(--font-mono);font-size:44px;line-height:1;
  color:#fff;text-shadow:0 0 22px rgba(var(--cyan-rgb),.55),0 0 2px rgba(var(--cyan-rgb),.8)}
.big-num .cur{font-size:22px;color:var(--cyan)}
.big-num .unit{font-family:var(--font-display);font-size:11px;letter-spacing:.14em;color:var(--muted);text-shadow:none}
.pnl-chip{display:inline-flex;align-items:center;gap:8px;margin-top:12px;padding:7px 12px;border-radius:14px;
  font-family:var(--font-mono);font-size:14px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.04)}
.pnl-chip svg{width:16px;height:16px}
.pnl-chip.up{border-color:rgba(var(--up-rgb),.5);background:rgba(var(--up-rgb),.1);box-shadow:0 0 18px rgba(var(--up-rgb),.22)}
.pnl-chip.dn{border-color:rgba(var(--down-rgb),.55);background:rgba(var(--down-rgb),.1);box-shadow:0 0 18px rgba(var(--down-rgb),.25)}

.stat{padding:10px;border-radius:14px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);min-width:0}
.stat .k{font-family:var(--font-display);font-size:8.5px;letter-spacing:.14em;color:var(--muted)}
.stat .v{margin-top:5px;font-family:var(--font-mono);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.bar{position:relative;height:8px;border-radius:99px;background:rgba(255,255,255,.07);overflow:hidden}
.bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:99px;width:0;transition:width .8s cubic-bezier(.2,.8,.2,1);
  background:linear-gradient(90deg,var(--cyan),var(--purple));box-shadow:0 0 12px rgba(var(--cyan-rgb),.6)}
.bar.hot>i{background:linear-gradient(90deg,var(--warn),var(--down));box-shadow:0 0 12px rgba(var(--down-rgb),.6)}

/* ---------- rings ---------- */
.ring-box{position:relative;width:118px;height:118px;margin:6px auto 0}
.ring-box canvas{filter:drop-shadow(0 0 8px rgba(var(--cyan-rgb),.45))}
.ring-box.pf canvas{filter:drop-shadow(0 0 8px rgba(var(--purple-rgb),.55))}
.ring-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none}
.ring-num{font-family:var(--font-mono);font-size:24px;color:#fff;text-shadow:0 0 14px rgba(var(--cyan-rgb),.6)}
.ring-box.pf .ring-num{text-shadow:0 0 14px rgba(var(--purple-rgb),.7)}
.ring-sub{margin-top:8px;text-align:center;font-family:var(--font-mono);font-size:11px;color:var(--muted)}

/* ---------- flash ---------- */
.flash{animation:flash .95s ease-out}
@keyframes flash{0%{filter:brightness(2.6) drop-shadow(0 0 10px var(--cyan))}100%{filter:brightness(1) drop-shadow(0 0 0 transparent)}}

/* ---------- chart ---------- */
#tv{width:100%;height:240px;margin-top:10px;border-radius:14px;overflow:hidden}
.seg{display:inline-flex;padding:3px;border-radius:12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);gap:2px}
.seg button{border:0;background:transparent;color:var(--muted);font-family:var(--font-mono);font-size:11px;padding:5px 10px;border-radius:9px;cursor:pointer}
.seg button.on{color:#02030a;background:linear-gradient(135deg,var(--cyan),#7be9ff);box-shadow:0 0 12px rgba(var(--cyan-rgb),.6)}

/* ---------- tabs ---------- */
.pane{animation:rise .45s cubic-bezier(.2,.8,.2,1)}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:50;padding:0 10px calc(10px + env(safe-area-inset-bottom,0px))}
.tabbar-in{max-width:520px;margin:0 auto;display:grid;grid-template-columns:repeat(4,1fr);gap:4px;padding:6px;border-radius:22px;
  background:rgba(8,11,28,.72);backdrop-filter:blur(22px) saturate(160%);-webkit-backdrop-filter:blur(22px) saturate(160%);
  border:1px solid rgba(var(--cyan-rgb),.2);box-shadow:0 18px 40px rgba(0,0,0,.8),0 0 30px -10px rgba(var(--purple-rgb),.5)}
.tab{position:relative;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 2px;border:0;border-radius:16px;background:transparent;
  color:var(--muted);font-family:var(--font-display);font-size:8.5px;letter-spacing:.1em;cursor:pointer;transition:color .2s,background .2s}
.tab svg{width:20px;height:20px}
.tab.on{color:var(--cyan);background:linear-gradient(to bottom,rgba(var(--cyan-rgb),.14),rgba(var(--cyan-rgb),.02));text-shadow:var(--glow-cyan)}
.tab.on::after{content:'';position:absolute;bottom:2px;left:30%;right:30%;height:2px;border-radius:2px;background:var(--cyan);box-shadow:0 0 10px var(--cyan)}
.tab .badge{position:absolute;top:3px;right:22%;min-width:16px;height:16px;padding:0 4px;border-radius:99px;font-family:var(--font-mono);font-size:10px;
  line-height:16px;text-align:center;color:#02030a;background:var(--purple);box-shadow:0 0 10px var(--purple)}

/* ---------- positions ---------- */
.pos-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.sym{font-family:var(--font-display);font-weight:900;font-size:17px;letter-spacing:.06em;color:#fff}
.pos-pnl{text-align:right;font-family:var(--font-mono)}
.pos-pnl .a{font-size:20px}
.pos-pnl .b{font-size:12px;opacity:.85}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.kv .stat .v{font-size:13px}
.track{position:relative;height:10px;margin:18px 4px 6px;border-radius:99px;
  background:linear-gradient(90deg,rgba(var(--down-rgb),.55),rgba(255,255,255,.1) 50%,rgba(var(--up-rgb),.55))}
.track .mk{position:absolute;top:50%;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:#fff;
  border:3px solid var(--cyan);box-shadow:0 0 14px var(--cyan);transition:left .8s cubic-bezier(.2,.8,.2,1)}
.track-lbl{display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:10px;color:var(--muted)}
.pos-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:12px}
.empty{padding:34px 12px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px}
.empty svg{width:34px;height:34px;margin:0 auto 10px;display:block;color:var(--cyan);opacity:.7;filter:drop-shadow(0 0 8px var(--cyan))}

/* ---------- history table ---------- */
.tbl-wrap{overflow-x:auto;margin:10px -4px 0;padding:0 4px}
table.tbl{width:100%;min-width:520px;border-collapse:separate;border-spacing:0 6px;font-family:var(--font-mono);font-size:12px}
.tbl th{padding:2px 8px;text-align:left;font-family:var(--font-display);font-size:8.5px;letter-spacing:.14em;color:var(--muted);font-weight:500}
.tbl td{padding:10px 8px;white-space:nowrap}
.tbl td:first-child{border-radius:12px 0 0 12px;border-left:3px solid transparent}
.tbl td:last-child{border-radius:0 12px 12px 0}
.tbl tr.win td{background:linear-gradient(90deg,rgba(var(--up-rgb),.12),rgba(var(--up-rgb),.03))}
.tbl tr.win td:first-child{border-left-color:var(--up)}
.tbl tr.loss td{background:linear-gradient(90deg,rgba(var(--down-rgb),.13),rgba(var(--down-rgb),.03))}
.tbl tr.loss td:first-child{border-left-color:var(--down)}
.tbl .side{font-size:9px;padding:1px 6px;border-radius:6px;margin-left:6px;vertical-align:middle}

/* ---------- terminal ---------- */
.term{position:relative;overflow:hidden;border-radius:var(--radius);background:#000;border:1px solid rgba(var(--up-rgb),.28);
  box-shadow:0 24px 50px -14px rgba(0,0,0,.9),0 0 40px -12px rgba(var(--up-rgb),.4),inset 0 0 60px rgba(var(--up-rgb),.05)}
.term-bar{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(var(--up-rgb),.18);background:rgba(var(--up-rgb),.04)}
.dot{width:9px;height:9px;border-radius:50%}
.term-body{position:relative;max-height:64vh;overflow-y:auto;padding:10px 12px 16px;font-family:var(--font-mono);font-size:12px;line-height:1.5}
.term::after{content:'';position:absolute;inset:0;pointer-events:none;
  background:repeating-linear-gradient(to bottom,rgba(255,255,255,.035) 0,rgba(255,255,255,.035) 1px,transparent 1px,transparent 3px)}
.log{padding:6px 0;border-bottom:1px dashed rgba(255,255,255,.07)}
.log .m{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.log .t{color:#4b8f7a}
.log .s{color:var(--cyan)}
.log .a{padding:0 7px;border-radius:5px;font-size:11px}
.log .a.hold{color:var(--warn);background:rgba(255,176,32,.1)}
.log .a.buy{color:var(--up);background:rgba(var(--up-rgb),.14);text-shadow:0 0 8px var(--up)}
.log .a.short{color:var(--down);background:rgba(var(--down-rgb),.14);text-shadow:0 0 8px var(--down)}
.log .sc{color:var(--muted)}
.log .r{margin-top:2px;color:#a8e6cf;opacity:.85;word-break:break-word}
.log .r.blk{color:#ffd28a}
.cursor{display:inline-block;width:8px;height:14px;margin-left:4px;vertical-align:-2px;background:var(--up);box-shadow:0 0 10px var(--up);animation:blink 1s steps(2) infinite}
@keyframes blink{50%{opacity:0}}

/* ---------- toasts + modal ---------- */
#toasts{position:fixed;left:0;right:0;top:calc(66px + env(safe-area-inset-top,0px));z-index:90;display:flex;flex-direction:column;align-items:center;gap:8px;pointer-events:none;padding:0 12px}
.toast{display:flex;align-items:center;gap:8px;max-width:420px;padding:10px 14px;border-radius:14px;font-family:var(--font-mono);font-size:12px;color:#fff;
  background:rgba(8,11,28,.88);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(var(--cyan-rgb),.4);
  box-shadow:0 14px 34px rgba(0,0,0,.7),0 0 22px rgba(var(--cyan-rgb),.25);animation:drop .35s cubic-bezier(.2,.8,.2,1)}
.toast svg{width:16px;height:16px;flex:none;color:var(--cyan)}
.toast.ok{border-color:rgba(var(--up-rgb),.5)} .toast.ok svg{color:var(--up)}
.toast.err{border-color:rgba(var(--down-rgb),.55)} .toast.err svg{color:var(--down)}
@keyframes drop{from{opacity:0;transform:translateY(-14px) scale(.96)}to{opacity:1;transform:none}}
.modal{position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;padding:18px;background:rgba(0,0,6,.72);
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.modal .glass{width:100%;max-width:380px;animation:rise .3s cubic-bezier(.2,.8,.2,1)}
.modal h3{margin:0;font-family:var(--font-display);font-size:14px;letter-spacing:.12em;color:#fff;display:flex;align-items:center;gap:8px}
.modal h3 svg{width:18px;height:18px;color:var(--cyan)}
.modal pre{margin:12px 0 0;white-space:pre-wrap;word-break:break-word;font-family:var(--font-mono);font-size:12px;line-height:1.55;color:#c9d8f5;max-height:46vh;overflow:auto}
.modal .acts{display:flex;gap:8px;margin-top:16px}
.modal .acts .btn{flex:1;height:40px}
.spin{animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.live-dot{width:8px;height:8px;border-radius:50%;background:var(--up);box-shadow:0 0 10px var(--up);animation:pulse 1.6s ease-in-out infinite}
.live-dot.off{background:var(--down);box-shadow:0 0 10px var(--down)}
@keyframes pulse{50
