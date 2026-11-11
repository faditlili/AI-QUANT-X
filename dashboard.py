"""Futuristic & Premium Cyberpunk Dashboard."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI QUANT X · NEXUS UI</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {
  --bg: #05050f;
  --grid-line: rgba(0, 255, 255, 0.05);
  --panel-bg: rgba(10, 15, 30, 0.6);
  --neon-cyan: #00f3ff;
  --neon-purple: #b026ff;
  --neon-green: #00ff66;
  --neon-red: #ff003c;
  --text-main: #e0f7fa;
  --text-muted: #7986cb;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Share Tech Mono', monospace;
  background-color: var(--bg);
  background-image: 
    linear-gradient(var(--grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 30px 30px;
  color: var(--text-main);
  min-height: 100vh;
  padding: 2rem;
  overflow-x: hidden;
}

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid rgba(0, 243, 255, 0.2); padding-bottom: 1rem; }
h1 { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2rem; letter-spacing: 2px; text-shadow: 0 0 10px var(--neon-cyan); color: #fff; }
h1 span { color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }
.status-badge { border: 1px solid var(--neon-green); color: var(--neon-green); padding: 5px 15px; border-radius: 4px; font-size: 0.9rem; box-shadow: 0 0 10px rgba(0, 255, 102, 0.2); display: flex; align-items: center; gap: 8px; background: rgba(0, 255, 102, 0.05); }
.dot { width: 10px; height: 10px; background: var(--neon-green); border-radius: 50%; animation: pulse 1.5s infinite; }

/* Grid Layout */
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }

/* Neon Cards */
.card {
  background: var(--panel-bg);
  border: 1px solid rgba(0, 243, 255, 0.2);
  border-radius: 8px;
  padding: 1.5rem;
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
  animation: scan 3s linear infinite;
}
.card:hover { box-shadow: 0 0 20px rgba(0, 243, 255, 0.15); border-color: var(--neon-cyan); transform: translateY(-2px); }
.card-title { font-family: 'Orbitron', sans-serif; font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.8rem; }
.card-value { font-size: 2rem; font-weight: bold; text-shadow: 0 0 8px currentColor; }
.cyan { color: var(--neon-cyan); }
.green { color: var(--neon-green); }
.red { color: var(--neon-red); }
.purple { color: var(--neon-purple); }

/* Chart Section */
.chart-container { background: var(--panel-bg); border: 1px solid rgba(176, 38, 255, 0.3); border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 0 20px rgba(176, 38, 255, 0.05); }
.chart-container h2 { font-family: 'Orbitron', sans-serif; color: var(--neon-purple); font-size: 1.1rem; margin-bottom: 1rem; text-shadow: 0 0 5px var(--neon-purple); }

/* Tables */
.table-wrapper { background: var(--panel-bg); border: 1px solid rgba(0, 243, 255, 0.2); border-radius: 8px; overflow: hidden; margin-bottom: 2rem; }
.table-title { font-family: 'Orbitron', sans-serif; padding: 1rem 1.5rem; background: rgba(0, 243, 255, 0.05); color: var(--neon-cyan); border-bottom: 1px solid rgba(0, 243, 255, 0.2); font-size: 1rem; }
table { width: 100%; border-collapse: collapse; text-align: left; }
th { padding: 1rem 1.5rem; font-size: 0.85rem; color: var(--text-muted); border-bottom: 1px solid rgba(255,255,255,0.05); text-transform: uppercase; }
td { padding: 1rem 1.5rem; font-size: 0.95rem; border-bottom: 1px solid rgba(255, 255, 255, 0.02); }
tr:hover td { background: rgba(0, 243, 255, 0.03); }

/* Badges */
.badge { padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; letter-spacing: 1px; }
.badge-long { border: 1px solid var(--neon-green); color: var(--neon-green); background: rgba(0, 255, 102, 0.1); box-shadow: 0 0 8px rgba(0, 255, 102, 0.2); }
.badge-short { border: 1px solid var(--neon-red); color: var(--neon-red); background: rgba(255, 0, 60, 0.1); box-shadow: 0 0 8px rgba(255, 0, 60, 0.2); }
.badge-hold { border: 1px solid var(--text-muted); color: var(--text-muted); background: rgba(121, 134, 203, 0.1); }

@keyframes pulse { 0% { opacity: 1; box-shadow: 0 0 10px var(--neon-green); } 50% { opacity: 0.5; box-shadow: 0 0 2px var(--neon-green); } 100% { opacity: 1; box-shadow: 0 0 10px var(--neon-green); } }
@keyframes scan { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
</style></head>
<body>
<div class="header">
  <h1>AI QUANT <span>X</span></h1>
  <div class="status-badge"><div class="dot"></div> SYSTEM ONLINE</div>
</div>

<section class="grid">
  <div class="card"><div class="card-title">Virtual Equity</div><div class="card-value cyan" id="equity">—</div></div>
  <div class="card"><div class="card-title">Cash Balance</div><div class="card-value" id="cash">—</div></div>
  <div class="card"><div class="card-title">Unrealized PnL</div><div class="card-value" id="unrealized">—</div></div>
  <div class="card"><div class="card-title">Realized PnL</div><div class="card-value" id="realized">—</div></div>
  <div class="card"><div class="card-title">Open Risk / Cap</div><div class="card-value purple" id="risk" style="font-size:1.5rem;">—</div></div>
</section>

<div class="chart-container">
  <h2>EQUITY CURVE // HISTORY</h2>
  <canvas id="equityChart" height="80"></canvas>
</div>

<div class="table-wrapper">
  <div class="table-title">ACTIVE POSITIONS</div>
  <table>
    <thead><tr><th>Asset</th><th>Side</th><th>Qty</th><th>Entry</th><th>Stop</th><th>Target</th><th>Risk (USDT)</th></tr></thead>
    <tbody id="positions-body"><tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Scanning network...</td></tr></tbody>
  </table>
</div>

<div class="table-wrapper">
  <div class="table-title">AI DECISION LOG</div>
  <table>
    <thead><tr><th>Time</th><th>Asset</th><th>Action</th><th>Score</th><th>Reasoning Core</th></tr></thead>
    <tbody id="decisions-body"><tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Loading neural logs...</td></tr></tbody>
  </table>
</div>

<script>
let chartInstance = null;

function formatNum(n) { return Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

async function load(){
 try{
  const [p, r, ps, ds, trades] = await Promise.all([
      fetch('/api/portfolio').then(y=>y.json()),
      fetch('/api/risk').then(y=>y.json()),
      fetch('/api/positions').then(y=>y.json()),
      fetch('/api/decisions').then(y=>y.json()),
      fetch('/api/trades').then(y=>y.json())
  ]);
  
  // Update Stats
  document.getElementById('equity').textContent = formatNum(p.equity) + ' USDT';
  document.getElementById('cash').textContent = formatNum(p.cash_balance) + ' USDT';
  
  const unrl = document.getElementById('unrealized');
  unrl.textContent = formatNum(p.unrealized_pnl) + ' USDT';
  unrl.className = 'card-value ' + (p.unrealized_pnl > 0 ? 'green' : p.unrealized_pnl < 0 ? 'red' : '');

  const rl = document.getElementById('realized');
  rl.textContent = formatNum(p.realized_pnl) + ' USDT';
  rl.className = 'card-value ' + (p.realized_pnl > 0 ? 'green' : p.realized_pnl < 0 ? 'red' : '');

  document.getElementById('risk').textContent = formatNum(r.open_risk) + ' / ' + formatNum(r.risk_cap);

  // Positions Table
  const pb = document.getElementById('positions-body');
  if(ps.length === 0) {
    pb.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No active positions.</td></tr>';
  } else {
    pb.innerHTML = ps.map(pos => `
      <tr>
        <td style="color:var(--neon-cyan); font-weight:bold;">${pos.symbol}</td>
        <td><span class="badge ${pos.side === 'LONG' ? 'badge-long' : 'badge-short'}">${pos.side}</span></td>
        <td>${Number(pos.quantity).toFixed(4)}</td>
        <td>${Number(pos.entry_price).toFixed(4)}</td>
        <td style="color:var(--neon-red);">${Number(pos.stop_price).toFixed(4)}</td>
        <td style="color:var(--neon-green);">${Number(pos.target_price).toFixed(4)}</td>
        <td class="purple">${Number(pos.risk_amount).toFixed(2)}</td>
      </tr>
    `).join('');
  }

  // Decisions Table
  const db = document.getElementById('decisions-body');
  if(ds.length === 0) {
    db.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No logs available.</td></tr>';
  } else {
    db.innerHTML = ds.slice(0, 10).map(d => {
      const time = new Date(d.created_at).toLocaleTimeString();
      let badgeClass = 'badge-hold';
      if(d.action.includes('BUY')) badgeClass = 'badge-long';
      if(d.action.includes('SHORT')) badgeClass = 'badge-short';
      return `
        <tr>
          <td style="color:var(--text-muted); font-size:0.85rem;">${time}</td>
          <td style="font-weight:bold;">${d.symbol}</td>
          <td><span class="badge ${badgeClass}">${d.action}</span></td>
          <td class="purple">${d.score}</td>
          <td style="font-size:0.85rem; color:var(--text-muted);">${d.reason}</td>
        </tr>
      `;
    }).join('');
  }

  // --- Render Chart (Equity Curve) ---
  // Simple logic to build a mock equity curve from recent trades to make it look awesome
  if(!chartInstance) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    let gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(0, 243, 255, 0.5)');
    gradient.addColorStop(1, 'rgba(0, 243, 255, 0.0)');

    // Reverse trades to chronological order
    let sortedTrades = trades.slice().reverse();
    let labels = ['Start'];
    let data = [200]; // Initial balance
    
    // If there's no history, add a fake point to make the chart show
    if(sortedTrades.length === 0) {
        labels.push('Now');
        data.push(p.equity);
    } else {
        sortedTrades.forEach((t, index) => {
            if(t.status === 'CLOSED') {
                labels.push('T' + (index+1));
                data.push(data[data.length-1] + (Number(t.net_pnl) || 0));
            }
        });
        // Add current open equity at the end
        labels.push('Live');
        data.push(p.equity);
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Portfolio Equity',
                data: data,
                borderColor: '#00f3ff',
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: '#b026ff',
                pointBorderColor: '#fff',
                pointRadius: 3,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index', intersect: false,
                    backgroundColor: 'rgba(5, 5, 15, 0.9)',
                    titleColor: '#00f3ff', bodyColor: '#fff',
                    borderColor: '#00f3ff', borderWidth: 1
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7986cb' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7986cb' } }
            }
        }
    });
  } else {
     // Just update the last data point if chart already exists
     chartInstance.data.datasets[0].data[chartInstance.data.datasets[0].data.length - 1] = p.equity;
     chartInstance.update();
  }

 }catch(e){ console.error('System Error:', e); }
}

load(); setInterval(load, 5000);
</script></body></html>""")

@router.get("/api/status")
async def status(request:Request):
    return request.app.state.engine.get_status()

@router.get("/api/portfolio")
async def portfolio(request:Request):
    return request.app.state.db.get_portfolio()

@router.get("/api/risk")
async def risk(request:Request):
    return request.app.state.engine.risk.get_risk_status()

@router.get("/api/positions")
async def positions(request:Request):
    return request.app.state.db.get_open_positions()

@router.get("/api/trades")
async def trades(request:Request):
    return request.app.state.db.get_recent_trades()

@router.get("/api/performance")
async def performance(request:Request):
    return request.app.state.db.get_performance()

@router.get("/api/decisions")
async def decisions(request:Request):
    return request.app.state.db.get_recent_decisions()

@router.get("/api/strategies")
async def strategies(request:Request):
    return request.app.state.db.get_performance_by_strategy()
