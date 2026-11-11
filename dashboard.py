"""Nexus v2 UI with Smooth Binance-Style Chart."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI QUANT X · NEXUS V2</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {
  --bg: #03040a;
  --panel-bg: rgba(10, 15, 30, 0.7);
  --border: rgba(0, 243, 255, 0.15);
  --neon-cyan: #00f3ff;
  --neon-purple: #b026ff;
  --neon-green: #00ff66;
  --neon-red: #ff003c;
  --text-main: #e0f7fa;
  --text-muted: #6b7a99;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Share Tech Mono', monospace;
  background-color: var(--bg);
  background-image: 
    radial-gradient(circle at 50% 0%, rgba(0, 243, 255, 0.05) 0%, transparent 50%),
    linear-gradient(rgba(0, 243, 255, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 243, 255, 0.02) 1px, transparent 1px);
  background-size: 100% 100%, 40px 40px, 40px 40px;
  color: var(--text-main);
  min-height: 100vh;
  padding: 1.5rem;
  overflow-x: hidden;
}

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
h1 { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2.2rem; letter-spacing: 3px; color: #fff; text-shadow: 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan); }
h1 span { color: var(--neon-purple); text-shadow: 0 0 15px var(--neon-purple); }
.status-badge { border: 1px solid var(--neon-green); color: var(--neon-green); padding: 6px 16px; border-radius: 4px; font-size: 0.9rem; box-shadow: 0 0 15px rgba(0, 255, 102, 0.2); display: flex; align-items: center; gap: 10px; background: rgba(0, 255, 102, 0.05); font-family: 'Orbitron', sans-serif;}
.dot { width: 8px; height: 8px; background: var(--neon-green); border-radius: 50%; box-shadow: 0 0 10px var(--neon-green); animation: pulse 1.5s infinite; }

/* Grids */
.grid-top { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.grid-mid { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
@media (max-width: 900px) { .grid-mid { grid-template-columns: 1fr; } }

/* Cards */
.card {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.2rem;
  backdrop-filter: blur(15px);
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
  transition: all 0.3s ease;
}
.card:hover { border-color: rgba(0, 243, 255, 0.4); box-shadow: 0 0 20px rgba(0, 243, 255, 0.1); }
.card::before {
  content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
  animation: scanline 4s linear infinite;
}
.card-title { font-family: 'Orbitron', sans-serif; font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 0.5rem; }
.card-value { font-size: 1.8rem; font-weight: bold; text-shadow: 0 0 10px currentColor; }
.cyan { color: var(--neon-cyan); }
.green { color: var(--neon-green); }
.red { color: var(--neon-red); }
.purple { color: var(--neon-purple); }

/* Tables */
.table-wrapper { background: var(--panel-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
.table-title { font-family: 'Orbitron', sans-serif; padding: 1rem 1.2rem; background: rgba(0, 243, 255, 0.05); color: var(--neon-cyan); border-bottom: 1px solid var(--border); font-size: 0.9rem; display: flex; justify-content: space-between;}
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
th { padding: 0.8rem 1.2rem; color: var(--text-muted); border-bottom: 1px solid rgba(255,255,255,0.05); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px; }
td { padding: 0.8rem 1.2rem; border-bottom: 1px solid rgba(255, 255, 255, 0.02); }
tr:hover td { background: rgba(0, 243, 255, 0.03); }
tr.win-row:hover td { background: rgba(0, 255, 102, 0.05); }
tr.loss-row:hover td { background: rgba(255, 0, 60, 0.05); }

/* Badges */
.badge { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; }
.badge-long { border: 1px solid var(--neon-green); color: var(--neon-green); background: rgba(0, 255, 102, 0.1); }
.badge-short { border: 1px solid var(--neon-red); color: var(--neon-red); background: rgba(255, 0, 60, 0.1); }
.badge-hold { border: 1px solid var(--text-muted); color: var(--text-muted); }
.badge-win { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
.badge-loss { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }

/* Chart Container */
.chart-container { 
  background: var(--panel-bg); 
  border: 1px solid rgba(176, 38, 255, 0.2); 
  border-radius: 8px; 
  padding: 1.2rem; 
  position: relative;
  height: 350px; /* تثبيت الارتفاع لمنع التمدد */
  min-height: 350px; 
}
.chart-container h2 { font-family: 'Orbitron', sans-serif; color: var(--neon-purple); font-size: 0.9rem; margin-bottom: 1rem; text-shadow: 0 0 5px var(--neon-purple); letter-spacing: 1px;}
.chart-container canvas { max-height: 280px; }

@keyframes pulse { 0% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.2); opacity: 0.5; } 100% { transform: scale(1); opacity: 1; } }
@keyframes scanline { 0% { left: -100%; } 100% { left: 100%; } }
</style></head>
<body>

<div class="header">
  <h1>AI QUANT <span>X</span></h1>
  <div class="status-badge"><div class="dot"></div> NEXUS v2.0 ONLINE</div>
</div>

<!-- Top Stats -->
<section class="grid-top">
  <div class="card"><div class="card-title">Virtual Equity</div><div class="card-value cyan" id="equity">—</div></div>
  <div class="card"><div class="card-title">Cash Balance</div><div class="card-value" id="cash">—</div></div>
  <div class="card"><div class="card-title">Unrealized PnL</div><div class="card-value" id="unrealized">—</div></div>
  <div class="card"><div class="card-title">Realized PnL</div><div class="card-value" id="realized">—</div></div>
  <div class="card"><div class="card-title">Win Rate</div><div class="card-value purple" id="winrate">—</div></div>
  <div class="card"><div class="card-title">Profit Factor</div><div class="card-value purple" id="pf">—</div></div>
</section>

<!-- Chart & Active Positions -->
<div class="grid-mid">
  <div class="chart-container">
    <h2>EQUITY CURVE // LIVE TELEMETRY</h2>
    <canvas id="equityChart"></canvas>
  </div>
  
  <div class="card" style="border-color: rgba(0, 255, 102, 0.3);">
    <div class="card-title" style="color:var(--neon-green);">Open Risk Status</div>
    <div class="card-value green" id="risk" style="font-size:1.5rem; margin-bottom:1rem;">—</div>
    <div style="font-size:0.8rem; color:var(--text-muted);">Capital at risk across active simulated positions.</div>
  </div>
</div>

<!-- Active Positions -->
<div class="table-wrapper">
  <div class="table-title">ACTIVE POSITIONS</div>
  <table>
    <thead><tr><th>Asset</th><th>Side</th><th>Qty</th><th>Entry</th><th>Stop</th><th>Target</th><th>Strategy</th></tr></thead>
    <tbody id="positions-body"><tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Scanning network...</td></tr></tbody>
  </table>
</div>

<!-- Trade History (Wins & Losses) -->
<div class="table-wrapper" style="border-color: rgba(176, 38, 255, 0.3);">
  <div class="table-title" style="color:var(--neon-purple); background:rgba(176, 38, 255, 0.05);">TRADE HISTORY // WINS & LOSSES</div>
  <table>
    <thead><tr><th>Time Closed</th><th>Asset</th><th>Side</th><th>Entry</th><th>Exit</th><th>Net PnL (USDT)</th><th>Reason</th></tr></thead>
    <tbody id="history-body"><tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Loading history matrix...</td></tr></tbody>
  </table>
</div>

<!-- Recent Decisions -->
<div class="table-wrapper">
  <div class="table-title">AI NEURAL DECISION LOG</div>
  <table>
    <thead><tr><th>Time</th><th>Asset</th><th>Action</th><th>Score</th><th>Reasoning</th></tr></thead>
    <tbody id="decisions-body"><tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Loading logs...</td></tr></tbody>
  </table>
</div>

<script>
let chartInstance = null;
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

async function load(){
 try{
  const [p, r, ps, ds, trades, perf] = await Promise.all([
      fetch('/api/portfolio').then(y=>y.json()),
      fetch('/api/risk').then(y=>y.json()),
      fetch('/api/positions').then(y=>y.json()),
      fetch('/api/decisions').then(y=>y.json()),
      fetch('/api/trades').then(y=>y.json()),
      fetch('/api/performance').then(y=>y.json())
  ]);
  
  // 1. Update Top Stats
  document.getElementById('equity').textContent = fmt(p.equity) + ' USDT';
  document.getElementById('cash').textContent = fmt(p.cash_balance) + ' USDT';
  
  const unrl = document.getElementById('unrealized');
  unrl.textContent = fmt(p.unrealized_pnl) + ' USDT';
  unrl.className = 'card-value ' + (p.unrealized_pnl > 0 ? 'green' : p.unrealized_pnl < 0 ? 'red' : '');

  const rl = document.getElementById('realized');
  rl.textContent = fmt(p.realized_pnl) + ' USDT';
  rl.className = 'card-value ' + (p.realized_pnl > 0 ? 'green' : p.realized_pnl < 0 ? 'red' : '');

  document.getElementById('winrate').textContent = perf.win_rate ? fmt(perf.win_rate) + '%' : '0.00%';
  document.getElementById('pf').textContent = perf.profit_factor ? fmt(perf.profit_factor) : '0.00';
  document.getElementById('risk').textContent = fmt(r.open_risk) + ' / ' + fmt(r.risk_cap) + ' USDT';

  // 2. Active Positions
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
        <td style="color:var(--neon-purple); font-size:0.8rem;">${pos.strategy || 'N/A'}</td>
      </tr>
    `).join('');
  }

  // 3. Trade History (Wins & Losses)
  const hb = document.getElementById('history-body');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 15);
  
  if(closedTrades.length === 0) {
    hb.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No closed trades yet.</td></tr>';
  } else {
    hb.innerHTML = closedTrades.map(t => {
      const isWin = t.net_pnl > 0;
      const pnlClass = isWin ? 'badge-win' : 'badge-loss';
      const rowClass = isWin ? 'win-row' : 'loss-row';
      const time = new Date(t.closed_at).toLocaleTimeString();
      
      return `
        <tr class="${rowClass}">
          <td style="color:var(--text-muted); font-size:0.8rem;">${time}</td>
          <td style="font-weight:bold;">${t.symbol}</td>
          <td><span class="badge ${t.side === 'LONG' ? 'badge-long' : 'badge-short'}">${t.side}</span></td>
          <td>${Number(t.entry_price).toFixed(4)}</td>
          <td>${Number(t.exit_price).toFixed(4)}</td>
          <td class="${pnlClass}" style="font-weight:bold; font-size:1.1rem;">${isWin ? '+' : ''}${fmt(t.net_pnl)}</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${t.exit_reason}</td>
        </tr>
      `;
    }).join('');
  }

  // 4. Decisions
  const db = document.getElementById('decisions-body');
  if(ds.length === 0) {
    db.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No logs available.</td></tr>';
  } else {
    db.innerHTML = ds.slice(0, 8).map(d => {
      const time = new Date(d.created_at).toLocaleTimeString();
      let badgeClass = 'badge-hold';
      if(d.action.includes('BUY')) badgeClass = 'badge-long';
      if(d.action.includes('SHORT')) badgeClass = 'badge-short';
      return `
        <tr>
          <td style="color:var(--text-muted); font-size:0.8rem;">${time}</td>
          <td style="font-weight:bold;">${d.symbol}</td>
          <td><span class="badge ${badgeClass}">${d.action}</span></td>
          <td class="purple">${d.score}</td>
          <td style="font-size:0.8rem; color:var(--text-muted); max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${d.reason}">${d.reason}</td>
        </tr>
      `;
    }).join('');
  }

  // 5. Chart Rendering (Smooth Binance-Style Curve)
  if(!chartInstance) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    
    // تدرج لوني نيون (Cyan) يختفي في الأسفل
    let gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(0, 243, 255, 0.4)'); 
    gradient.addColorStop(1, 'rgba(0, 243, 255, 0.0)');

    // بناء البيانات من الصفقات
    let sortedTrades = trades.filter(t => t.status === 'CLOSED').reverse();
    let labels = ['Start'];
    let data = [200]; // الرصيد الابتدائي
    
    sortedTrades.forEach((t, index) => {
        labels.push('T' + (index+1));
        data.push(data[data.length-1] + (Number(t.net_pnl) || 0));
    });
    
    // إضافة الرصيد الحالي
    labels.push('Live');
    data.push(p.equity);

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Equity',
                data: data,
                borderColor: '#00f3ff', // لون الخط (سماوي نيون)
                backgroundColor: gradient, // التدرج اللوني تحته
                borderWidth: 3,
                pointRadius: 0, // إخفاء النقاط لجعله خطاً ناعماً
                pointHoverRadius: 6,
                pointBackgroundColor: '#00f3ff',
                fill: true,
                tension: 0.4 // هذا هو السطر السحري الذي يجعل الخط "مموجاً" وناعماً
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
                    displayColors: false
                } 
            },
            scales: {
                x: { 
                    display: false // إخفاء المحور السيني (مثل بينانس)
                },
                y: { 
                    display: false, // إخفاء المحور الصادي (مثل بينانس)
                    grace: '15%' // إعطاء هامش علوي وسفلي للرسم
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
  } else {
     // تحديث النقطة الأخيرة بصمت دون إعادة رسم كامل
     chartInstance.data.datasets[0].data[chartInstance.data.datasets[0].data.length - 1] = p.equity;
     chartInstance.update('none'); 
  }

 }catch(e){ console.error('System Error:', e); }
}

load(); setInterval(load, 5000);
</script></body></html>""")

# (باقي المسارات API كما هي)
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
