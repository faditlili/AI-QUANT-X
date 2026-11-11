"""FastAPI dashboard with Interactive Backtesting UI & Robust Fetching."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
from backtest import run_backtest, format_report  # <--- تم حذف fetch_history من هنا
import config

router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>AI QUANT X · NEXUS</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: { extend: { colors: { brand: { bg: '#03040a', card: '#0a0f1e', border: '#1e293b' }, neon: { cyan: '#00f3ff', green: '#00ff66', red: '#ff003c', purple: '#b026ff' } }, fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Share Tech Mono', 'monospace'], orbitron: ['Orbitron', 'sans-serif'] } } }
    }
  </script>
  <style>
    body { background-color: #03040a; background-image: radial-gradient(circle at 50% 0%, rgba(0, 243, 255, 0.05) 0%, transparent 50%), linear-gradient(rgba(0, 243, 255, 0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 243, 255, 0.02) 1px, transparent 1px); background-size: 100% 100%, 40px 40px, 40px 40px; -webkit-tap-highlight-color: transparent; }
    .glass { background: rgba(10, 15, 30, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(0, 243, 255, 0.15); }
    .neon-glow { text-shadow: 0 0 10px currentColor; }
    .scanline { position: relative; overflow: hidden; }
    .scanline::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, #00f3ff, transparent); animation: scan 3s linear infinite; }
    @keyframes scan { 0% { left: -100%; } 100% { left: 100%; } }
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-thumb { background: #00f3ff; border-radius: 4px; }
  </style>
</head>
<body class="text-slate-200 font-sans antialiased min-h-screen pb-10 selection:bg-neon-cyan selection:text-black">
  <div class="max-w-md mx-auto px-4 pt-6">
    <header class="flex justify-between items-center mb-6">
      <h1 class="font-orbitron font-black text-2xl text-white tracking-widest neon-glow" style="text-shadow: 0 0 15px #00f3ff;">AI QUANT <span class="text-neon-purple" style="text-shadow: 0 0 15px #b026ff;">X</span></h1>
      <div class="flex gap-2">
        <button onclick="openBacktest()" class="px-3 py-1.5 rounded-full border border-neon-purple text-neon-purple text-xs font-bold font-orbitron tracking-wider bg-[rgba(176,38,255,0.05)] active:scale-95 transition-all">TEST</button>
        <button id="pause-btn" onclick="togglePause()" class="px-3 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-green text-neon-green shadow-[0_0_10px_rgba(0,255,102,0.2)] bg-[rgba(0,255,102,0.05)]">● ACTIVE</button>
      </div>
    </header>

    <section class="text-center mb-8">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-1 font-mono">Total Estimated Value (USDT)</p>
      <h2 id="total-equity" class="font-mono text-5xl font-bold text-white tracking-tight mb-2">0.00</h2>
      <div id="pnl-display" class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-slate-800/50">
        <span id="pnl-value" class="text-slate-400">+0.00 USDT</span>
        <span id="pnl-percent" class="text-slate-500 text-xs">(0.00%)</span>
      </div>
    </section>

    <section class="glass rounded-2xl p-4 mb-6 scanline shadow-[0_0_20px_rgba(0,0,0,0.5)]">
      <div class="flex justify-between items-center mb-2">
         <h3 class="font-orbitron text-xs text-neon-cyan tracking-widest">EQUITY CURVE</h3>
         <span class="text-[10px] text-slate-500 font-mono">LIVE TELEMETRY</span>
      </div>
      <div class="h-48 w-full relative"><canvas id="equityChart"></canvas></div>
    </section>

    <section class="grid grid-cols-2 gap-3 mb-6">
      <div class="glass rounded-xl p-3 scanline">
        <p class="text-[10px] text-slate-400 font-mono uppercase mb-1">Win Rate</p>
        <p id="winrate" class="font-mono text-xl text-neon-purple font-bold neon-glow">--%</p>
      </div>
      <div class="glass rounded-xl p-3 scanline">
        <p class="text-[10px] text-slate-400 font-mono uppercase mb-1">Profit Factor</p>
        <p id="pf" class="font-mono text-xl text-neon-purple font-bold neon-glow">--</p>
      </div>
    </section>

    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">ACTIVE POSITIONS</h3>
        <span id="pos-count" class="text-xs text-slate-500 font-mono">0 Open</span>
      </div>
      <div id="active-positions-list" class="space-y-3"></div>
    </section>
  </div>

  <div id="backtest-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden items-center justify-center z-50 px-4">
    <div class="glass w-full max-w-md rounded-2xl p-6 relative border border-neon-purple/50 shadow-[0_0_30px_rgba(176,38,255,0.2)]">
      <button onclick="closeBacktest()" class="absolute top-4 right-4 text-slate-400 hover:text-white">✕</button>
      <h3 class="font-orbitron text-neon-purple text-lg mb-4 neon-glow">RUN BACKTEST</h3>
      <div class="space-y-4 mb-6">
        <select id="bt-symbol" class="w-full bg-brand-bg border border-slate-700 rounded-lg p-2 text-white outline-none focus:border-neon-purple">
          <option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option><option value="SOLUSDT">SOLUSDT</option>
        </select>
        <select id="bt-strat" class="w-full bg-brand-bg border border-slate-700 rounded-lg p-2 text-white outline-none focus:border-neon-purple">
          <option value="all">All Strategies</option><option value="trend">Trend</option><option value="mean_reversion">Mean Reversion</option><option value="breakout">Breakout</option>
        </select>
      </div>
      <button onclick="runBacktest()" id="bt-run-btn" class="w-full bg-neon-purple/20 border border-neon-purple text-neon-purple font-bold py-2 rounded-lg hover:bg-neon-purple/30 transition-all">Run Simulation</button>
      <div id="bt-results" class="mt-4 text-xs font-mono whitespace-pre-wrap hidden bg-black/50 p-3 rounded-lg border border-slate-800 max-h-48 overflow-y-auto"></div>
    </div>
  </div>

<script>
let chartInstance = null;
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

async function togglePause() {
    const btn = document.getElementById('pause-btn');
    btn.innerHTML = '...';
    const res = await fetch('/api/toggle_pause', { method: 'POST' });
    const data = await res.json();
    updatePauseButton(data.paused);
}

function updatePauseButton(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (isPaused) {
        btn.className = "px-3 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-red text-neon-red shadow-[0_0_10px_rgba(255,0,60,0.2)] bg-[rgba(255,0,60,0.05)]";
        btn.innerHTML = '■ PAUSED';
    } else {
        btn.className = "px-3 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-green text-neon-green shadow-[0_0_10px_rgba(0,255,102,0.2)] bg-[rgba(0,255,102,0.05)]";
        btn.innerHTML = '● ACTIVE';
    }
}

async function closePosition(id, symbol) {
    if(!confirm(`Close ${symbol}?`)) return;
    await fetch(`/api/close_position/${id}`, { method: 'POST' });
    load();
}

function openBacktest() { document.getElementById('backtest-modal').classList.remove('hidden'); document.getElementById('backtest-modal').classList.add('flex'); }
function closeBacktest() { document.getElementById('backtest-modal').classList.add('hidden'); document.getElementById('backtest-modal').classList.remove('flex'); }

async function runBacktest() {
    const symbol = document.getElementById('bt-symbol').value;
    const strat = document.getElementById('bt-strat').value;
    const btn = document.getElementById('bt-run-btn');
    const resDiv = document.getElementById('bt-results');
    
    btn.innerHTML = 'Running...';
    btn.disabled = true;
    resDiv.classList.add('hidden');
    
    try {
        const res = await fetch(`/api/run_backtest?symbol=${symbol}&strategy=${strat}`, { method: 'POST' });
        const data = await res.json();
        if(data.success) {
            resDiv.textContent = data.report;
            resDiv.classList.remove('hidden');
        } else {
            alert("Error: " + data.error);
        }
    } catch(e) { alert("Failed to run backtest"); }
    btn.innerHTML = 'Run Simulation';
    btn.disabled = false;
}

async function load(){
 try{
  const results = await Promise.allSettled([
      fetch('/api/portfolio').then(y=>y.json()), fetch('/api/risk').then(y=>y.json()),
      fetch('/api/positions').then(y=>y.json()), fetch('/api/performance').then(y=>y.json()),
      fetch('/api/status').then(y=>y.json())
  ]);
  
  const p = results[0].status === 'fulfilled' ? results[0].value : {equity: 0, cash_balance: 0, unrealized_pnl: 0, realized_pnl: 0};
  const r = results[1].status === 'fulfilled' ? results[1].value : {open_risk: 0, risk_cap: 0};
  const ps = results[2].status === 'fulfilled' ? results[2].value : [];
  const perf = results[3].status === 'fulfilled' ? results[3].value : {win_rate: 0, profit_factor: 0};
  const status = results[4].status === 'fulfilled' ? results[4].value : {paused: false};

  updatePauseButton(status.paused);
  document.getElementById('total-equity').textContent = fmt(p.equity);
  
  const pnlVal = p.unrealized_pnl + p.realized_pnl;
  const pnlPercent = (pnlVal / 200) * 100;
  const pnlDisplay = document.getElementById('pnl-display');
  document.getElementById('pnl-value').textContent = `${pnlVal >= 0 ? '+' : ''}${fmt(pnlVal)} USDT`;
  document.getElementById('pnl-percent').textContent = `(${pnlVal >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`;
  pnlDisplay.className = pnlVal > 0 ? "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-[rgba(0,255,102,0.1)] text-neon-green border border-[rgba(0,255,102,0.2)]" : (pnlVal < 0 ? "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-[rgba(255,0,60,0.1)] text-neon-red border border-[rgba(255,0,60,0.2)]" : "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-slate-800/50");

  document.getElementById('winrate').textContent = perf.win_rate ? fmt(perf.win_rate) + '%' : '0.00%';
  document.getElementById('pf').textContent = perf.profit_factor ? fmt(perf.profit_factor) : '0.00';

  const posContainer = document.getElementById('active-positions-list');
  document.getElementById('pos-count').textContent = `${ps.length} Open`;
  if(ps.length === 0) {
    posContainer.innerHTML = '<div class="text-center text-slate-500 text-sm py-4 glass rounded-xl">No active positions</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => `
      <div class="glass rounded-xl p-4 relative overflow-hidden border-l-2 ${pos.side === 'LONG' ? 'border-l-neon-green' : 'border-l-neon-red'}">
        <div class="flex justify-between items-start mb-2">
          <div><h4 class="font-bold text-white text-lg tracking-wide">${pos.symbol}</h4><span class="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">${pos.side}</span></div>
          <div class="text-right"><p class="text-[10px] text-slate-400 uppercase tracking-wider">Entry</p><p class="font-mono text-sm text-white">${Number(pos.entry_price).toFixed(4)}</p></div>
        </div>
        <div class="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-700/50">
           <div><p class="text-[10px] text-slate-500 uppercase">Target</p><p class="font-mono text-xs text-neon-green">${Number(pos.target_price).toFixed(4)}</p></div>
           <div class="text-right"><p class="text-[10px] text-slate-500 uppercase">Stop</p><p class="font-mono text-xs text-neon-red">${Number(pos.stop_price).toFixed(4)}</p></div>
        </div>
        <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="absolute top-2 right-2 text-[10px] font-bold text-neon-red border border-neon-red/30 px-2 py-1 rounded hover:bg-neon-red/10 active:scale-95 transition-all">CLOSE</button>
      </div>
    `).join('');
  }

  if(!chartInstance) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    let gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(0, 243, 255, 0.5)'); gradient.addColorStop(1, 'rgba(0, 243, 255, 0.0)');
    let tradesRes = await fetch('/api/trades').then(y=>y.json()).catch(()=>[]);
    let sortedTrades = tradesRes.filter(t => t.status === 'CLOSED').reverse();
    let labels = ['Start']; let data = [200]; 
    sortedTrades.forEach((t, index) => { labels.push('T' + (index+1)); data.push(data[data.length-1] + (Number(t.net_pnl) || 0)); });
    labels.push('Live'); data.push(p.equity);
    chartInstance = new Chart(ctx, {
        type: 'line', data: { labels: labels, datasets: [{ data: data, borderColor: '#00f3ff', backgroundColor: gradient, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, pointBackgroundColor: '#00f3ff', fill: true, tension: 0.4 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false, backgroundColor: 'rgba(0,0,0,0.8)', displayColors: false, callbacks: { label: function(context) { return '$' + fmt(context.parsed.y); } } } }, scales: { x: { display: false }, y: { display: false, grace: '15%' } }, interaction: { mode: 'nearest', axis: 'x', intersect: false } }
    });
  } else {
     chartInstance.data.datasets[0].data[chartInstance.data.datasets[0].data.length - 1] = p.equity;
     chartInstance.update('none'); 
  }
 }catch(e){ console.error('System Error:', e); }
}
load(); setInterval(load, 3000);
</script>
</body>
</html>""")

