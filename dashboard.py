"""Ultimate FastAPI Dashboard - Final Perfected Edition."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio, re
from backtest import run_backtest, format_report
import config
from optimizer import run_auto_tune

router=APIRouter()
_bt_running=False

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
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
@media(max-width:430px){#pause-btn .lbl{display:none}}

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
@keyframes pulse{50%{transform:scale(1.5);opacity:.55}}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-thumb{background:rgba(var(--cyan-rgb),.3);border-radius:9px}
@media(min-width:720px){.deck{display:grid;grid-template-columns:1fr 1fr;gap:12px}.deck>.span2{grid-column:1/-1}.stack>.deck{margin-top:12px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div class="orb o1"></div><div class="orb o2"></div>

<header class="nav">
  <div class="nav-inner">
    <div class="brand"><i data-lucide="hexagon"></i><span>AI QUANT <b>X</b></span></div>
    <div class="nav-bal" title="Total balance"><i data-lucide="wallet"></i><span id="nav-bal">0.00</span></div>
    <div class="nav-actions">
      <button id="pause-btn" class="btn btn-up" onclick="togglePause()" aria-label="Pause or resume bot"><i data-lucide="activity"></i><span class="lbl">ACTIVE</span></button>
      <button id="tune-btn" class="btn btn-purple" onclick="autoTune()" aria-label="Auto tune"><i data-lucide="sparkles"></i><span class="lbl">AUTO-TUNE</span></button>
    </div>
  </div>
  <div class="nav-line"></div>
</header>

<main class="wrap">

  <!-- ================= OVERVIEW ================= -->
  <section id="tab-overview" class="pane stack">
    <div class="glass">
      <div class="flex items-center justify-between">
        <span class="label"><i data-lucide="wallet"></i>Total Balance</span>
        <span class="flex items-center gap-2"><span id="live-dot" class="live-dot"></span><span class="chip cy">PAPER</span></span>
      </div>
      <div class="big-num"><span class="cur">$</span><span id="equity">0.00</span><span class="unit">USDT</span></div>
      <div id="pnl-chip" class="pnl-chip"><i data-lucide="minus"></i><span id="pnl-val">0.00 USDT</span><span id="pnl-pct">(0.00%)</span></div>
      <div class="grid grid-cols-3 gap-2 mt-4">
        <div class="stat"><div class="k">CASH</div><div class="v" id="st-cash">0.00</div></div>
        <div class="stat"><div class="k">FLOATING</div><div class="v" id="st-unreal">0.00</div></div>
        <div class="stat"><div class="k">REALIZED</div><div class="v" id="st-real">0.00</div></div>
      </div>
      <div class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <span class="label"><i data-lucide="shield"></i>Risk Heat</span>
          <span class="mono muted" style="font-size:11px" id="heat-txt">0.00 / 0.00</span>
        </div>
        <div class="bar" id="heat-bar"><i id="heat-fill"></i></div>
        <div class="flex items-center justify-between mt-2 mono" style="font-size:11px">
          <span class="muted">DAILY P&amp;L</span><span id="daily-txt">0.00</span>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="glass" style="padding:14px 10px">
        <div class="label" style="justify-content:center"><i data-lucide="target"></i>Win Rate</div>
        <div class="ring-box"><canvas id="ring-wr"></canvas>
          <div class="ring-center"><div class="ring-num" id="wr-num">0%</div></div></div>
        <div class="ring-sub" id="wr-sub">W 0 / L 0</div>
      </div>
      <div class="glass violet" style="padding:14px 10px">
        <div class="label" style="justify-content:center"><i data-lucide="gauge"></i>Profit Factor</div>
        <div class="ring-box pf"><canvas id="ring-pf"></canvas>
          <div class="ring-center"><div class="ring-num" id="pf-num">0.00</div></div></div>
        <div class="ring-sub" id="pf-sub">GP 0 / GL 0</div>
      </div>
    </div>

    <div class="glass">
      <div class="flex items-center justify-between">
        <span class="label"><i data-lucide="activity"></i>BTC / USDT</span>
        <div class="seg" id="seg">
          <button class="on" data-iv="15m" onclick="setInterval2('15m')">15m</button>
          <button data-iv="1h" onclick="setInterval2('1h')">1h</button>
          <button data-iv="4h" onclick="setInterval2('4h')">4h</button>
        </div>
      </div>
      <div class="flex items-baseline gap-3 mt-2">
        <span class="mono" style="font-size:22px" id="btc-price">--</span>
        <span class="mono" style="font-size:12px" id="btc-chg">--</span>
      </div>
      <div id="tv"></div>
    </div>
  </section>

  <!-- ================= POSITIONS ================= -->
  <section id="tab-positions" class="pane stack hidden">
    <div class="flex items-center justify-between px-1">
      <span class="label"><i data-lucide="crosshair"></i>Open Positions</span>
      <span class="chip pu" id="pos-count">0 OPEN</span>
    </div>
    <div id="pos-list" class="stack"></div>
  </section>

  <!-- ================= HISTORY ================= -->
  <section id="tab-history" class="pane stack hidden">
    <div class="glass">
      <div class="flex items-center justify-between">
        <span class="label"><i data-lucide="history"></i>Last 10 Closed</span>
        <span class="chip" id="hist-sum">--</span>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead><tr><th>PAIR</th><th>ENTRY</th><th>EXIT</th><th>NET PNL</th><th>CLOSED</th></tr></thead>
          <tbody id="hist-body"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ================= LOGS ================= -->
  <section id="tab-logs" class="pane stack hidden">
    <div class="term">
      <div class="term-bar">
        <span class="dot" style="background:var(--down)"></span><span class="dot" style="background:var(--warn)"></span><span class="dot" style="background:var(--up)"></span>
        <span class="label" style="margin-left:6px;color:var(--up)"><i data-lucide="terminal" style="color:var(--up)"></i>Neural Logs</span>
        <div class="seg" style="margin-left:auto" id="logseg">
          <button class="on" data-f="all" onclick="setLogFilter('all')">ALL</button>
          <button data-f="sig" onclick="setLogFilter('sig')">SIGNALS</button>
        </div>
      </div>
      <div class="term-body" id="log-body"></div>
    </div>
  </section>

</main>

<nav class="tabbar">
  <div class="tabbar-in">
    <button class="tab on" data-tab="overview" onclick="switchTab('overview')"><i data-lucide="layout-dashboard"></i>OVERVIEW</button>
    <button class="tab" data-tab="positions" onclick="switchTab('positions')"><i data-lucide="crosshair"></i>POSITIONS<span class="badge hidden" id="tab-badge">0</span></button>
    <button class="tab" data-tab="history" onclick="switchTab('history')"><i data-lucide="history"></i>HISTORY</button>
    <button class="tab" data-tab="logs" onclick="switchTab('logs')"><i data-lucide="terminal"></i>LOGS</button>
  </div>
</nav>

<div id="toasts"></div>

<div id="modal" class="modal hidden" onclick="if(event.target===this)closeModal(false)">
  <div class="glass violet">
    <h3><i id="modal-icon" data-lucide="info"></i><span id="modal-title">--</span></h3>
    <pre id="modal-body"></pre>
    <div class="acts">
      <button id="modal-cancel" class="btn" onclick="closeModal(false)">CANCEL</button>
      <button id="modal-ok" class="btn btn-purple" onclick="closeModal(true)">OK</button>
    </div>
  </div>
</div>

<script>
const state = { paused: false, positions: [], interval: '15m', logFilter: 'all', decisions: [], tab: 'overview', equityShown: null, posIds: '', overlaySig: '', timer: null };
let ringWr = null, ringPf = null, chart = null, series = null, priceLines = [], modalCb = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => { const d = document.createElement('div'); d.textContent = String(s == null ? '' : s); return d.innerHTML; };
const num = (v) => { const n = Number(v); return isFinite(n) ? n : 0; };
const fmt = (n) => num(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtSigned = (n) => (num(n) > 0 ? '+' : '') + fmt(n);
const fmtPrice = (n) => { n = num(n); const a = Math.abs(n); if (a >= 1000) return fmt(n); if (a >= 1) return n.toFixed(4); return n.toPrecision(4); };
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const icons = () => { try { if (window.lucide) window.lucide.createIcons(); } catch (e) {} };
const fmtClock = (iso) => { const d = new Date(iso); return isNaN(d) ? '--' : d.toLocaleTimeString('en-GB'); };
const fmtShort = (iso) => { const d = new Date(iso); return isNaN(d) ? '--' : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }); };
const cls = (v) => (num(v) > 0 ? 'up' : num(v) < 0 ? 'dn' : 'muted');

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (r.status === 401) { window.location.href = '/login'; throw new Error('unauthorized'); }
  return r.json();
}

function setText(el, text) {
  if (!el) return;
  if (el.textContent !== text) {
    el.textContent = text;
    el.classList.remove('flash');
    void el.offsetWidth;
    el.classList.add('flash');
  }
}

function tween(el, from, to, ms) {
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / ms);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ---------------- toasts / modal ---------------- */
function toast(msg, type) {
  const icon = type === 'ok' ? 'check-circle' : type === 'err' ? 'alert-circle' : 'info';
  const el = document.createElement('div');
  el.className = 'toast ' + (type || '');
  el.innerHTML = '<i data-lucide="' + icon + '"></i><span>' + esc(msg) + '</span>';
  $('toasts').appendChild(el);
  icons();
  setTimeout(() => { el.style.transition = 'all .3s'; el.style.opacity = '0'; el.style.transform = 'translateY(-12px)'; setTimeout(() => el.remove(), 320); }, 3600);
}

function openModal(o) {
  $('modal-title').textContent = o.title;
  $('modal-body').textContent = o.body || '';
  $('modal-icon').outerHTML = '<i id="modal-icon" data-lucide="' + (o.icon || 'info') + '"></i>';
  $('modal-cancel').style.display = o.cancelText === null ? 'none' : '';
  $('modal-cancel').textContent = o.cancelText || 'CANCEL';
  $('modal-ok').textContent = o.okText || 'OK';
  $('modal-ok').className = 'btn ' + (o.tone === 'down' ? 'btn-down' : 'btn-purple');
  modalCb = o.onOk || null;
  $('modal').classList.remove('hidden');
  icons();
}

function closeModal(ok) {
  $('modal').classList.add('hidden');
  const cb = modalCb; modalCb = null;
  if (ok && cb) cb();
}

/* ---------------- tabs ---------------- */
function switchTab(name) {
  state.tab = name;
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('on', b.dataset.tab === name));
  ['overview', 'positions', 'history', 'logs'].forEach((t) => $('tab-' + t).classList.toggle('hidden', t !== name));
  try { localStorage.setItem('aqx_tab', name); } catch (e) {}
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (name === 'overview' && chart) setTimeout(() => { const w = $('tv').clientWidth; if (w > 0) { chart.applyOptions({ width: w }); chart.timeScale().fitContent(); } }, 80);
}

/* ---------------- bot controls ---------------- */
function renderPause() {
  const b = $('pause-btn');
  if (state.paused) { b.className = 'btn btn-down'; b.innerHTML = '<i data-lucide="pause"></i><span class="lbl">PAUSED</span>'; }
  else { b.className = 'btn btn-up'; b.innerHTML = '<i data-lucide="activity"></i><span class="lbl">ACTIVE</span>'; }
  icons();
}

async function togglePause() {
  const b = $('pause-btn');
  b.setAttribute('disabled', '');
  try {
    const d = await api('/api/toggle_pause', { method: 'POST' });
    state.paused = !!d.paused;
    toast(state.paused ? 'Bot paused' : 'Bot resumed', state.paused ? 'err' : 'ok');
  } catch (e) { toast('Request failed', 'err'); }
  b.removeAttribute('disabled');
  renderPause();
}

function autoTune() {
  openModal({
    title: 'AUTO-TUNE', icon: 'sparkles', okText: 'START',
    body: 'سيقوم البوت باختبار الاستراتيجيات على بيانات BTCUSDT ويطبق الأفضل والأكثر موثوقية. قد يستغرق دقيقة. هل تريد المتابعة؟',
    onOk: runTune
  });
}

async function runTune() {
  const b = $('tune-btn');
  b.setAttribute('disabled', '');
  b.innerHTML = '<i data-lucide="loader" class="spin"></i><span class="lbl">TUNING</span>';
  icons();
  toast('Auto-Tune running... this may take a minute', 'info');
  try {
    const d = await api('/api/auto_tune?symbol=BTCUSDT', { method: 'POST' });
    if (d.success) {
      const p = d.best_params || {};
      openModal({ title: 'TUNE COMPLETE', icon: 'check-circle', cancelText: null, okText: 'DONE',
        body: ['Strategy: ' + String(p.strategy || '').toUpperCase(), 'RSI: ' + p.RSI + '  EMA: ' + p.EMA, 'Return: ' + fmtSigned(d.return_pct) + '%', 'Win rate: ' + num(d.win_rate).toFixed(1) + '%', 'Trades: ' + d.trades].join(String.fromCharCode(10)) });
    } else {
      openModal({ title: 'TUNE FAILED', icon: 'alert-circle', cancelText: null, okText: 'CLOSE', tone: 'down', body: String(d.error || 'Unknown error') });
    }
  } catch (e) { toast('Auto-Tune request failed', 'err'); }
  b.removeAttribute('disabled');
  b.innerHTML = '<i data-lucide="sparkles"></i><span class="lbl">AUTO-TUNE</span>';
  icons();
}

function closePosition(id, symbol) {
  openModal({
    title: 'CLOSE POSITION', icon: 'x-circle', okText: 'CLOSE NOW', tone: 'down',
    body: 'هل أنت متأكد من إغلاق صفقة ' + symbol + ' الآن بسعر السوق؟',
    onOk: async () => {
      try {
        const d = await api('/api/close_position/' + id, { method: 'POST' });
        if (d.success) toast('Closed ' + symbol, 'ok'); else toast('Error: ' + (d.error || 'close failed'), 'err');
      } catch (e) { toast('Failed to close position', 'err'); }
      load();
    }
  });
}

/* ---------------- rings ---------------- */
function makeRing(id, c1, c2) {
  if (!window.Chart) return null;
  const canvas = $(id);
  const g = canvas.getContext('2d').createLinearGradient(0, 0, 118, 118);
  g.addColorStop(0, c1); g.addColorStop(1, c2);
  return new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: { datasets: [{ data: [0, 100], backgroundColor: [g, 'rgba(255,255,255,0.07)'], borderWidth: 0, cutout: '80%', borderRadius: 10 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: { duration: 1000 }, plugins: { legend: { display: false }, tooltip: { enabled: false } } }
  });
}

function setRing(r, v) {
  if (!r) return;
  const x = Math.max(0, Math.min(100, v));
  r.data.datasets[0].data = [x, 100 - x];
  r.update();
}

/* ---------------- overview ---------------- */
function renderBalance(p, rk) {
  const start = num(p.initial_balance) || 200;
  const eq = num(p.equity);
  if (state.equityShown === null) { $('equity').textContent = fmt(eq); }
  else if (Math.abs(state.equityShown - eq) > 0.004) {
    tween($('equity'), state.equityShown, eq, 700);
    $('equity').classList.remove('flash'); void $('equity').offsetWidth; $('equity').classList.add('flash');
  }
  state.equityShown = eq;
  setText($('nav-bal'), fmt(eq));

  const pnl = eq - start, pct = start ? pnl / start * 100 : 0;
  const chip = $('pnl-chip');
  chip.className = 'pnl-chip ' + (pnl > 0.004 ? 'up' : pnl < -0.004 ? 'dn' : '');
  const icon = pnl > 0.004 ? 'trending-up' : pnl < -0.004 ? 'trending-down' : 'minus';
  if (chip.dataset.icon !== icon) {
    chip.dataset.icon = icon;
    chip.innerHTML = '<i data-lucide="' + icon + '"></i><span id="pnl-val"></span><span id="pnl-pct"></span>';
    icons();
  }
  const col = pnl > 0.004 ? 'var(--up)' : pnl < -0.004 ? 'var(--down)' : 'var(--muted)';
  chip.style.color = col;
  setText($('pnl-val'), fmtSigned(pnl) + ' USDT');
  setText($('pnl-pct'), '(' + (pct > 0 ? '+' : '') + pct.toFixed(2) + '%)');

  setText($('st-cash'), fmt(p.cash_balance));
  const un = $('st-unreal'); setText(un, fmtSigned(p.unrealized_pnl)); un.className = 'v ' + cls(p.unrealized_pnl);
  const re = $('st-real'); setText(re, fmtSigned(p.realized_pnl)); re.className = 'v ' + cls(p.realized_pnl);

  if (rk) {
    const cap = num(rk.risk_cap), used = num(rk.open_risk);
    const ratio = cap > 0 ? Math.min(100, used / cap * 100) : 0;
    $('heat-fill').style.width = ratio.toFixed(1) + '%';
    $('heat-bar').className = 'bar' + (ratio > 70 ? ' hot' : '');
    setText($('heat-txt'), fmt(used) + ' / ' + fmt(cap) + ' USDT');
    const dc = $('daily-txt'); setText(dc, fmtSigned(rk.daily_change) + ' USDT' + (rk.daily_limit_hit ? '  LIMIT HIT' : '')); dc.className = cls(rk.daily_change);
  }
}

function renderRings(perf) {
  const wr = num(perf.win_rate);
  setText($('wr-num'), wr.toFixed(0) + '%');
  setText($('wr-sub'), 'W ' + num(perf.wins) + ' / L ' + num(perf.losses));
  setRing(ringWr, wr);
  const hasPf = perf.profit_factor !== null && perf.profit_factor !== undefined;
  const pf = num(perf.profit_factor);
  setText($('pf-num'), hasPf ? pf.toFixed(2) : 'INF');
  setText($('pf-sub'), 'GP ' + fmt(perf.gross_profit) + ' / GL ' + fmt(perf.gross_loss));
  setRing(ringPf, hasPf ? Math.min(pf / 3, 1) * 100 : 100);
}

/* ---------------- candlestick chart ---------------- */
function initChart() {
  const el = $('tv');
  if (!window.LightweightCharts) { el.innerHTML = '<div class="empty">Chart library unavailable</div>'; return; }
  const up = css('--up'), down = css('--down');
  chart = LightweightCharts.createChart(el, {
    width: el.clientWidth || 320, height: 240,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--muted'), fontFamily: 'Share Tech Mono, monospace' },
    grid: { vertLines: { color: 'rgba(0,243,255,0.05)' }, horzLines: { color: 'rgba(176,38,255,0.07)' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
    timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible: false }
  });
  series = chart.addCandlestickSeries({ upColor: up, downColor: down, borderUpColor: up, borderDownColor: down, wickUpColor: up, wickDownColor: down });
  if (window.ResizeObserver) new ResizeObserver(() => { const w = el.clientWidth; if (w > 0) chart.applyOptions({ width: w }); }).observe(el);
  loadKlines();
}

async function loadKlines() {
  if (!series) return;
  try {
    const d = await api('/api/market_klines?symbol=BTCUSDT&interval=' + state.interval);
    if (!Array.isArray(d) || d.length === 0) return;
    series.setData(d);
    chart.timeScale().fitContent();
    const last = d[d.length - 1], first = d[0];
    setText($('btc-price'), '$' + fmtPrice(last.close));
    const chg = first.open ? (last.close / first.open - 1) * 100 : 0;
    const ce = $('btc-chg'); ce.className = 'mono ' + cls(chg); setText(ce, (chg > 0 ? '+' : '') + chg.toFixed(2) + '%');
    state.overlaySig = '';
    drawOverlays();
  } catch (e) {}
}

function drawOverlays() {
  if (!series) return;
  const mine = state.positions.filter((p) => p.symbol === 'BTCUSDT');
  const sig = JSON.stringify(mine.map((p) => [p.id, p.stop_price, p.target_price]));
  if (sig === state.overlaySig) return;
  state.overlaySig = sig;
  priceLines.forEach((l) => { try { series.removePriceLine(l); } catch (e) {} });
  priceLines = [];
  mine.forEach((p) => {
    const mk = (price, color, title) => priceLines.push(series.createPriceLine({ price: num(price), color: color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: title }));
    mk(p.entry_price, '#00f3ff', 'ENTRY'); mk(p.stop_price, css('--down'), 'STOP'); mk(p.target_price, css('--up'), 'TARGET');
  });
}

function setInterval2(iv) {
  state.interval = iv;
  document.querySelectorAll('#seg button').forEach((b) => b.classList.toggle('on', b.dataset.iv === iv));
  loadKlines();
}

/* ---------------- positions ---------------- */
function calcPos(p) {
  const sign = p.side === 'LONG' ? 1 : -1;
  const entry = num(p.entry_price), cur = num(p.current_price) || entry;
  const pnl = (cur - entry) * num(p.quantity) * sign;
  const pct = entry ? (cur / entry - 1) * sign * 100 : 0;
  const stop = num(p.stop_price), target = num(p.target_price);
  let prog = 50;
  if (p.side === 'LONG' && target > stop) prog = (cur - stop) / (target - stop) * 100;
  if (p.side === 'SHORT' && stop > target) prog = (stop - cur) / (stop - target) * 100;
  return { pnl: pnl, pct: pct, cur: cur, prog: Math.max(2, Math.min(98, prog)) };
}

function buildPos(p) {
  const long = p.side === 'LONG';
  const base = String(p.symbol).replace('USDT', '');
  return '<div class="glass ' + (long ? '' : 'violet') + '" id="pc-' + p.id + '">' +
    '<div class="pos-head"><div><div class="sym">' + esc(base) + '<span class="muted" style="font-size:10px">/USDT</span></div>' +
    '<div class="flex items-center gap-2 mt-1"><span class="chip ' + (long ? 'up' : 'dn') + '"><i data-lucide="' + (long ? 'trending-up' : 'trending-down') + '"></i>' + esc(p.side) + '</span>' +
    '<span class="chip">' + esc(p.strategy || 'auto') + '</span></div></div>' +
    '<div class="pos-pnl"><div class="a" id="pc-' + p.id + '-pnl">0.00</div><div class="b" id="pc-' + p.id + '-pct">0.00%</div></div></div>' +
    '<div class="kv">' +
    '<div class="stat"><div class="k">ENTRY</div><div class="v">' + fmtPrice(p.entry_price) + '</div></div>' +
    '<div class="stat"><div class="k">EXIT (LIVE)</div><div class="v" id="pc-' + p.id + '-mark">--</div></div>' +
    '<div class="stat"><div class="k">TARGET</div><div class="v up">' + fmtPrice(p.target_price) + '</div></div>' +
    '<div class="stat"><div class="k">STOP LOSS</div><div class="v dn">' + fmtPrice(p.stop_price) + '</div></div></div>' +
    '<div class="track"><div class="mk" id="pc-' + p.id + '-mk" style="left:50%"></div></div>' +
    '<div class="track-lbl"><span>STOP</span><span>ENTRY</span><span>TARGET</span></div>' +
    '<div class="pos-foot"><span class="mono muted" style="font-size:11px">RISK ' + fmt(p.risk_amount) + ' USDT | ' + fmtShort(p.opened_at) + '</span>' +
    '<button class="btn btn-down" data-id="' + num(p.id) + '" data-sym="' + esc(p.symbol) + '" onclick="closePosition(this.dataset.id, this.dataset.sym)"><i data-lucide="x-circle"></i><span>CLOSE</span></button></div></div>';
}

function renderPositions(list) {
  state.positions = list;
  const n = list.length;
  $('pos-count').textContent = n + ' OPEN';
  const badge = $('tab-badge');
  badge.textContent = n; badge.classList.toggle('hidden', n === 0);
  const ids = list.map((p) => p.id).join(',');
  if (ids !== state.posIds) {
    state.posIds = ids;
    $('pos-list').innerHTML = n === 0
      ? '<div class="glass"><div class="empty"><i data-lucide="radar"></i>NO OPEN POSITIONS<br>Scanning the market...</div></div>'
      : list.map(buildPos).join('');
    icons();
  }
  list.forEach((p) => {
    const c = calcPos(p);
    const pe = $('pc-' + p.id + '-pnl'), pc = $('pc-' + p.id + '-pct');
    if (!pe) return;
    pe.className = 'a ' + cls(c.pnl); pc.className = 'b ' + cls(c.pnl);
    setText(pe, fmtSigned(c.pnl) + ' USDT');
    setText(pc, (c.pct > 0 ? '+' : '') + c.pct.toFixed(2) + '%');
    setText($('pc-' + p.id + '-mark'), fmtPrice(c.cur));
    $('pc-' + p.id + '-mk').style.left = c.prog.toFixed(1) + '%';
  });
  drawOverlays();
}

/* ---------------- history ---------------- */
function renderHistory(trades) {
  const closed = trades.filter((t) => t.status === 'CLOSED')
    .sort((a, b) => String(b.closed_at || '').localeCompare(String(a.closed_at || '')))
    .slice(0, 10);
  const wins = closed.filter((t) => num(t.net_pnl) > 0).length;
  const net = closed.reduce((s, t) => s + num(t.net_pnl), 0);
  const sum = $('hist-sum');
  sum.className = 'chip ' + (net > 0 ? 'up' : net < 0 ? 'dn' : '');
  sum.textContent = closed.length ? 'W' + wins + ' / L' + (closed.length - wins) + '  ' + fmtSigned(net) : '--';
  $('hist-body').innerHTML = closed.length === 0
    ? '<tr><td colspan="5"><div class="empty">NO CLOSED TRADES YET</div></td></tr>'
    : closed.map((t) => {
        const w = num(t.net_pnl) > 0;
        const base = String(t.symbol).replace('USDT', '');
        return '<tr class="' + (w ? 'win' : 'loss') + '">' +
          '<td><b>' + esc(base) + '</b><span class="side chip ' + (t.side === 'LONG' ? 'up' : 'dn') + '">' + esc(t.side) + '</span></td>' +
          '<td>' + fmtPrice(t.entry_price) + '</td><td>' + fmtPrice(t.exit_price) + '</td>' +
          '<td class="' + (w ? 'up' : 'dn') + '"><b>' + fmtSigned(t.net_pnl) + '</b></td>' +
          '<td class="muted">' + fmtShort(t.closed_at) + '</td></tr>';
      }).join('');
}

/* ---------------- logs ---------------- */
function setLogFilter(f) {
  state.logFilter = f;
  document.querySelectorAll('#logseg button').forEach((b) => b.classList.toggle('on', b.dataset.f === f));
  renderLogs(state.decisions, true);
}

function renderLogs(list, force) {
  const sig = (list[0] ? list[0].id : 0) + ':' + list.length + ':' + state.logFilter;
  if (!force && sig === state.logSig) return;
  state.logSig = sig;
  state.decisions = list;
  const rows = list.filter((d) => state.logFilter === 'all' || String(d.action).toUpperCase() !== 'HOLD').slice(0, 60);
  const head = '<div class="log"><span class="up">&gt;</span> <span class="muted">awaiting signals</span><span class="cursor"></span></div>';
  $('log-body').innerHTML = head + rows.map((d) => {
    const a = String(d.action || '').toUpperCase();
    const k = a.indexOf('SHORT') >= 0 ? 'short' : a.indexOf('BUY') >= 0 ? 'buy' : 'hold';
    const reason = String(d.reason || '');
    const blk = reason.indexOf('Blocked') >= 0 ? ' blk' : '';
    return '<div class="log"><div class="m"><span class="t">' + fmtClock(d.created_at) + '</span><span class="s">' + esc(String(d.symbol || '').replace('USDT', '')) +
      '</span><span class="a ' + k + '">' + esc(a) + '</span><span class="sc">SC ' + num(d.score).toFixed(0) + '</span></div><div class="r' + blk + '">' + esc(reason) + '</div></div>';
  }).join('');
}

/* ---------------- main loop ---------------- */
async function load() {
  if (document.hidden) return;
  const get = (u) => api(u).catch(() => null);
  const res = await Promise.all([get('/api/portfolio'), get('/api/positions'), get('/api/performance'), get('/api/status'), get('/api/decisions'), get('/api/trades'), get('/api/risk')]);
  const p = res[0], ps = res[1], perf = res[2], st = res[3], dec = res[4], tr = res[5], rk = res[6];
  $('live-dot').className = 'live-dot' + (p ? '' : ' off');
  if (p) renderBalance(p, rk);
  if (Array.isArray(ps)) renderPositions(ps);
  if (perf) renderRings(perf);
  if (st && typeof st.paused === 'boolean' && st.paused !== state.paused) { state.paused = st.paused; renderPause(); }
  if (Array.isArray(dec)) renderLogs(dec, false);
  if (Array.isArray(tr)) renderHistory(tr);
}

document.addEventListener('DOMContentLoaded', () => {
  icons();
  try { ringWr = makeRing('ring-wr', '#00f3ff', '#00ffa3'); ringPf = makeRing('ring-pf', '#b026ff', '#00f3ff'); } catch (e) {}
  try { initChart(); } catch (e) {}
  let saved = 'overview';
  try { saved = localStorage.getItem('aqx_tab') || 'overview'; } catch (e) {}
  if (['overview', 'positions', 'history', 'logs'].indexOf(saved) >= 0) switchTab(saved);
  window.scrollTo(0, 0);
  load();
  setInterval(load, 5000);
  setInterval(loadKlines, 20000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { load(); loadKlines(); } });
});
</script>
</body>
</html>""")

