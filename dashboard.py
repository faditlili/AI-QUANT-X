"""The Absolute Best FastAPI Dashboard - SaaS Edition with Live PnL & Toasts."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
from backtest import run_backtest, format_report
import config

router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>AI QUANT X · SaaS Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: { 
        extend: { 
          colors: { 
            brand: { bg: '#f8fafc', card: '#ffffff', border: '#e2e8f0', text: '#0f172a', muted: '#64748b' },
            green: '#10b981', red: '#ef4444', blue: '#3b82f6', purple: '#8b5cf6'
          }, 
          fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Share Tech Mono', 'monospace'] } 
        } 
      }
    }
  </script>
  <style>
    body { background-color: #f8fafc; font-family: 'Inter', sans-serif; color: #0f172a; -webkit-tap-highlight-color: transparent; }
    .card { background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03); border-radius: 1rem; transition: all 0.2s ease; }
    .card:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); transform: translateY(-2px); }
    
    /* Custom Scrollbar */
    .custom-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    
    /* Heatmap */
    .heatmap-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
    .heatmap-cell { aspect-ratio: 1; border-radius: 3px; background: #f1f5f9; }
    .heatmap-cell.win { background: #10b981; }
    .heatmap-cell.loss { background: #ef4444; }
    .heatmap-cell.neutral { background: #e2e8f0; }
    
    /* Navigation Tabs */
    .tab-btn { padding: 0.75rem 1rem; font-size: 0.875rem; font-weight: 600; color: #64748b; border-bottom: 2px solid transparent; transition: all 0.2s; display: flex; align-items: center; gap: 0.5rem; }
    .tab-btn.active { color: #3b82f6; border-bottom-color: #3b82f6; }
    
    /* Toast Animation */
    @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .toast { animation: slideDown 0.3s ease-out forwards; }
  </style>
</head>
<body class="min-h-screen pb-10">

  <!-- Toast Container -->
  <div id="toast-container" class="fixed top-4 left-0 right-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none"></div>

  <!-- Top Navigation -->
  <nav class="bg-white border-b border-slate-200 sticky top-0 z-30">
    <div class="max-w-md mx-auto px-4">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-md">X</div>
            <span class="font-bold text-lg tracking-tight">AI QUANT</span>
        </div>
        <div class="flex gap-2">
            <button onclick="openBacktest()" class="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-200 flex items-center gap-1"><i data-lucide="flask-conical" class="w-3.5 h-3.5"></i> TEST</button>
            <button id="pause-btn" onclick="togglePause()" class="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-semibold hover:bg-green-200 flex items-center gap-1"><i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE</button>
        </div>
      </div>
      <!-- Tabs -->
      <div class="flex gap-2 mt-2 overflow-x-auto custom-scroll border-b border-slate-200">
        <button class="tab-btn active" onclick="switchTab('overview', this)"><i data-lucide="layout-dashboard" class="w-4 h-4"></i> Overview</button>
        <button class="tab-btn" onclick="switchTab('positions', this)"><i data-lucide="briefcase" class="w-4 h-4"></i> Positions</button>
        <button class="tab-btn" onclick="switchTab('history', this)"><i data-lucide="history" class="w-4 h-4"></i> History</button>
        <button class="tab-btn" onclick="switchTab('logs', this)"><i data-lucide="terminal" class="w-4 h-4"></i> Logs</button>
      </div>
    </div>
  </nav>

  <div class="max-w-md mx-auto px-4 pt-6">
    
    <!-- OVERVIEW TAB -->
    <div id="tab-overview" class="space-y-6">
        <!-- Main Balance -->
        <section class="card p-6 relative overflow-hidden">
            <div class="absolute top-0 right-0 p-4 opacity-10"><i data-lucide="wallet" class="w-24 h-24"></i></div>
            <p class="text-slate-500 text-xs font-medium mb-1">Total Balance</p>
            <div class="flex items-end gap-3 relative z-10">
                <h2 id="total-equity" class="text-4xl font-bold text-slate-900">0.00</h2>
                <span class="text-slate-500 text-sm mb-1">USDT</span>
            </div>
            <div id="pnl-display" class="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 relative z-10">
                <i data-lucide="trending-up" class="w-3.5 h-3.5" id="pnl-icon"></i>
                <span id="pnl-value">+0.00 USDT</span>
                <span id="pnl-percent" class="opacity-70">(0.00%)</span>
            </div>
        </section>

        <!-- Market Breadth -->
        <section class="card p-4">
            <div class="flex justify-between items-center mb-2">
                <h3 class="text-xs font-semibold text-slate-600 flex items-center gap-1"><i data-lucide="bar-chart-2" class="w-3.5 h-3.5"></i> Market Breadth</h3>
                <span id="breadth-label" class="text-xs font-bold text-slate-800">Loading...</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2.5">
                <div id="breadth-bar" class="bg-blue-500 h-2.5 rounded-full transition-all duration-500" style="width: 50%"></div>
            </div>
        </section>

        <!-- Chart -->
        <section class="card p-4">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-semibold text-slate-800">Market Chart</h3>
                <select id="chart-symbol" onchange="changeChartSymbol()" class="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-lg px-2 py-1 outline-none font-medium">
                    <option value="BTCUSDT">BTC/USDT</option>
                    <option value="ETHUSDT">ETH/USDT</option>
                    <option value="SOLUSDT">SOL/USDT</option>
                    <option value="BNBUSDT">BNB/USDT</option>
                </select>
            </div>
            <div id="tvchart" class="w-full h-56 rounded-lg overflow-hidden"></div>
        </section>

        <!-- Stats Grid with Donut Charts -->
        <section class="grid grid-cols-2 gap-4">
            <div class="card p-4 flex flex-col items-center justify-center">
                <h3 class="text-xs font-medium text-slate-500 mb-2">Win Rate</h3>
                <div class="relative w-20 h-20">
                    <canvas id="winrateChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="winrate" class="text-sm font-bold text-slate-800">0%</span>
                    </div>
                </div>
            </div>
            <div class="card p-4 flex flex-col items-center justify-center">
                <h3 class="text-xs font-medium text-slate-500 mb-2">Profit Factor</h3>
                <div class="relative w-20 h-20">
                    <canvas id="pfChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="pf" class="text-sm font-bold text-slate-800">0.0</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Heatmap -->
        <section class="card p-4">
            <h3 class="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2"><i data-lucide="calendar" class="w-4 h-4"></i> 30-Day PnL</h3>
            <div class="heatmap-grid" id="heatmap"></div>
        </section>

        <!-- Market Watch -->
        <section class="card p-4">
            <h3 class="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2"><i data-lucide="globe" class="w-4 h-4"></i> Market Watch</h3>
            <div class="h-40 overflow-y-auto custom-scroll" id="market-watch">
                <div class="text-center text-slate-400 text-xs py-4">Loading data...</div>
            </div>
        </section>
    </div>

    <!-- POSITIONS TAB -->
    <div id="tab-positions" class="hidden space-y-4">
        <div class="flex justify-between items-center mb-2">
            <h3 class="text-lg font-bold text-slate-800">Active Positions</h3>
            <span id="pos-count" class="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">0 Open</span>
        </div>
        <div id="active-positions-list" class="space-y-3"></div>
    </div>

    <!-- HISTORY TAB -->
    <div id="tab-history" class="hidden space-y-4">
        <h3 class="text-lg font-bold text-slate-800 mb-2">Trade History</h3>
        <div class="card overflow-hidden" id="trade-history">
            <div class="text-center text-slate-400 text-xs py-8">Loading history...</div>
        </div>
    </div>

    <!-- LOGS TAB -->
    <div id="tab-logs" class="hidden space-y-4">
        <h3 class="text-lg font-bold text-slate-800 mb-2">AI Neural Logs</h3>
        <div class="card p-4 h-96 overflow-y-auto font-mono text-[11px] custom-scroll bg-slate-900 text-slate-300 rounded-xl" id="neural-logs">
            <div class="text-slate-500">Waiting for scan cycle...</div>
        </div>
    </div>

  </div>

  <!-- Backtest Modal -->
  <div id="backtest-modal" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm hidden items-center justify-center z-50 px-4">
    <div class="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2"><i data-lucide="flask-conical" class="w-5 h-5 text-blue-500"></i> Run Backtest</h3>
        <button onclick="closeBacktest()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
      </div>
      <div class="space-y-4 mb-6">
        <select id="bt-symbol" class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm outline-none">
          <option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option><option value="SOLUSDT">SOLUSDT</option>
        </select>
        <select id="bt-strat" class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm outline-none">
          <option value="all">All Strategies</option><option value="trend">Trend</option><option value="mean_reversion">Mean Reversion</option><option value="breakout">Breakout</option>
        </select>
      </div>
      <button onclick="runBacktest()" id="bt-run-btn" class="w-full bg-blue-600 text-white font-semibold py-2.5 rounded-lg hover:bg-blue-700 transition-all flex justify-center items-center gap-2">
        <i data-lucide="play" class="w-4 h-4"></i> Run Simulation
      </button>
      <div id="bt-results" class="mt-4 text-xs font-mono whitespace-pre-wrap hidden bg-slate-50 p-3 rounded-lg border border-slate-200 max-h-48 overflow-y-auto custom-scroll"></div>
    </div>
  </div>

<script>
let tvChart = null;
let candleSeries = null;
let currentSymbol = "BTCUSDT";
let currentPositions = []; 
let winrateChart = null;
let pfChart = null;
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

// Initialize Icons
lucide.createIcons();

// --- Toast Notification System ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-slate-800';
    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info';
    
    toast.className = `toast ${bgColor} text-white px-4 py-3 rounded-xl shadow-lg flex items-center gap-3 pointer-events-auto`;
    toast.innerHTML = `<i data-lucide="${icon}" class="w-5 h-5"></i><span class="text-sm font-medium">${message}</span>`;
    container.appendChild(toast);
    lucide.createIcons();
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Tabs Logic
function switchTab(tabName, btn) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.classList.add('hidden'));
    document.getElementById(`tab-${tabName}`).classList.remove('hidden');
}

async function togglePause() {
    const btn = document.getElementById('pause-btn');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin"></i>...';
    lucide.createIcons();
    
    const res = await fetch('/api/toggle_pause', { method: 'POST' });
    const data = await res.json();
    updatePauseButton(data.paused);
    showToast(data.paused ? 'Bot Paused' : 'Bot Resumed', data.paused ? 'error' : 'success');
}

function updatePauseButton(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (isPaused) {
        btn.className = "px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-xs font-semibold hover:bg-red-200 flex items-center gap-1";
        btn.innerHTML = '<i data-lucide="pause-circle" class="w-3.5 h-3.5"></i> PAUSED';
    } else {
        btn.className = "px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-semibold hover:bg-green-200 flex items-center gap-1";
        btn.innerHTML = '<i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE';
    }
    lucide.createIcons();
}

async function closePosition(id, symbol) {
    if(!confirm(`Close ${symbol}?`)) return;
    await fetch(`/api/close_position/${id}`, { method: 'POST' });
    showToast(`Closed ${symbol}`, 'success');
    load();
}

function openBacktest() { document.getElementById('backtest-modal').classList.remove('hidden'); document.getElementById('backtest-modal').classList.add('flex'); }
function closeBacktest() { document.getElementById('backtest-modal').classList.add('hidden'); document.getElementById('backtest-modal').classList.remove('flex'); }

async function runBacktest() {
    const symbol = document.getElementById('bt-symbol').value;
    const strat = document.getElementById('bt-strat').value;
    const btn = document.getElementById('bt-run-btn');
    const resDiv = document.getElementById('bt-results');
    btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Running...'; btn.disabled = true; resDiv.classList.add('hidden');
    lucide.createIcons();
    
    try {
        const res = await fetch(`/api/run_backtest?symbol=${symbol}&strategy=${strat}`, { method: 'POST' });
        const data = await res.json();
        if(data.success) { 
            resDiv.textContent = data.report; 
            resDiv.classList.remove('hidden'); 
            showToast('Backtest Completed', 'success');
        } 
        else { showToast("Error: " + data.error, 'error'); }
    } catch(e) { showToast("Failed to run backtest", 'error'); }
    btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> Run Simulation'; btn.disabled = false;
    lucide.createIcons();
}

// Init Charts
function initTVChart() {
    const chartElement = document.getElementById('tvchart');
    if(!chartElement) return;
    
    const width = chartElement.clientWidth > 0 ? chartElement.clientWidth : 350;
    
    tvChart = LightweightCharts.createChart(chartElement, {
        width: width, height: 224,
        layout: { background: { type: 'solid', color: '#ffffff' }, textColor: '#64748b' },
        grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    
    candleSeries = tvChart.addCandlestickSeries({
        upColor: '#10b981', downColor: '#ef4444',
        borderVisible: false, wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });
    
    window.addEventListener('resize', () => { tvChart.applyOptions({ width: chartElement.clientWidth }); });
    loadChartData(currentSymbol);
}

function initDonutCharts() {
    const ctxWin = document.getElementById('winrateChart').getContext('2d');
    winrateChart = new Chart(ctxWin, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: ['#10b981', '#f1f5f9'], borderWidth: 0, cutout: '80%' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: false } } }
    });

    const ctxPf = document.getElementById('pfChart').getContext('2d');
    pfChart = new Chart(ctxPf, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: ['#8b5cf6', '#f1f5f9'], borderWidth: 0, cutout: '80%' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: false } } }
    });
}

async function loadLiveTickers() {
    try {
        const res = await fetch('/api/live_tickers');
        const data = await res.json();
        if(data.length > 0) {
            const marketGrid = document.getElementById('market-watch');
            marketGrid.innerHTML = data.map(d => {
                const isUp = d.change >= 0;
                const textColor = isUp ? 'text-green-600' : 'text-red-600';
                const bgColor = isUp ? 'bg-green-50' : 'bg-red-50';
                const sign = isUp ? '+' : '';
                return `
                <div class="flex justify-between items-center p-2 rounded-lg ${bgColor} mb-1">
                    <span class="font-bold text-slate-800 text-xs">${d.symbol}</span>
                    <div class="text-right">
                        <div class="text-slate-900 text-xs font-mono font-semibold">$${fmt(d.price)}</div>
                        <div class="${textColor} text-[10px] font-bold">${sign}${d.change}%</div>
                    </div>
                </div>`;
            }).join('');
        }
    } catch(e) {}
}

async function loadChartData(symbol) {
    try {
        const res = await fetch(`/api/market_klines?symbol=${symbol}&interval=15m`);
        const data = await res.json();
        
        if(data && data.length > 0) {
            candleSeries.setData(data);
            tvChart.timeScale().fitContent();
            
            candleSeries.setMarkers([]);
            const symbolPositions = currentPositions.filter(p => p.symbol === symbol);
            let markers = [];
            
            symbolPositions.forEach(pos => {
                const entryTime = Math.floor(new Date(pos.opened_at).getTime() / 1000);
                markers.push({
                    time: entryTime, position: pos.side === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: pos.side === 'LONG' ? '#10b981' : '#ef4444',
                    shape: pos.side === 'LONG' ? 'arrowUp' : 'arrowDown', text: pos.side
                });
                candleSeries.createPriceLine({ price: Number(pos.entry_price), color: '#3b82f6', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ENTRY' });
                candleSeries.createPriceLine({ price: Number(pos.stop_price), color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'STOP' });
                candleSeries.createPriceLine({ price: Number(pos.target_price), color: '#10b981', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TARGET' });
            });
            candleSeries.setMarkers(markers);
        }
    } catch(e) {}
}

function changeChartSymbol() { currentSymbol = document.getElementById('chart-symbol').value; loadChartData(currentSymbol); }

async function updateHeatmap(trades) {
    const heatmapContainer = document.getElementById('heatmap');
    let dayStats = {};
    trades.filter(t => t.status === 'CLOSED' && t.closed_at).forEach(t => {
        const date = t.closed_at.split('T')[0];
        if(!dayStats[date]) dayStats[date] = 0;
        dayStats[date] += Number(t.net_pnl) || 0;
    });
    
    let html = '';
    let today = new Date();
    for(let i = 34; i >= 0; i--) {
        let d = new Date(today); d.setDate(today.getDate() - i);
        let dateStr = d.toISOString().split('T')[0];
        let pnl = dayStats[dateStr] || 0;
        let cellClass = pnl > 0 ? 'win' : (pnl < 0 ? 'loss' : 'neutral');
        html += `<div class="heatmap-cell ${cellClass}" title="${dateStr}: ${pnl > 0 ? '+' : ''}${pnl.toFixed(2)} USDT"></div>`;
    }
    heatmapContainer.innerHTML = html;
}

async function load(){
 try{
  const results = await Promise.allSettled([
      fetch('/api/portfolio').then(y=>y.json()), 
      fetch('/api/positions').then(y=>y.json()), 
      fetch('/api/performance').then(y=>y.json()),
      fetch('/api/status').then(y=>y.json()),
      fetch('/api/decisions').then(y=>y.json()),
      fetch('/api/trades').then(y=>y.json()),
      fetch('/api/risk').then(y=>y.json()) // Fetch risk status for Breadth
  ]);
  
  const p = results[0].status === 'fulfilled' ? results[0].value : {equity: 0, unrealized_pnl: 0, realized_pnl: 0};
  const ps = results[1].status === 'fulfilled' ? results[1].value : [];
  const perf = results[2].status === 'fulfilled' ? results[2].value : {win_rate: 0, profit_factor: 0};
  const status = results[3].status === 'fulfilled' ? results[3].value : {paused: false};
  const decisions = results[4].status === 'fulfilled' ? results[4].value : [];
  const trades = results[5].status === 'fulfilled' ? results[5].value : [];
  const risk = results[6].status === 'fulfilled' ? results[6].value : {breadth: 50};

  currentPositions = ps;
  updatePauseButton(status.paused);
  
  document.getElementById('total-equity').textContent = fmt(p.equity);
  const pnlVal = p.unrealized_pnl + p.realized_pnl;
  const pnlPercent = (pnlVal / 200) * 100;
  const pnlDisplay = document.getElementById('pnl-display');
  const pnlIcon = document.getElementById('pnl-icon');
  
  document.getElementById('pnl-value').textContent = `${pnlVal >= 0 ? '+' : ''}${fmt(pnlVal)} USDT`;
  document.getElementById('pnl-percent').textContent = `(${pnlVal >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`;
  
  if(pnlVal > 0) {
      pnlDisplay.className = "mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-100 text-green-700 relative z-10";
      pnlIcon.setAttribute('data-lucide', 'trending-up');
  } else if(pnlVal < 0) {
      pnlDisplay.className = "mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-100 text-red-700 relative z-10";
      pnlIcon.setAttribute('data-lucide', 'trending-down');
  } else {
      pnlDisplay.className = "mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 relative z-10";
      pnlIcon.setAttribute('data-lucide', 'minus');
  }
  lucide.createIcons();

  // Breadth
  const breadth = risk.breadth || 50;
  const breadthBar = document.getElementById('breadth-bar');
  const breadthLabel = document.getElementById('breadth-label');
  breadthBar.style.width = `${breadth}%`;
  if(breadth > 60) { breadthBar.className = 'bg-green-500 h-2.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Bullish'; breadthLabel.className = 'text-xs font-bold text-green-600'; }
  else if(breadth < 40) { breadthBar.className = 'bg-red-500 h-2.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Bearish'; breadthLabel.className = 'text-xs font-bold text-red-600'; }
  else { breadthBar.className = 'bg-blue-500 h-2.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Neutral'; breadthLabel.className = 'text-xs font-bold text-blue-600'; }

  // Update Donut Charts
  let wr = perf.win_rate || 0;
  document.getElementById('winrate').textContent = wr.toFixed(0) + '%';
  if(winrateChart) winrateChart.data.datasets[0].data = [wr, 100 - wr], winrateChart.update();

  let pf = perf.profit_factor || 0;
  document.getElementById('pf').textContent = (perf.profit_factor === null ? '∞' : pf.toFixed(2));
  let pfPct = Math.min((pf / 3) * 100, 100);
  if(pfChart) pfChart.data.datasets[0].data = [pfPct, 100 - pfPct], pfChart.update();

  updateHeatmap(trades);

  // Positions with Live PnL
  const posContainer = document.getElementById('active-positions-list');
  document.getElementById('pos-count').textContent = `${ps.length} Open`;
  if(ps.length === 0) {
    posContainer.innerHTML = '<div class="text-center text-slate-400 text-sm py-8 card">No active positions</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => {
        // حساب الربح العائم
        const currentPrice = Number(pos.current_price || pos.entry_price);
        const entryPrice = Number(pos.entry_price);
        const qty = Number(pos.quantity);
        const sideMultiplier = pos.side === 'LONG' ? 1 : -1;
        const unrealizedPnl = (currentPrice - entryPrice) * qty * sideMultiplier;
        
        const pnlColor = unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600';
        const pnlSign = unrealizedPnl >= 0 ? '+' : '';
        const pnlBg = unrealizedPnl >= 0 ? 'bg-green-50' : 'bg-red-50';

        return `
      <div class="card p-4 border-l-4 ${pos.side === 'LONG' ? 'border-l-green-500' : 'border-l-red-500'}">
        <div class="flex justify-between items-start mb-3">
          <div>
              <h4 class="font-bold text-slate-900 text-lg">${pos.symbol}</h4>
              <div class="flex gap-2 items-center mt-1">
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-600">${pos.side}</span>
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded ${pnlBg} ${pnlColor}">${pnlSign}${fmt(unrealizedPnl)} USDT</span>
              </div>
          </div>
          <div class="text-right">
            <p class="text-[10px] text-slate-400 uppercase">Entry</p>
            <p class="font-mono text-sm font-semibold text-slate-800">${entryPrice.toFixed(4)}</p>
            <p class="text-[10px] text-slate-400 uppercase mt-1">Current</p>
            <p class="font-mono text-xs font-semibold text-slate-600">${currentPrice.toFixed(4)}</p>
          </div>
        </div>
        <div class="flex justify-between items-center pt-3 border-t border-slate-100">
           <div class="flex gap-4">
               <div><p class="text-[10px] text-slate-400 uppercase">Target</p><p class="font-mono text-xs text-green-600 font-semibold">${Number(pos.target_price).toFixed(4)}</p></div>
               <div><p class="text-[10px] text-slate-400 uppercase">Stop</p><p class="font-mono text-xs text-red-600 font-semibold">${Number(pos.stop_price).toFixed(4)}</p></div>
           </div>
           <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="text-[10px] font-bold text-red-600 border border-red-200 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors">CLOSE</button>
        </div>
      </div>
    `}).join('');
  }

  // History Table
  const histContainer = document.getElementById('trade-history');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 10);
  if(closedTrades.length === 0) {
      histContainer.innerHTML = '<div class="text-center text-slate-400 text-xs py-8">No recent trades</div>';
  } else {
      let html = `<table class="w-full text-left text-xs text-slate-600">
        <thead class="bg-slate-50 text-[10px] uppercase text-slate-400 border-b border-slate-200">
          <tr><th class="p-3">Asset</th><th class="p-3">Side</th><th class="p-3 text-right">Entry</th><th class="p-3 text-right">Net PnL</th></tr>
        </thead><tbody>`;
      closedTrades.forEach(t => {
          const isWin = Number(t.net_pnl) > 0;
          html += `<tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
              <td class="p-3 font-bold text-slate-800">${t.symbol}</td>
              <td class="p-3"><span class="text-[9px] font-bold px-1.5 py-0.5 rounded ${t.side === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">${t.side}</span></td>
              <td class="p-3 text-right font-mono">${Number(t.entry_price).toFixed(2)}</td>
              <td class="p-3 text-right font-mono font-bold ${isWin ? 'text-green-600' : 'text-red-600'}">${isWin ? '+' : ''}${fmt(t.net_pnl)}</td>
          </tr>`;
      });
      html += '</tbody></table>';
      histContainer.innerHTML = html;
  }

  // Logs
  const logContainer = document.getElementById('neural-logs');
  if(decisions.length === 0) {
    logContainer.innerHTML = '<div class="text-slate-500">No scans yet...</div>';
  } else {
    logContainer.innerHTML = decisions.slice(0, 25).map(d => {
        const time = new Date(d.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        let color = d.action.includes('BUY') ? 'text-green-400' : d.action.includes('SHORT') ? 'text-red-400' : 'text-slate-400';
        return `<div class="mb-1.5 flex gap-2"><span class="text-slate-600 shrink-0">[${time}]</span> <span class="text-white font-semibold shrink-0">${d.symbol}</span> <span class="${color} shrink-0 font-semibold">${d.action}</span> <span class="text-slate-500 truncate">${d.reason.substring(0, 50)}...</span></div>`;
    }).join('');
  }

 }catch(e){ console.error('System Error:', e); }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { initTVChart(); initDonutCharts(); }, 200);
    loadLiveTickers();
    load(); 
    setInterval(load, 3000);
    setInterval(loadLiveTickers, 10000);
});
</script>
</body>
</html>""")

