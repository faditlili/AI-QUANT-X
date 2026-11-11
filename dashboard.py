"""Ultimate Mobile-First Trading Dashboard with Controls."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    # باستخدام Tailwind CSS لتصميم متجاوب وسريع
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
      theme: {
        extend: {
          colors: {
            brand: { bg: '#03040a', card: '#0a0f1e', border: '#1e293b' },
            neon: { cyan: '#00f3ff', green: '#00ff66', red: '#ff003c', purple: '#b026ff' }
          },
          fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Share Tech Mono', 'monospace'], orbitron: ['Orbitron', 'sans-serif'] }
        }
      }
    }
  </script>
  <style>
    body { background-color: #03040a; background-image: radial-gradient(circle at 50% 0%, rgba(0, 243, 255, 0.05) 0%, transparent 50%), linear-gradient(rgba(0, 243, 255, 0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 243, 255, 0.02) 1px, transparent 1px); background-size: 100% 100%, 40px 40px, 40px 40px; -webkit-tap-highlight-color: transparent; }
    .glass { background: rgba(10, 15, 30, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(0, 243, 255, 0.15); }
    .neon-glow { text-shadow: 0 0 10px currentColor; }
    .scanline { position: relative; overflow: hidden; }
    .scanline::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, #00f3ff, transparent); animation: scan 3s linear infinite; }
    @keyframes scan { 0% { left: -100%; } 100% { left: 100%; } }
    /* Custom Scrollbar for mobile */
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #00f3ff; border-radius: 4px; }
  </style>
</head>
<body class="text-slate-200 font-sans antialiased min-h-screen pb-10 selection:bg-neon-cyan selection:text-black">

  <div class="max-w-md mx-auto px-4 pt-6">
    
    <!-- Header -->
    <header class="flex justify-between items-center mb-6">
      <h1 class="font-orbitron font-black text-2xl text-white tracking-widest neon-glow" style="text-shadow: 0 0 15px #00f3ff;">AI QUANT <span class="text-neon-purple" style="text-shadow: 0 0 15px #b026ff;">X</span></h1>
      <button id="pause-btn" onclick="togglePause()" class="px-4 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-green text-neon-green shadow-[0_0_10px_rgba(0,255,102,0.2)] bg-[rgba(0,255,102,0.05)]">
        ● ACTIVE
      </button>
    </header>

    <!-- Balance Section -->
    <section class="text-center mb-8">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-1 font-mono">Total Estimated Value (USDT)</p>
      <h2 id="total-equity" class="font-mono text-5xl font-bold text-white tracking-tight mb-2">0.00</h2>
      <div id="pnl-display" class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-slate-800/50">
        <span id="pnl-value" class="text-slate-400">+0.00 USDT</span>
        <span id="pnl-percent" class="text-slate-500 text-xs">(0.00%)</span>
      </div>
    </section>

    <!-- Chart Section -->
    <section class="glass rounded-2xl p-4 mb-6 scanline shadow-[0_0_20px_rgba(0,0,0,0.5)]">
      <div class="flex justify-between items-center mb-2">
         <h3 class="font-orbitron text-xs text-neon-cyan tracking-widest">EQUITY CURVE</h3>
         <span class="text-[10px] text-slate-500 font-mono">LIVE TELEMETRY</span>
      </div>
      <div class="h-48 w-full relative">
        <canvas id="equityChart"></canvas>
      </div>
    </section>

    <!-- Quick Stats Grid -->
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

    <!-- Active Positions -->
    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">ACTIVE POSITIONS</h3>
        <span id="pos-count" class="text-xs text-slate-500 font-mono">0 Open</span>
      </div>
      <div id="active-positions-list" class="space-y-3">
        <!-- Position Cards Injected Here -->
        <div class="text-center text-slate-500 text-sm py-4 glass rounded-xl">Scanning network...</div>
      </div>
    </section>

    <!-- Recent Trades (History) -->
    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">RECENT TRADES</h3>
      </div>
      <div id="history-list" class="space-y-2">
        <!-- History Cards Injected Here -->
      </div>
    </section>

  </div>

<script>
let chartInstance = null;
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

// --- INTERACTIVE CONTROLS ---
async function togglePause() {
    const btn = document.getElementById('pause-btn');
    btn.innerHTML = '...';
    try {
        const res = await fetch('/api/toggle_pause', { method: 'POST' });
        const data = await res.json();
        updatePauseButton(data.paused);
    } catch(e) {
        console.error(e);
        btn.innerHTML = 'ERR';
    }
}

function updatePauseButton(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (isPaused) {
        btn.className = "px-4 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-red text-neon-red shadow-[0_0_10px_rgba(255,0,60,0.2)] bg-[rgba(255,0,60,0.05)]";
        btn.innerHTML = '■ PAUSED';
    } else {
        btn.className = "px-4 py-1.5 rounded-full border text-xs font-bold font-orbitron tracking-wider transition-all active:scale-95 border-neon-green text-neon-green shadow-[0_0_10px_rgba(0,255,102,0.2)] bg-[rgba(0,255,102,0.05)]";
        btn.innerHTML = '● ACTIVE';
    }
}

async function closePosition(id, symbol) {
    if(!confirm(`Are you sure you want to close ${symbol}?`)) return;
    try {
        const res = await fetch(`/api/close_position/${id}`, { method: 'POST' });
        const data = await res.json();
        if(data.success) {
            load(); // Refresh UI immediately
        } else {
            alert("Error: " + data.error);
        }
    } catch(e) { alert("Failed to close position."); }
}

// --- MAIN DATA FETCHING ---
async function load(){
 try{
  const [p, r, ps, trades, perf, status] = await Promise.all([
      fetch('/api/portfolio').then(y=>y.json()),
      fetch('/api/risk').then(y=>y.json()),
      fetch('/api/positions').then(y=>y.json()),
      fetch('/api/trades').then(y=>y.json()),
      fetch('/api/performance').then(y=>y.json()),
      fetch('/api/status').then(y=>y.json())
  ]);
  
  // 1. Update Header & Balance
  updatePauseButton(status.paused);
  document.getElementById('total-equity').textContent = fmt(p.equity);
  
  const pnlVal = p.unrealized_pnl + p.realized_pnl;
  const pnlPercent = (pnlVal / 200) * 100;
  const pnlDisplay = document.getElementById('pnl-display');
  const pnlValue = document.getElementById('pnl-value');
  const pnlPercentEl = document.getElementById('pnl-percent');
  
  pnlValue.textContent = `${pnlVal >= 0 ? '+' : ''}${fmt(pnlVal)} USDT`;
  pnlPercentEl.textContent = `(${pnlVal >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`;
  
  if (pnlVal > 0) {
      pnlDisplay.className = "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-[rgba(0,255,102,0.1)] text-neon-green border border-[rgba(0,255,102,0.2)]";
  } else if (pnlVal < 0) {
      pnlDisplay.className = "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-[rgba(255,0,60,0.1)] text-neon-red border border-[rgba(255,0,60,0.2)]";
  }

  document.getElementById('winrate').textContent = perf.win_rate ? fmt(perf.win_rate) + '%' : '0.00%';
  document.getElementById('pf').textContent = perf.profit_factor ? fmt(perf.profit_factor) : '0.00';

  // 2. Render Active Positions (Cards)
  const posContainer = document.getElementById('active-positions-list');
  document.getElementById('pos-count').textContent = `${ps.length} Open`;
  
  if(ps.length === 0) {
    posContainer.innerHTML = '<div class="text-center text-slate-500 text-sm py-4 glass rounded-xl">No active positions</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => `
      <div class="glass rounded-xl p-4 relative overflow-hidden border-l-2 ${pos.side === 'LONG' ? 'border-l-neon-green' : 'border-l-neon-red'}">
        <div class="flex justify-between items-start mb-2">
          <div>
            <h4 class="font-bold text-white text-lg tracking-wide">${pos.symbol}</h4>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">${pos.side}</span>
          </div>
          <div class="text-right">
            <p class="text-[10px] text-slate-400 uppercase tracking-wider">Entry</p>
            <p class="font-mono text-sm text-white">${Number(pos.entry_price).toFixed(4)}</p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-700/50">
           <div>
             <p class="text-[10px] text-slate-500 uppercase">Target</p>
             <p class="font-mono text-xs text-neon-green">${Number(pos.target_price).toFixed(4)}</p>
           </div>
           <div class="text-right">
             <p class="text-[10px] text-slate-500 uppercase">Stop</p>
             <p class="font-mono text-xs text-neon-red">${Number(pos.stop_price).toFixed(4)}</p>
           </div>
        </div>
        <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="absolute top-2 right-2 text-[10px] font-bold text-neon-red border border-neon-red/30 px-2 py-1 rounded hover:bg-neon-red/10 active:scale-95 transition-all">CLOSE</button>
      </div>
    `).join('');
  }

  // 3. Render History (Wins/Losses List)
  const histContainer = document.getElementById('history-list');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 8); // Last 8
  
  if(closedTrades.length === 0) {
    histContainer.innerHTML = '<div class="text-center text-slate-500 text-sm py-2">No recent trades</div>';
  } else {
    histContainer.innerHTML = closedTrades.map(t => {
      const isWin = t.net_pnl > 0;
      return `
        <div class="glass rounded-lg p-3 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold ${isWin ? 'bg-[rgba(0,255,102,0.1)] text-neon-green' : 'bg-[rgba(255,0,60,0.1)] text-neon-red'}">
              ${t.side === 'LONG' ? 'L' : 'S'}
            </div>
            <div>
              <p class="font-bold text-sm text-slate-200">${t.symbol}</p>
              <p class="text-[10px] text-slate-500">${new Date(t.closed_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
            </div>
          </div>
          <div class="text-right">
            <p class="font-mono text-sm font-bold ${isWin ? 'text-neon-green' : 'text-neon-red'}">${isWin ? '+' : ''}${fmt(t.net_pnl)}</p>
            <p class="text-[9px] text-slate-500 uppercase">${t.exit_reason}</p>
          </div>
        </div>
      `;
    }).join('');
  }

  // 4. Chart Rendering (Smooth Curve)
  if(!chartInstance) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    let gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(0, 243, 255, 0.5)'); 
    gradient.addColorStop(1, 'rgba(0, 243, 255, 0.0)');

    let sortedTrades = trades.filter(t => t.status === 'CLOSED').reverse();
    let labels = ['Start'];
    let data = [200]; 
    
    sortedTrades.forEach((t, index) => {
        labels.push('T' + (index+1));
        data.push(data[data.length-1] + (Number(t.net_pnl) || 0));
    });
    
    labels.push('Live');
    data.push(p.equity);

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                borderColor: '#00f3ff',
                backgroundColor: gradient,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointBackgroundColor: '#00f3ff',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true, 
            maintainAspectRatio: false, 
            plugins: { 
                legend: { display: false }, 
                tooltip: { 
                    mode: 'index', 
                    intersect: false, 
                    backgroundColor: 'rgba(0,0,0,0.8)', 
                    titleColor: '#00f3ff',
                    bodyColor: '#fff',
                    displayColors: false,
                    callbacks: { label: function(context) { return '$' + fmt(context.parsed.y); } }
                } 
            },
            scales: {
                x: { display: false },
                y: { display: false, grace: '15%' }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false }
        }
    });
  } else {
     chartInstance.data.datasets[0].data[chartInstance.data.datasets[0].data.length - 1] = p.equity;
     chartInstance.update('none'); 
  }

 }catch(e){ console.error('System Error:', e); }
}

load(); setInterval(load, 3000); // تحديث أسرع (كل 3 ثوانٍ)
</script>
</body>
</html>""")

# --- API ENDPOINTS ---
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
@router.get("/api/decisions")
async def decisions(request:Request): return request.app.state.db.get_recent_decisions()

# --- NEW CONTROL ENDPOINTS ---
@router.post("/api/toggle_pause")
async def toggle_pause(request:Request):
    engine = request.app.state.engine
    engine.set_paused(not engine.paused)
    return {"success": True, "paused": engine.paused}

@router.post("/api/close_position/{pos_id}")
async def close_position(request:Request, pos_id: int):
    try:
        db = request.app.state.db
        engine = request.app.state.engine
        pos = db.get_position(pos_id)
        if not pos or pos["status"] != "OPEN":
            return JSONResponse({"success": False, "error": "Position not found or already closed"}, status_code=400)
        
        # Get current market price for the symbol
        prices = await engine.market.get_last_prices(pos["source"])
        if pos["symbol"] not in prices:
            return JSONResponse({"success": False, "error": "Could not fetch current price"}, status_code=400)
        
        current_price = prices[pos["symbol"]]["last_price"]
        
        # Close the position
        engine.trader.close_position(pos_id, current_price, "MANUAL_UI")
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