@router.get("/api/status")
async def status(request:Request): return request.app.state.engine.get_status()
@router.get("/api/portfolio")
async def portfolio(request:Request):
    db=request.app.state.db
    return {**db.get_portfolio(),"initial_balance":float(db.get_state("initial_balance",config.INITIAL_BALANCE))}
@router.get("/api/risk")
async def risk(request:Request): 
    r = request.app.state.engine.risk.get_risk_status()
    r["breadth"] = await request.app.state.engine.market.get_market_breadth("futures")
    return r
@router.get("/api/positions")
async def positions(request:Request): 
    db = request.app.state.db; market = request.app.state.engine.market; pos_list = db.get_open_positions()
    if pos_list:
        sources = {p["source"] for p in pos_list}; all_prices = {}
        for src in sources: all_prices.update(await market.get_last_prices(src))
        for p in pos_list: p["current_price"] = all_prices.get(p["symbol"], {}).get("last_price", p["entry_price"])
    return pos_list
@router.get("/api/trades")
async def trades(request:Request): return request.app.state.db.get_recent_trades()
@router.get("/api/performance")
async def performance(request:Request): return request.app.state.db.get_performance()
@router.get("/api/decisions")
async def decisions(request:Request): return request.app.state.db.get_recent_decisions()
@router.get("/api/live_tickers")
async def live_tickers(request: Request):
    try:
        market = request.app.state.engine.market; tickers = await market.get_tickers_24h("futures"); symbols = list(config.SYMBOLS); out = []
        for s in symbols:
            if s in tickers: out.append({"symbol": s.replace("USDT", ""), "price": tickers[s]["last_price"], "change": round(tickers[s]["change_percent"], 2)})
        return out
    except Exception: return []