# --- APIs ---
@router.get("/api/status")
async def status(request:Request): return request.app.state.engine.get_status()
@router.get("/api/portfolio")
async def portfolio(request:Request): return request.app.state.db.get_portfolio()
@router.get("/api/risk")
async def risk(request:Request): 
    r = request.app.state.engine.risk.get_risk_status()
    # نضيف اتساع السوق للـ API
    r["breadth"] = await request.app.state.engine.market.get_market_breadth("futures")
    return r

@router.get("/api/positions")
async def positions(request:Request): 
    db = request.app.state.db
    market = request.app.state.engine.market
    pos_list = db.get_open_positions()
    
    # جلب السعر الحالي للصفقات المفتوحة لحساب الربح العائم
    if pos_list:
        sources = {p["source"] for p in pos_list}
        all_prices = {}
        for src in sources:
            prices = await market.get_last_prices(src)
            all_prices.update(prices)
            
        for p in pos_list:
            symbol = p["symbol"]
            if symbol in all_prices:
                p["current_price"] = all_prices[symbol]["last_price"]
            else:
                p["current_price"] = p["entry_price"]
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
        market = request.app.state.engine.market
        tickers = await market.get_tickers_24h("futures")
        symbols = list(config.SYMBOLS)
        out = []
        for s in symbols:
            if s in tickers:
                out.append({
                    "symbol": s.replace("USDT", ""),
                    "price": tickers[s]["last_price"],
                    "change": round(tickers[s]["change_percent"], 2)
                })
        return out
    except Exception:
        return []

@router.get("/api/market_klines")
async def market_klines(request: Request, symbol: str = "BTCUSDT", interval: str = "15m"):
    try:
        market = request.app.state.engine.market
        df = await market.get_klines(symbol, interval, 100, "futures")
        
        data = []
        for _, row in df.iterrows():
            data.append({
                "time": int(row["timestamp"]) // 1000, 
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"])
            })
        return data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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
        df = await market.fetch_history(symbol, "1h", "futures", 1000)
        if df.empty: return {"success": False, "error": "Failed to fetch history"}
        strategies = None if strategy == "all" else [strategy]
        report = await asyncio.to_thread(run_backtest, df, strategies, "futures")
        report_text = format_report(symbol, report, "1h")
        return {"success": True, "report": report_text}
    except Exception as e:
        return {"success": False, "error": str(e)}
