"""Ultimate FastAPI Dashboard - Final Perfected Edition with Forced PnL Colors."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio, re
from backtest import run_backtest, format_report
import config

router=APIRouter()
_bt_running=False

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
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: { 
        extend: { 
          colors: { 
            brand: { bg: '#f8fafc', card: '#ffffff', border: '#e2e8f0', text: '#0f172a', muted: '#64748b' },
            green: '#10b981', red: '#ef4444', blue: '#3b82f6', purple: '#8b5cf6', neutral: '#94a3b8'
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
    .custom-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    .tab-btn { padding: 0.75rem 0.5rem; font-size: 0.75rem; font-weight: 600; color: #64748b; border-bottom: 2px solid transparent; transition: all 0.2s; display: flex; align-items: center; gap: 0.25rem; white-space: nowrap; }
    .tab-btn.active { color: #3b82f6; border-bottom-color: #3b82f6; }
    @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .toast { animation: slideDown 0.3s ease-out forwards; }
  </style>
</head>
<body class="min-h-screen pb-10">

  <div id="toast-container" class="fixed top-4 left-0 right-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none"></div>

  <nav class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-md mx-auto px-4">
      <div class="flex justify-between items-center h-14">
        <div class="flex items-center gap-2">
            <div style="background-color: #2563eb; color: white; width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M9 1v3"/><path d="M15 1v3"/><path d="M9 20v3"/><path d="M15 20v3"/><path d="M20 9h3"/><path d="M20 14h3"/><path d="M1 9h3"/><path d="M1 14h3"/></svg>
            </div>
            <span class="font-bold text-base tracking-tight">AI QUANT</span>
        </div>
        <div class="flex gap-2">
            <button onclick="openBacktest()" class="px-2.5 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-200 flex items-center gap-1"><i data-lucide="flask-conical" class="w-3.5 h-3.5"></i> TEST</button>
            <button id="pause-btn" onclick="togglePause()" class="px-2.5 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-semibold hover:bg-green-200 flex items-center gap-1"><i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE</button>
        </div>
      </div>
      <div class="flex gap-1 mt-1 overflow-x-auto custom-scroll border-b border-slate-200 text-[11px] px-1">
        <button class="tab-btn active" onclick="switchTab('overview', this)"><i data-lucide="layout-dashboard" class="w-3.5 h-3.5"></i> Overview</button>
        <button class="tab-btn" onclick="switchTab('positions', this)"><i data-lucide="briefcase" class="w-3.5 h-3.5"></i> Positions</button>
        <button class="tab-btn" onclick="switchTab('history', this)"><i data-lucide="history" class="w-3.5 h-3.5"></i> History</button>
        <button class="tab-btn" onclick="switchTab('logs', this)"><i data-lucide="terminal" class="w-3.5 h-3.5"></i> Logs</button>
      </div>
    </div>
  </nav>

  <div class="max-w-md mx-auto px-4 pt-4">
    
    <div id="tab-overview" class="space-y-4">
        <section class="card p-5 relative overflow-hidden">
            <div class="absolute top-0 right-0 p-4 opacity-5"><i data-lucide="wallet" class="w-24 h-24"></i></div>
            <p class="text-slate-500 text-xs font-medium mb-1">Total Balance</p>
            <div class="flex items-end gap-2 relative z-10">
                <h2 id="total-equity" class="text-3xl font-bold text-slate-900">0.00</h2>
                <span class="text-slate-500 text-xs mb-1 font-medium">USDT</span>
            </div>
            <div id="pnl-display" class="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-slate-50 border border-slate-200 relative z-10">
                <i data-lucide="minus" class="w-3.5 h-3.5 text-slate-600" id="pnl-icon"></i>
                <span id="pnl-value" style="color: #64748b;">0.00 USDT</span>
                <span id="pnl-percent" style="color: #94a3b8;">(0.00%)</span>
            </div>
        </section>

        <section class="grid grid-cols-2 gap-3">
            <div class="card p-3 flex flex-col items-center justify-center">
                <h3 class="text-[11px] font-semibold text-slate-500 mb-1">Win Rate</h3>
                <div class="relative w-16 h-16">
                    <canvas id="winrateChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="winrate" class="text-xs font-bold text-slate-800">0%</span>
                    </div>
                </div>
            </div>
            <div class="card p-3 flex flex-col items-center justify-center">
                <h3 class="text-[11px] font-semibold text-slate-500 mb-1">Profit Factor</h3>
                <div class="relative w-16 h-16">
                    <canvas id="pfChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="pf" class="text-xs font-bold text-slate-800">0.0</span>
                    </div>
                </div>
            </div>
        </section>

        <section class="card p-4">
            <div class="flex justify-between items-center mb-3">
                <h3 class="text-sm font-semibold text-slate-800 flex items-center gap-2"><i data-lucide="bar-chart-2" class="w-4 h-4 text-blue-500"></i> Weekly Performance</h3>
                <span class="text-[10px] text-slate-400 font-medium">Last 7 Days</span>
            </div>
            <div class="h-32 w-full">
                <canvas id="weeklyChart"></canvas>
            </div>
            
            <div class="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-100">
                <div class="text-center">
                    <p class="text-[10px] text-slate-400 uppercase font-semibold">Trades</p>
                    <p id="stat-trades" class="text-sm font-bold text-slate-800">0</p>
                </div>
                <div class="text-center border-x border-slate-100">
                    <p class="text-[10px] text-slate-400 uppercase font-semibold">Best Trade</p>
                    <p id="stat-best" class="text-sm font-bold" style="color: #64748b;">0.00</p>
                </div>
                <div class="text-center">
                    <p class="text-[10px] text-slate-400 uppercase font-semibold">Worst Trade</p>
                    <p id="stat-worst" class="text-sm font-bold" style="color: #64748b;">0.00</p>
                </div>
            </div>
        </section>

        <section class="card p-4">
            <div class="flex justify-between items-center mb-3">
                <h3 class="text-sm font-semibold text-slate-800">Market Chart</h3>
                <select id="chart-symbol" onchange="changeChartSymbol()" class="bg-slate-50 border border-slate-200 text-slate-700 text-[11px] rounded-md px-2 py-1 outline-none font-medium">
                    <option value="BTCUSDT">BTC/USDT</option>
                    <option value="ETHUSDT">ETH/USDT</option>
                    <option value="SOLUSDT">SOL/USDT</option>
                    <option value="BNBUSDT">BNB/USDT</option>
                </select>
            </div>
            <div id="tvchart" class="w-full h-48 rounded-lg overflow-hidden"></div>
        </section>

        <section class="card p-3 flex items-center justify-between">
            <div class="flex items-center gap-2">
                <i data-lucide="bar-chart" class="w-4 h-4 text-slate-400"></i>
                <span class="text-xs font-semibold text-slate-600">Market Breadth</span>
            </div>
            <div class="flex items-center gap-3 w-1/2">
                <div class="w-full bg-slate-100 rounded-full h-1.5 flex-1">
                    <div id="breadth-bar" class="bg-slate-500 h-1.5 rounded-full transition-all duration-500" style="width: 50%"></div>
                </div>
                <span id="breadth-label" class="text-[10px] font-bold text-slate-800 w-12 text-right">50%</span>
            </div>
        </section>

        <section class="card p-4">
            <h3 class="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2"><i data-lucide="globe" class="w-4 h-4 text-slate-400"></i> Market Watch</h3>
            <div class="h-36 overflow-y-auto custom-scroll pr-1" id="market-watch">
                <div class="text-center text-slate-400 text-xs py-4">Loading data...</div>
            </div>
        </section>
    </div>

    <div id="tab-positions" class="hidden space-y-3">
        <div class="flex justify-between items-center mb-1">
            <h3 class="text-lg font-bold text-slate-800">Active Positions</h3>
            <span id="pos-count" class="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">0 Open</span>
        </div>
        <div id="active-positions-list" class="space-y-3"></div>
    </div>

    <div id="tab-history" class="hidden space-y-3">
        <h3 class="text-lg font-bold text-slate-800 mb-1">Trade History</h3>
        <div class="card overflow-hidden" id="trade-history">
            <div class="text-center text-slate-400 text-xs py-8">Loading history...</div>
        </div>
    </div>

    <div id="tab-logs" class="hidden space-y-3">
        <h3 class="text-lg font-bold text-slate-800 mb-1">AI Neural Logs</h3>
        <div class="card p-3 h-[calc(100vh-200px)] overflow-y-auto font-mono text-[10px] custom-scroll bg-slate-900 text-slate-300 rounded-xl" id="neural-logs">
            <div class="text-slate-500">Waiting for scan cycle...</div>
        </div>
    </div>

  </div>

  <div id="backtest-modal" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm hidden items-center justify-center z-50 px-4">
    <div class="bg-white rounded-2xl p-5 w-full max-w-sm shadow-xl">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-base font-bold text-slate-800 flex items-center gap-2"><i data-lucide="flask-conical" class="w-4 h-4 text-blue-500"></i> Run Backtest</h3>
        <button onclick="closeBacktest()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
      </div>
      <div class="space-y-3 mb-5">
        <select id="bt-symbol" class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs outline-none">
          <option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option><option value="SOLUSDT">SOLUSDT</option>
        </select>
        <select id="bt-strat" class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs outline-none">
          <option value="all">All Strategies</option><option value="trend">Trend</option><option value="mean_reversion">Mean Reversion</option><option value="breakout">Breakout</option>
        </select>
      </div>
      <button onclick="runBacktest()" id="bt-run-btn" class="w-full bg-blue-600 text-white font-semibold py-2 rounded-lg hover:bg-blue-700 transition-all flex justify-center items-center gap-2 text-sm">
        <i data-lucide="play" class="w-3.5 h-3.5"></i> Run Simulation
      </button>
      <div id="bt-results" class="mt-3 text-[10px] font-mono whitespace-pre-wrap hidden bg-slate-50 p-2 rounded-lg border border-slate-200 max-h-40 overflow-y-auto custom-scroll"></div>
    </div>
  </div>

<script>
let tvChart = null;
let candleSeries = null;
let currentSymbol = "BTCUSDT";
let currentPositions = []; 
let winrateChart = null;
let pfChart = null;
let weeklyChart = null;
let priceLines = [];
let overlaySig = '';
const refreshIcons = () => { try { if (window.lucide) window.lucide.createIcons(); } catch (e) {} };
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
// سعر بدقة مناسبة لحجمه (يعرض أيضاً العملات الصغيرة مثل SHIB بدل 0.0000)
const fmtPrice = (n) => { n = Number(n); if (!isFinite(n)) return '-'; const a = Math.abs(n); if (a >= 1000) return fmt(n); if (a >= 1) return n.toFixed(4); return n.toPrecision(4); };

// الألوان الصارمة
const COLOR_GREEN = '#10b981';
const COLOR_RED = '#ef4444';
const COLOR_NEUTRAL = '#64748b';

refreshIcons();

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-slate-800';
    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info';
    
    toast.className = `toast ${bgColor} text-white px-3 py-2 rounded-lg shadow-lg flex items-center gap-2 pointer-events-auto text-xs font-medium`;
    toast.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4"></i><span>${message}</span>`;
    container.appendChild(toast);
    refreshIcons();
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

function switchTab(tabName, btn) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.classList.add('hidden'));
    document.getElementById(`tab-${tabName}`).classList.remove('hidden');
    
    if (tabName === 'overview' && tvChart) {
        setTimeout(() => {
            tvChart.applyOptions({ width: document.getElementById('tvchart').clientWidth });
            tvChart.timeScale().fitContent();
        }, 100);
    }
}

async function togglePause() {
    const btn = document.getElementById('pause-btn');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i>...';
    refreshIcons();
    
    try {
        const res = await fetch('/api/toggle_pause', { method: 'POST' });
        const data = await res.json();
        updatePauseButton(data.paused);
        showToast(data.paused ? 'Bot Paused' : 'Bot Resumed', data.paused ? 'error' : 'success');
    } catch (e) {
        btn.innerHTML = originalHtml; refreshIcons();
        showToast('Request failed', 'error');
    }
}

function updatePauseButton(isPaused) {
    const btn = document.getElementById('pause-btn');
    if (isPaused) {
        btn.className = "px-2.5 py-1.5 bg-red-100 text-red-700 rounded-lg text-xs font-semibold hover:bg-red-200 flex items-center gap-1";
        btn.innerHTML = '<i data-lucide="pause-circle" class="w-3.5 h-3.5"></i> PAUSED';
    } else {
        btn.className = "px-2.5 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-semibold hover:bg-green-200 flex items-center gap-1";
        btn.innerHTML = '<i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE';
    }
    refreshIcons();
}

async function closePosition(id, symbol) {
    if(!confirm(`Close ${symbol}?`)) return;
    try {
        const res = await fetch(`/api/close_position/${id}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) showToast(`Closed ${symbol}`, 'success');
        else showToast('Error: ' + (data.error || 'close failed'), 'error');
    } catch (e) { showToast('Failed to close position', 'error'); }
    load();
}

function openBacktest() { document.getElementById('backtest-modal').classList.remove('hidden'); document.getElementById('backtest-modal').classList.add('flex'); }
function closeBacktest() { document.getElementById('backtest-modal').classList.add('hidden'); document.getElementById('backtest-modal').classList.remove('flex'); }

async function runBacktest() {
    const symbol = document.getElementById('bt-symbol').value;
    const strat = document.getElementById('bt-strat').value;
    const btn = document.getElementById('bt-run-btn');
    const resDiv = document.getElementById('bt-results');
    btn.innerHTML = '<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i> Running...'; btn.disabled = true; resDiv.classList.add('hidden');
    refreshIcons();
    
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
    btn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5"></i> Run Simulation'; btn.disabled = false;
    refreshIcons();
}

function initTVChart() {
    const chartElement = document.getElementById('tvchart');
    if(!chartElement) return;
    const width = chartElement.clientWidth > 0 ? chartElement.clientWidth : 350;
    
    tvChart = LightweightCharts.createChart(chartElement, {
        width: width, height: 192,
        layout: { background: { type: 'solid', color: '#ffffff' }, textColor: '#64748b' },
        grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    
    candleSeries = tvChart.addCandlestickSeries({
        upColor: COLOR_GREEN, downColor: COLOR_RED,
        borderVisible: false, wickUpColor: COLOR_GREEN, wickDownColor: COLOR_RED,
    });
    
    window.addEventListener('resize', () => { tvChart.applyOptions({ width: chartElement.clientWidth }); });
    loadChartData(currentSymbol);

    setTimeout(() => {
        const w = chartElement.clientWidth;
        tvChart.applyOptions({ width: w, height: 192 });
        tvChart.timeScale().fitContent();
    }, 1000);
}

function initCharts() {
    const ctxWin = document.getElementById('winrateChart').getContext('2d');
    winrateChart = new Chart(ctxWin, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: [COLOR_GREEN, '#f1f5f9'], borderWidth: 0, cutout: '80%' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: false } } }
    });

    const ctxPf = document.getElementById('pfChart').getContext('2d');
    pfChart = new Chart(ctxPf, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: ['#8b5cf6', '#f1f5f9'], borderWidth: 0, cutout: '80%' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: false } } }
    });

    const ctxWeek = document.getElementById('weeklyChart').getContext('2d');
    weeklyChart = new Chart(ctxWeek, {
        type: 'bar',
        data: {
            labels: ['', '', '', '', '', '', ''],
            datasets: [{
                label: 'PnL (USDT)',
                data: [0, 0, 0, 0, 0, 0, 0],
                backgroundColor: '#cbd5e1',
                borderRadius: 4,
                barPercentage: 0.6
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw > 0 ? '+' : ''}${fmt(ctx.raw)} USDT` } } },
            scales: {
                x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#94a3b8' } },
                y: { display: false, grace: '15%' } 
            }
        }
    });
}

async function loadLiveTickers() {
    try {
        const res = await fetch('/api/live_tickers');
        const data = await res.json();
        if(data.length > 0) {
            const marketGrid = document.getElementById('market-watch');
            marketGrid.innerHTML = data.map(d => {
                let textColor = COLOR_NEUTRAL;
                let bgColor = 'bg-slate-50';
                let sign = '';
                if (d.change > 0) { textColor = COLOR_GREEN; bgColor = 'bg-green-50'; sign = '+'; }
                else if (d.change < 0) { textColor = COLOR_RED; bgColor = 'bg-red-50'; }

                return `
                <div class="flex justify-between items-center p-1.5 rounded-md ${bgColor} mb-1">
                    <span class="font-bold text-slate-800 text-[11px]">${d.symbol}</span>
                    <div class="text-right">
                        <div class="text-slate-900 text-[11px] font-mono font-semibold">$${fmtPrice(d.price)}</div>
                        <div class="text-[9px] font-bold" style="color: ${textColor};">${sign}${d.change}%</div>
                    </div>
                </div>`;
            }).join('');
        }
    } catch(e) {}
}

function drawPositionOverlays() {
    if (!candleSeries) return;
    priceLines.forEach(l => { try { candleSeries.removePriceLine(l); } catch (e) {} });
    priceLines = [];
    const markers = [];
    currentPositions.filter(p => p.symbol === currentSymbol).forEach(pos => {
        const entryTime = Math.floor(new Date(pos.opened_at).getTime() / 1000);
        markers.push({
            time: entryTime, position: pos.side === 'LONG' ? 'belowBar' : 'aboveBar',
            color: pos.side === 'LONG' ? COLOR_GREEN : COLOR_RED,
            shape: pos.side === 'LONG' ? 'arrowUp' : 'arrowDown', text: pos.side
        });
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.entry_price), color: '#3b82f6', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ENTRY' }));
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.stop_price), color: COLOR_RED, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'STOP' }));
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.target_price), color: COLOR_GREEN, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TARGET' }));
    });
    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);
}

async function loadChartData(symbol) {
    try {
        const res = await fetch(`/api/market_klines?symbol=${symbol}&interval=15m`);
        const data = await res.json();
        if(data && data.length > 0) {
            candleSeries.setData(data);
            tvChart.timeScale().fitContent();
            
            drawPositionOverlays();
        }
    } catch(e) {}
}

function changeChartSymbol() { currentSymbol = document.getElementById('chart-symbol').value; loadChartData(currentSymbol); }

function updateWeeklyStats(trades) {
    const closedTrades = trades.filter(t => t.status === 'CLOSED' && t.closed_at);
    
    let days = [];
    let today = new Date();
    
    for(let i = 6; i >= 0; i--) {
        let d = new Date(today);
        d.setDate(today.getDate() - i);
        let dateStr = d.toISOString().split('T')[0];
        let dayName = d.toLocaleDateString('en-US', { weekday: 'short' });
        days.push({ date: dateStr, label: dayName, pnl: 0 });
    }

    closedTrades.forEach(t => {
        const date = t.closed_at.split('T')[0];
        let dayIndex = days.findIndex(d => d.date === date);
        if(dayIndex !== -1) {
            days[dayIndex].pnl += Number(t.net_pnl) || 0;
        }
    });

    const labels = days.map(d => d.label);
    const data = days.map(d => d.pnl);
    const bgColors = data.map(v => v > 0 ? COLOR_GREEN : (v < 0 ? COLOR_RED : '#cbd5e1'));
    
    if(weeklyChart) {
        weeklyChart.data.labels = labels;
        weeklyChart.data.datasets[0].data = data;
        weeklyChart.data.datasets[0].backgroundColor = bgColors;
        weeklyChart.update();
    }

    const totalTrades = closedTrades.length;
    const bestTrade = closedTrades.length > 0 ? Math.max(...closedTrades.map(t => Number(t.net_pnl))) : 0;
    const worstTrade = closedTrades.length > 0 ? Math.min(...closedTrades.map(t => Number(t.net_pnl))) : 0;

    document.getElementById('stat-trades').textContent = totalTrades;
    
    // تطبيق اللون الأخضر أو الأحمر أو الرمادي بشكل صارم (Inline CSS)
    const bestEl = document.getElementById('stat-best');
    if (bestTrade > 0) {
        bestEl.style.color = COLOR_GREEN;
        bestEl.textContent = `+${fmt(bestTrade)}`;
    } else {
        bestEl.style.color = COLOR_NEUTRAL;
        bestEl.textContent = `0.00`;
    }

    const worstEl = document.getElementById('stat-worst');
    if (worstTrade < 0) {
        worstEl.style.color = COLOR_RED;
        worstEl.textContent = `${fmt(worstTrade)}`;
    } else {
        worstEl.style.color = COLOR_NEUTRAL;
        worstEl.textContent = `0.00`;
    }
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
      fetch('/api/risk').then(y=>y.json())
  ]);
  
  if (results[0].status !== 'fulfilled') { return; }
  const p = results[0].value;
  const startBalance = p.initial_balance || 200;
  const ps = results[1].status === 'fulfilled' ? results[1].value : [];
  const perf = results[2].status === 'fulfilled' ? results[2].value : {win_rate: 0, profit_factor: 0};
  const status = results[3].status === 'fulfilled' ? results[3].value : {paused: false};
  const decisions = results[4].status === 'fulfilled' ? results[4].value : [];
  const trades = results[5].status === 'fulfilled' ? results[5].value : [];
  const risk = results[6].status === 'fulfilled' ? results[6].value : {breadth: 50};

  currentPositions = ps;
  const sig = JSON.stringify(ps.map(x => [x.id, x.stop_price]));
  if (sig !== overlaySig) { overlaySig = sig; drawPositionOverlays(); }
  updatePauseButton(status.paused);
  
  document.getElementById('total-equity').textContent = fmt(p.equity);
  
  const pnlVal = p.equity - startBalance;
  const pnlPercent = (pnlVal / startBalance) * 100;
  const pnlDisplay = document.getElementById('pnl-display');
  const pnlIcon = document.getElementById('pnl-icon');
  const pnlValueEl = document.getElementById('pnl-value');
  const pnlPercentEl = document.getElementById('pnl-percent');
  
  // إجبار الألوان باستخدام Inline Styles
  if (pnlVal > 0) {
      pnlValueEl.textContent = `+${fmt(pnlVal)} USDT`;
      pnlPercentEl.textContent = `(+${pnlPercent.toFixed(2)}%)`;
      pnlDisplay.className = "mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-green-50 border border-green-200 relative z-10";
      
      pnlValueEl.style.color = COLOR_GREEN;
      pnlPercentEl.style.color = COLOR_GREEN;
      
      pnlIcon.setAttribute('data-lucide', 'trending-up');
      pnlIcon.className = "w-3.5 h-3.5";
      pnlIcon.style.color = COLOR_GREEN;
  } else if (pnlVal < 0) {
      pnlValueEl.textContent = `${fmt(pnlVal)} USDT`;
      pnlPercentEl.textContent = `(${pnlPercent.toFixed(2)}%)`;
      pnlDisplay.className = "mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-red-50 border border-red-200 relative z-10";
      
      pnlValueEl.style.color = COLOR_RED;
      pnlPercentEl.style.color = COLOR_RED;
      
      pnlIcon.setAttribute('data-lucide', 'trending-down');
      pnlIcon.className = "w-3.5 h-3.5";
      pnlIcon.style.color = COLOR_RED;
  } else {
      pnlValueEl.textContent = `0.00 USDT`;
      pnlPercentEl.textContent = `(0.00%)`;
      pnlDisplay.className = "mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-slate-50 border border-slate-200 relative z-10";
      
      pnlValueEl.style.color = COLOR_NEUTRAL;
      pnlPercentEl.style.color = COLOR_NEUTRAL;
      
      pnlIcon.setAttribute('data-lucide', 'minus');
      pnlIcon.className = "w-3.5 h-3.5";
      pnlIcon.style.color = COLOR_NEUTRAL;
  }
  refreshIcons();

  updateWeeklyStats(trades);

  const breadth = risk.breadth || 50;
  const breadthBar = document.getElementById('breadth-bar');
  const breadthLabel = document.getElementById('breadth-label');
  breadthBar.style.width = `${breadth}%`;
  if(breadth > 60) { breadthBar.className = 'bg-green-500 h-1.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Bullish'; breadthLabel.style.color = COLOR_GREEN; }
  else if(breadth < 40) { breadthBar.className = 'bg-red-500 h-1.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Bearish'; breadthLabel.style.color = COLOR_RED; }
  else { breadthBar.className = 'bg-blue-500 h-1.5 rounded-full transition-all duration-500'; breadthLabel.textContent = 'Neutral'; breadthLabel.style.color = '#3b82f6'; }

  let wr = perf.win_rate || 0;
  document.getElementById('winrate').textContent = wr.toFixed(0) + '%';
  if(winrateChart) winrateChart.data.datasets[0].data = [wr, 100 - wr], winrateChart.update();

  let pfVal = (perf.profit_factor === undefined ? 0 : perf.profit_factor);
  let pfText = (pfVal === null ? '∞' : Number(pfVal).toFixed(2));
  document.getElementById('pf').textContent = pfText;
  let pfPct = 0;
  if (pfVal === null) pfPct = 100;
  else if (pfVal > 0) pfPct = Math.min((pfVal / 3) * 100, 100);
  if(pfChart) pfChart.data.datasets[0].data = [pfPct, 100 - pfPct], pfChart.update();

  const posContainer = document.getElementById('active-positions-list');
  document.getElementById('pos-count').textContent = `${ps.length} Open`;
  if(ps.length === 0) {
    posContainer.innerHTML = '<div class="text-center text-slate-400 text-sm py-8 card">No active positions</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => {
        const currentPrice = Number(pos.current_price || pos.entry_price);
        const entryPrice = Number(pos.entry_price);
        const qty = Number(pos.quantity);
        const sideMultiplier = pos.side === 'LONG' ? 1 : -1;
        const unrealizedPnl = (currentPrice - entryPrice) * qty * sideMultiplier;
        
        let pnlColorStyle = `color: ${COLOR_NEUTRAL};`;
        let pnlBg = 'bg-slate-100';
        let pnlSign = '';
        if (unrealizedPnl > 0) { pnlColorStyle = `color: ${COLOR_GREEN};`; pnlBg = 'bg-green-50'; pnlSign = '+'; }
        else if (unrealizedPnl < 0) { pnlColorStyle = `color: ${COLOR_RED};`; pnlBg = 'bg-red-50'; }

        return `
      <div class="card p-3 border-l-4 ${pos.side === 'LONG' ? 'border-l-green-500' : 'border-l-red-500'}">
        <div class="flex justify-between items-start mb-2">
          <div>
              <h4 class="font-bold text-slate-900 text-base">${pos.symbol}</h4>
              <div class="flex gap-2 items-center mt-1">
                  <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">${pos.side}</span>
                  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${pnlBg}" style="${pnlColorStyle}">${pnlSign}${fmt(unrealizedPnl)} USDT</span>
              </div>
          </div>
          <div class="text-right">
            <p class="text-[9px] text-slate-400 uppercase">Entry</p>
            <p class="font-mono text-xs font-semibold text-slate-800">${fmtPrice(entryPrice)}</p>
            <p class="text-[9px] text-slate-400 uppercase mt-0.5">Current</p>
            <p class="font-mono text-[11px] font-semibold text-slate-600">${fmtPrice(currentPrice)}</p>
          </div>
        </div>
        <div class="flex justify-between items-center pt-2 border-t border-slate-100">
           <div class="flex gap-3">
               <div><p class="text-[9px] text-slate-400 uppercase">Target</p><p class="font-mono text-[11px] font-semibold" style="color: ${COLOR_GREEN};">${fmtPrice(pos.target_price)}</p></div>
               <div><p class="text-[9px] text-slate-400 uppercase">Stop</p><p class="font-mono text-[11px] font-semibold" style="color: ${COLOR_RED};">${fmtPrice(pos.stop_price)}</p></div>
           </div>
           <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="text-[9px] font-bold border px-2.5 py-1 rounded-md hover:bg-red-50 transition-colors" style="color: ${COLOR_RED}; border-color: ${COLOR_RED}40;">CLOSE</button>
        </div>
      </div>
    `}).join('');
  }

  const histContainer = document.getElementById('trade-history');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 10);
  if(closedTrades.length === 0) {
      histContainer.innerHTML = '<div class="text-center text-slate-400 text-xs py-8">No recent trades</div>';
  } else {
      let html = `<table class="w-full text-left text-xs text-slate-600">
        <thead class="bg-slate-50 text-[10px] uppercase text-slate-400 border-b border-slate-200">
          <tr><th class="p-2">Asset</th><th class="p-2">Side</th><th class="p-2 text-right">Entry</th><th class="p-2 text-right">Net PnL</th></tr>
        </thead><tbody>`;
      closedTrades.forEach(t => {
          let pnlColorStyle = `color: ${COLOR_NEUTRAL};`;
          let pnlSign = '';
          if (t.net_pnl > 0) { pnlColorStyle = `color: ${COLOR_GREEN};`; pnlSign = '+'; }
          else if (t.net_pnl < 0) { pnlColorStyle = `color: ${COLOR_RED};`; }

          html += `<tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
              <td class="p-2 font-bold text-slate-800 text-[11px]">${t.symbol}</td>
              <td class="p-2"><span class="text-[9px] font-bold px-1.5 py-0.5 rounded ${t.side === 'LONG' ? 'bg-green-100' : 'bg-red-100'}" style="${pnlColorStyle}">${t.side}</span></td>
              <td class="p-2 text-right font-mono text-[11px]">${fmtPrice(t.entry_price)}</td>
              <td class="p-2 text-right font-mono font-bold text-[11px]" style="${pnlColorStyle}">${pnlSign}${fmt(t.net_pnl)}</td>
          </tr>`;
      });
      html += '</tbody></table>';
      histContainer.innerHTML = html;
  }

  const logContainer = document.getElementById('neural-logs');
  if(decisions.length === 0) {
    logContainer.innerHTML = '<div class="text-slate-500">No scans yet...</div>';
  } else {
    logContainer.innerHTML = decisions.slice(0, 25).map(d => {
        const time = new Date(d.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        let colorStyle = d.action.includes('LONG') ? `color: ${COLOR_GREEN};` : d.action.includes('SHORT') ? `color: ${COLOR_RED};` : `color: #94a3b8;`;
        return `<div class="mb-1 flex gap-2 text-[10px]"><span class="text-slate-600 shrink-0">[${time}]</span> <span class="text-white font-semibold shrink-0">${d.symbol}</span> <span class="shrink-0 font-semibold" style="${colorStyle}">${d.action}</span> <span class="text-slate-500 truncate">${String(d.reason || '').length > 60 ? String(d.reason).substring(0, 60) + '...' : String(d.reason || '')}</span></div>`;
    }).join('');
  }

 }catch(e){ console.error('System Error:', e); }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { try { if (window.LightweightCharts) initTVChart(); } catch (e) { console.error(e); } try { if (window.Chart) initCharts(); } catch (e) { console.error(e); } }, 200);
    loadLiveTickers();
    load(); 
    setInterval(load, 3000);
    setInterval(loadLiveTickers, 10000);
    setInterval(() => { if (candleSeries) loadChartData(currentSymbol); }, 60000);
});
</script>
</body>
</html>""")

# --- APIs ---
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
    db = request.app.state.db
    market = request.app.state.engine.market
    pos_list = db.get_open_positions()
    
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
    global _bt_running
    symbol = symbol.upper()
    if not re.fullmatch(r"[A-Z0-9]{5,15}", symbol):
        return {"success": False, "error": "Invalid symbol"}
    if strategy != "all" and strategy not in config.STRATEGIES:
        return {"success": False, "error": "Invalid strategy"}
    if _bt_running:
        return {"success": False, "error": "Another backtest is running, try again shortly"}
    _bt_running = True
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
    finally:
        _bt_running = False