@router.get("/api/market_klines")
async def market_klines(request: Request, symbol: str = "BTCUSDT", interval: str = "15m"):
    try:
        market = request.app.state.engine.market; df = await market.get_klines(symbol, interval, 100, "futures"); data = []
        for _, row in df.iterrows(): data.append({"time": int(row["timestamp"]) // 1000, "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])})
        return data
    except Exception as e: return JSONResponse({"error": str(e)}, status_code=500)
@router.post("/api/toggle_pause")
async def toggle_pause(request:Request):
    engine = request.app.state.engine; engine.set_paused(not engine.paused); return {"success": True, "paused": engine.paused}
@router.post("/api/close_position/{pos_id}")
async def close_position(request:Request, pos_id: int):
    try:
        db = request.app.state.db; engine = request.app.state.engine; pos = db.get_position(pos_id)
        if not pos or pos["status"] != "OPEN": return JSONResponse({"success": False, "error": "Not found"}, status_code=400)
        prices = await engine.market.get_last_prices(pos["source"])
        if pos["symbol"] not in prices: return JSONResponse({"success": False, "error": "No price"}, status_code=400)
        engine.trader.close_position(pos_id, prices[pos["symbol"]]["last_price"], "MANUAL_UI"); return {"success": True}
    except Exception as e: return JSONResponse({"success": False, "error": str(e)}, status_code=500)
@router.post("/api/run_backtest")
async def run_backtest_api(request: Request, symbol: str = "BTCUSDT", strategy: str = "all"):
    global _bt_running
    symbol = symbol.upper()
    if not re.fullmatch(r"[A-Z0-9]{5,15}", symbol): return {"success": False, "error": "Invalid symbol"}
    if strategy != "all" and strategy not in config.STRATEGIES: return {"success": False, "error": "Invalid strategy"}
    if _bt_running: return {"success": False, "error": "Another backtest is running, try again shortly"}
    _bt_running = True
    try:
        engine = request.app.state.engine; market = engine.market; df = await market.fetch_history(symbol, "1h", "futures", 1000)
        if df.empty: return {"success": False, "error": "Failed to fetch history"}
        strategies = None if strategy == "all" else [strategy]
        report = await asyncio.to_thread(run_backtest, df, strategies, "futures")
        return {"success": True, "report": format_report(symbol, report, "1h")}
    except Exception as e: return {"success": False, "error": str(e)}
    finally: _bt_running = False
@router.post("/api/auto_tune")
async def api_auto_tune(request: Request, symbol: str = "BTCUSDT"):
    try:
        engine = request.app.state.engine; db = request.app.state.db; market = engine.market
        return await run_auto_tune(db, market, symbol)
    except Exception as e: return {"success": False, "error": str(e)}