@router.get("/api/status")
async def status(request:Request): return request.app.state.engine.get_status()
@router.get("/api/portfolio")
async def portfolio(request:Request): return request.app.state.db.get_portfolio()
@router.get("/api/risk")
async def risk(request:Request): return request.app.state.engine.risk.get_risk_status()
@router.get("/api/positions")
async def positions(request:Request): return request.app.state.db.get_open_positions()
@router.get("/api/trades")
async def trades(request:Request): return request.app.state.db.get_recent_trades()
@router.get("/api/performance")
async def performance(request:Request): return request.app.state.db.get_performance()

@router.post("/api/toggle_pause")
async def toggle_pause(request:Request):
    engine = request.app.state.engine
    engine.set_paused(not engine.paused)
    return {"success": True, "paused": engine.paused}

@router.post("/api/close_position/{pos_id}")
async def close_position(request:Request, pos_id: int):
    try:
        db = request.app.state.db; engine = request.app.state.engine
        pos = db.get_position(pos_id)
        if not pos or pos["status"] != "OPEN": return JSONResponse({"success": False, "error": "Not found"}, status_code=400)
        prices = await engine.market.get_last_prices(pos["source"])
        if pos["symbol"] not in prices: return JSONResponse({"success": False, "error": "No price"}, status_code=400)
        engine.trader.close_position(pos_id, prices[pos["symbol"]]["last_price"], "MANUAL_UI")
        return {"success": True}
    except Exception as e: return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.post("/api/run_backtest")
async def run_backtest_api(request: Request, symbol: str = "BTCUSDT", strategy: str = "all"):
    try:
        engine = request.app.state.engine
        market = engine.market
        
        # --- تم التعديل هنا لاستخدام market.fetch_history بدلاً من الدالة المحذوفة ---
        df = await market.fetch_history(symbol, "1h", "futures", 1000)
        
        if df.empty: return {"success": False, "error": "Failed to fetch history"}
        strategies = None if strategy == "all" else [strategy]
        report = await asyncio.to_thread(run_backtest, df, strategies, "futures")
        report_text = format_report(symbol, report, "1h")
        return {"success": True, "report": report_text}
    except Exception as e:
        return {"success": False, "error": str(e)}
