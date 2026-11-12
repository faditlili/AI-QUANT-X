"""Ultimate FastAPI Dashboard with Dynamic Theme Switcher (Cyber, Matrix, Gold)."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
from backtest import run_backtest, format_report
import config

router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>AI QUANT X · NEXUS ULTRA</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <script>
    // ربط ألوان Tailwind بمتغيرات CSS لكي تتغير ديناميكياً
    tailwind.config = {
      darkMode: 'class',
      theme: { 
        extend: { 
          colors: { 
            brand: { bg: 'var(--bg)', card: 'var(--glass-bg)', border: 'var(--glass-border)' }, 
            neon: { 
              cyan: 'var(--primary)', 
              green: 'var(--up-color)', 
              red: 'var(--down-color)', 
              purple: 'var(--secondary)' 
            } 
          }, 
          fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Share Tech Mono', 'monospace'], orbitron: ['Orbitron', 'sans-serif'] } 
        } 
      }
    }
  </script>
  <style>
    /* --- Dynamic Theme Variables --- */
    :root {
        --bg: #020308;
        --bg-grid: rgba(0, 243, 255, 0.02);
        --primary: #00f3ff;
        --secondary: #b026ff;
        --glass-bg: rgba(10, 15, 30, 0.65);
        --glass-border: rgba(0, 243, 255, 0.15);
        --up-color: #00ff66;
        --down-color: #ff003c;
    }
    
    /* Cyberpunk Theme (Default) */
    body.theme-cyber {
        --bg: #020308;
        --bg-grid: rgba(0, 243, 255, 0.02);
        --primary: #00f3ff;
        --secondary: #b026ff;
        --up-color: #00ff66;
        --down-color: #ff003c;
    }

    /* Matrix Theme */
    body.theme-matrix {
        --bg: #020a05;
        --bg-grid: rgba(0, 255, 102, 0.03);
        --primary: #00ff66;
        --secondary: #00cc44;
        --up-color: #00ff66;
        --down-color: #ff003c;
    }

    /* Binance Gold Theme */
    body.theme-gold {
        --bg: #0b0e11;
        --bg-grid: rgba(252, 213, 53, 0.03);
        --primary: #FCD535;
        --secondary: #F0B90B;
        --up-color: #0ecb81;
        --down-color: #f6465d;
    }

    body { background-color: var(--bg); background-image: radial-gradient(circle at 50% 0%, var(--bg-grid) 0%, transparent 60%), linear-gradient(var(--bg-grid) 1px, transparent 1px), linear-gradient(90deg, var(--bg-grid) 1px, transparent 1px); background-size: 100% 100%, 40px 40px, 40px 40px; -webkit-tap-highlight-color: transparent; transition: background-color 0.5s ease; }
    
    /* Base Glass */
    .glass { background: var(--glass-bg); backdrop-filter: blur(16px); border: 1px solid var(--glass-border); box-shadow: 0 4px 30px rgba(0,0,0,0.5); transition: border-color 0.5s ease; }
    
    /* --- Liquid Glass Effects --- */
    .liquid-btn {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
        box-shadow: 5px 5px 10px rgba(0, 0, 0, 0.5), -2px -2px 8px rgba(255, 255, 255, 0.05), inset 0px 1px 1px rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        transition: all 0.2s ease;
    }
    .liquid-btn:active {
        box-shadow: inset 4px 4px 8px rgba(0, 0, 0, 0.6), inset -2px -2px 6px rgba(255, 255, 255, 0.05);
        transform: scale(0.98);
    }
    .liquid-btn-green {
        background: linear-gradient(145deg, rgba(0, 255, 102, 0.15), rgba(0, 100, 40, 0.2));
        box-shadow: 4px 4px 10px rgba(0, 0, 0, 0.5), -2px -2px 8px rgba(0, 255, 102, 0.1), inset 0px 1px 2px rgba(0, 255, 102, 0.4);
        border: 1px solid rgba(0, 255, 102, 0.3);
        text-shadow: 0 0 8px rgba(0, 255, 102, 0.8);
    }
    .liquid-btn-red {
        background: linear-gradient(145deg, rgba(255, 0, 60, 0.15), rgba(100, 0, 20, 0.2));
        box-shadow: 4px 4px 10px rgba(0, 0, 0, 0.5), -2px -2px 8px rgba(255, 0, 60, 0.1), inset 0px 1px 2px rgba(255, 0, 60, 0.4);
        border: 1px solid rgba(255, 0, 60, 0.3);
        text-shadow: 0 0 8px rgba(255, 0, 60, 0.8);
    }
    .liquid-card {
        background: linear-gradient(145deg, rgba(10, 15, 30, 0.8), rgba(5, 8, 15, 0.95));
        box-shadow: 8px 8px 16px rgba(0, 0, 0, 0.6), -3px -3px 12px rgba(0, 243, 255, 0.05), inset 0px 1px 1px rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 1rem;
        transition: box-shadow 0.5s ease;
    }

    .neon-glow { text-shadow: 0 0 10px var(--primary); color: var(--primary); transition: color 0.5s ease; }
    .neon-glow-secondary { text-shadow: 0 0 10px var(--secondary); color: var(--secondary); }
    
    .scanline { position: relative; overflow: hidden; }
    .scanline::before { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--primary), transparent); animation: scan 4s linear infinite; }
    @keyframes scan { 0% { left: -100%; } 100% { left: 100%; } }
    
    .ticker-wrap { width: 100%; overflow: hidden; background: rgba(0,0,0,0.4); border-radius: 8px; border: 1px solid var(--glass-border); }
    .ticker { display: flex; white-space: nowrap; animation: ticker 40s linear infinite; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-50%, 0, 0); } }
    
    .custom-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; }
    
    .progress-bg { background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; height: 6px; }
    .progress-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
    
    .heatmap-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
    .heatmap-cell { aspect-ratio: 1; border-radius: 2px; background: rgba(255,255,255,0.05); }
    .heatmap-cell.win { background: rgba(0, 255, 102, 0.8); }
    .heatmap-cell.loss { background: rgba(255, 0, 60, 0.8); }
    .heatmap-cell.neutral { background: rgba(255, 255, 255, 0.1); }
  </style>
</head>
<body class="theme-cyber text-slate-200 font-sans antialiased min-h-screen pb-10 selection:bg-neon-cyan selection:text-black">
  <div class="max-w-md mx-auto px-4 pt-6">
    
    <header class="flex justify-between items-center mb-6">
      <h1 class="font-orbitron font-black text-2xl text-white tracking-widest neon-glow">AI QUANT <span class="neon-glow-secondary">X</span></h1>
      <div class="flex gap-2 items-center">
        <!-- Theme Switcher -->
        <button onclick="cycleTheme()" class="px-2 py-2 rounded-full text-sm liquid-btn text-slate-300" title="Change Theme">🎨</button>
        
        <button onclick="openBacktest()" class="px-3 py-1.5 rounded-full text-xs font-bold font-orbitron tracking-wider text-neon-purple liquid-btn">TEST</button>
        <button id="pause-btn" onclick="togglePause()" class="px-3 py-1.5 rounded-full text-xs font-bold font-orbitron tracking-wider liquid-btn liquid-btn-green">● ACTIVE</button>
      </div>
    </header>

    <div class="ticker-wrap mb-6 py-2">
      <div class="ticker" id="ticker-content">
        <span class="mx-4 font-mono text-sm text-slate-400">Connecting...</span>
      </div>
    </div>

    <!-- Main Balance Card -->
    <section class="text-center mb-8 liquid-card p-6 relative">
      <p class="text-slate-400 text-[10px] uppercase tracking-[0.2em] mb-1 font-mono">Total Estimated Value (USDT)</p>
      <h2 id="total-equity" class="font-mono text-5xl font-bold text-white tracking-tight mb-2">0.00</h2>
      <div id="pnl-display" class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-slate-800/50 border border-slate-700 shadow-inner">
        <span id="pnl-value" class="text-slate-400">+0.00 USDT</span>
        <span id="pnl-percent" class="text-slate-500 text-xs">(0.00%)</span>
      </div>
    </section>

    <!-- LIVE CHART -->
    <section class="glass rounded-2xl p-4 mb-6 scanline relative">
      <div class="flex justify-between items-center mb-2 relative z-10">
         <h3 class="font-orbitron text-xs text-neon-cyan tracking-widest" style="color: var(--primary)">LIVE MARKET</h3>
         <select id="chart-symbol" onchange="changeChartSymbol()" class="bg-black/50 border border-slate-700 text-neon-cyan text-[10px] rounded px-2 py-1 outline-none font-mono" style="color: var(--primary)">
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
            <option value="SOLUSDT">SOL/USDT</option>
            <option value="BNBUSDT">BNB/USDT</option>
         </select>
      </div>
      <div id="tvchart" class="w-full h-56 rounded-lg overflow-hidden relative z-10"></div>
      
      <div id="loading-chart" class="absolute inset-0 flex flex-col items-center justify-center bg-[#020308]/80 z-20 hidden">
        <div class="w-8 h-8 rounded-full border-2 border-neon-cyan/30 border-t-neon-cyan animate-spin mb-2" style="border-top-color: var(--primary)"></div>
        <span class="text-neon-cyan font-mono text-[10px] animate-pulse" style="color: var(--primary)">LOADING...</span>
      </div>
    </section>

    <!-- Stats Cards -->
    <section class="grid grid-cols-2 gap-3 mb-6">
      <div class="liquid-card p-4">
        <p class="text-[10px] text-slate-400 font-mono uppercase mb-1">Win Rate</p>
        <p id="winrate" class="font-mono text-xl font-bold neon-glow">--%</p>
      </div>
      <div class="liquid-card p-4">
        <p class="text-[10px] text-slate-400 font-mono uppercase mb-1">Profit Factor</p>
        <p id="pf" class="font-mono text-xl font-bold neon-glow">--</p>
      </div>
    </section>

    <!-- PnL Heatmap -->
    <section class="glass rounded-xl p-4 mb-6">
      <h3 class="font-orbitron text-xs text-slate-300 tracking-widest mb-4 border-b border-slate-700 pb-2">30-DAY PnL HEATMAP</h3>
      <div class="heatmap-grid" id="heatmap"></div>
      <div class="flex justify-between items-center mt-3 text-[9px] text-slate-500 font-mono">
        <span>Less</span>
        <div class="flex gap-1">
            <div class="w-2.5 h-2.5 bg-slate-800 rounded-sm"></div>
            <div class="w-2.5 h-2.5 bg-neon-green/40 rounded-sm"></div>
            <div class="w-2.5 h-2.5 bg-neon-green/80 rounded-sm"></div>
            <div class="w-2.5 h-2.5 bg-neon-green rounded-sm"></div>
        </div>
        <span>More</span>
      </div>
    </section>

    <section class="glass rounded-xl p-4 mb-6">
      <h3 class="font-orbitron text-xs text-slate-300 tracking-widest mb-4 border-b border-slate-700 pb-2">STRATEGY PERFORMANCE</h3>
      <div id="strategy-stats" class="space-y-3">
        <div class="text-slate-500 text-xs font-mono">Loading stats...</div>
      </div>
    </section>

    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">MARKET WATCH</h3>
        <span class="text-[10px] text-slate-500 font-mono">TOP 30 ASSETS</span>
      </div>
      <div class="glass rounded-xl p-2 h-40 overflow-y-auto custom-scroll" id="market-watch">
        <div class="text-center text-slate-500 text-xs py-4 font-mono">Loading data...</div>
      </div>
    </section>

    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">ACTIVE POSITIONS</h3>
        <span id="pos-count" class="text-xs text-slate-500 font-mono">0 Open</span>
      </div>
      <div id="active-positions-list"></div>
    </section>

    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">TRADE HISTORY</h3>
      </div>
      <div class="glass rounded-xl overflow-x-auto custom-scroll" id="trade-history">
        <div class="text-center text-slate-500 text-xs py-4 font-mono">Loading history...</div>
      </div>
    </section>

    <section class="mb-6">
      <div class="flex justify-between items-end mb-3">
        <h3 class="font-orbitron text-sm text-slate-200 tracking-wider">NEURAL LOGS</h3>
      </div>
      <div class="glass rounded-xl p-3 h-32 overflow-y-auto font-mono text-[10px] custom-scroll" id="neural-logs">
         <div class="text-slate-500">Waiting for scan cycle...</div>
      </div>
    </section>
  </div>

  <!-- Backtest Modal -->
  <div id="backtest-modal" class="fixed inset-0 bg-black/90 backdrop-blur-sm hidden items-center justify-center z-50 px-4">
    <div class="liquid-card w-full max-w-md p-6 relative border border-neon-purple/50 shadow-[0_0_30px_rgba(176,38,255,0.2)]">
      <button onclick="closeBacktest()" class="absolute top-4 right-4 text-slate-400 hover:text-white">✕</button>
      <h3 class="font-orbitron text-neon-purple text-lg mb-4 neon-glow" style="color: var(--secondary); text-shadow: 0 0 10px var(--secondary);">RUN BACKTEST</h3>
      <div class="space-y-4 mb-6">
        <select id="bt-symbol" class="w-full bg-brand-bg border border-slate-700 rounded-lg p-2 text-white outline-none focus:border-neon-purple">
          <option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option><option value="SOLUSDT">SOLUSDT</option>
        </select>
        <select id="bt-strat" class="w-full bg-brand-bg border border-slate-700 rounded-lg p-2 text-white outline-none focus:border-neon-purple">
          <option value="all">All Strategies</option><option value="trend">Trend</option><option value="mean_reversion">Mean Reversion</option><option value="breakout">Breakout</option>
        </select>
      </div>
      <button onclick="runBacktest()" id="bt-run-btn" class="w-full liquid-btn font-bold py-2 rounded-lg transition-all" style="color: var(--secondary)">Run Simulation</button>
      <div id="bt-results" class="mt-4 text-xs font-mono whitespace-pre-wrap hidden bg-black/50 p-3 rounded-lg border border-slate-800 max-h-48 overflow-y-auto custom-scroll"></div>
    </div>
  </div>

<script>
let tvChart = null;
let candleSeries = null;
let currentSymbol = "BTCUSDT";
let currentPositions = []; 
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

// --- Theme Logic ---
const themes = ['theme-cyber', 'theme-matrix', 'theme-gold'];
let currentThemeIndex = parseInt(localStorage.getItem('themeIndex') || '0');

function applyTheme(index) {
    document.body.className = document.body.className.replace(/theme-\w+/g, '').trim();
    document.body.classList.add(themes[index]);
    localStorage.setItem('themeIndex', index);
    
    // Update Chart Colors dynamically
    if (tvChart && candleSeries) {
        const styles = getComputedStyle(document.body);
        const upColor = styles.getPropertyValue('--up-color').trim();
        const downColor = styles.getPropertyValue('--down-color').trim();
        
        candleSeries.applyOptions({
            upColor: upColor,
            downColor: downColor,
            wickUpColor: upColor,
            wickDownColor: downColor
        });
        
        // Reload chart to apply new line colors if needed
        loadChartData(currentSymbol);
    }
}

function cycleTheme() {
    currentThemeIndex = (currentThemeIndex + 1) % themes.length;
    applyTheme(currentThemeIndex);
}

// Apply saved theme on load
document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentThemeIndex);
});

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
        btn.className = "px-3 py-1.5 rounded-full text-xs font-bold font-orbitron tracking-wider liquid-btn liquid-btn-red";
        btn.innerHTML = '■ PAUSED';
    } else {
        btn.className = "px-3 py-1.5 rounded-full text-xs font-bold font-orbitron tracking-wider liquid-btn liquid-btn-green";
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
    btn.innerHTML = 'Running...'; btn.disabled = true; resDiv.classList.add('hidden');
    try {
        const res = await fetch(`/api/run_backtest?symbol=${symbol}&strategy=${strat}`, { method: 'POST' });
        const data = await res.json();
        if(data.success) { resDiv.textContent = data.report; resDiv.classList.remove('hidden'); } 
        else { alert("Error: " + data.error); }
    } catch(e) { alert("Failed to run backtest"); }
    btn.innerHTML = 'Run Simulation'; btn.disabled = false;
}

async function loadLiveTickers() {
    try {
        const res = await fetch('/api/live_tickers');
        const data = await res.json();
        if(data.length > 0) {
            let top10 = data.slice(0, 10);
            let tickerHtml = top10.map(d => {
                const color = d.change >= 0 ? 'text-neon-green' : 'text-neon-red';
                const sign = d.change >= 0 ? '+' : '';
                return `<span class="mx-4 font-mono text-xs"><span class="text-slate-300 font-bold">${d.symbol}</span> <span class="text-white">$${fmt(d.price)}</span> <span class="${color}">${sign}${d.change}%</span></span>`;
            }).join('');
            document.getElementById('ticker-content').innerHTML = tickerHtml + tickerHtml;

            const marketGrid = document.getElementById('market-watch');
            marketGrid.innerHTML = data.map(d => {
                const isUp = d.change >= 0;
                const textColor = isUp ? 'text-neon-green' : 'text-neon-red';
                const bgColor = isUp ? 'bg-[rgba(0,255,102,0.03)]' : 'bg-[rgba(255,0,60,0.03)]';
                const sign = isUp ? '+' : '';
                return `
                <div class="flex justify-between items-center p-2 rounded border border-slate-800 ${bgColor} mb-1">
                    <span class="font-bold text-slate-200 text-xs">${d.symbol}</span>
                    <div class="text-right">
                        <div class="text-white text-xs font-mono">$${fmt(d.price)}</div>
                        <div class="${textColor} text-[9px] font-mono">${sign}${d.change}%</div>
                    </div>
                </div>`;
            }).join('');
        }
    } catch(e) {}
}

function initTVChart() {
    const chartElement = document.getElementById('tvchart');
    if(!chartElement) return;
    
    const width = chartElement.clientWidth > 0 ? chartElement.clientWidth : 350;
    const styles = getComputedStyle(document.body);
    const upColor = styles.getPropertyValue('--up-color').trim();
    const downColor = styles.getPropertyValue('--down-color').trim();
    
    tvChart = LightweightCharts.createChart(chartElement, {
        width: width,
        height: 224,
        layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#64748b' },
        grid: { vertLines: { color: 'rgba(255, 255, 255, 0.02)' }, horzLines: { color: 'rgba(255, 255, 255, 0.02)' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    
    candleSeries = tvChart.addCandlestickSeries({
        upColor: upColor,
        downColor: downColor,
        borderVisible: false,
        wickUpColor: upColor,
        wickDownColor: downColor,
    });
    
    window.addEventListener('resize', () => {
        tvChart.applyOptions({ width: chartElement.clientWidth });
    });
    
    loadChartData(currentSymbol);
}

async function loadChartData(symbol) {
    const loader = document.getElementById('loading-chart');
    loader.classList.remove('hidden');
    
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
                    time: entryTime,
                    position: pos.side === 'LONG' ? 'belowBar' : 'aboveBar',
                    color: pos.side === 'LONG' ? '#00ff66' : '#ff003c',
                    shape: pos.side === 'LONG' ? 'arrowUp' : 'arrowDown',
                    text: pos.side
                });
                
                candleSeries.createPriceLine({ price: Number(pos.entry_price), color: '#00f3ff', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ENTRY' });
                candleSeries.createPriceLine({ price: Number(pos.stop_price), color: '#ff003c', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'STOP' });
                candleSeries.createPriceLine({ price: Number(pos.target_price), color: '#00ff66', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TARGET' });
            });
            
            candleSeries.setMarkers(markers);
        }
    } catch(e) {
        console.error("Failed to load chart data", e);
    }
    
    loader.classList.add('hidden');
}

function changeChartSymbol() {
    currentSymbol = document.getElementById('chart-symbol').value;
    loadChartData(currentSymbol);
}

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
        let d = new Date(today);
        d.setDate(today.getDate() - i);
        let dateStr = d.toISOString().split('T')[0];
        let pnl = dayStats[dateStr] || 0;
        
        let cellClass = 'neutral';
        if (pnl > 0) cellClass = 'win';
        else if (pnl < 0) cellClass = 'loss';
        
        html += `<div class="heatmap-cell ${cellClass}" title="${dateStr}: ${pnl > 0 ? '+' : ''}${pnl.toFixed(2)} USDT"></div>`;
    }
    heatmapContainer.innerHTML = html;
}

async function load(){
 try{
  const results = await Promise.allSettled([
      fetch('/api/portfolio').then(y=>y.json()), 
      fetch('/api/risk').then(y=>y.json()),
      fetch('/api/positions').then(y=>y.json()), 
      fetch('/api/performance').then(y=>y.json()),
      fetch('/api/status').then(y=>y.json()),
      fetch('/api/decisions').then(y=>y.json()),
      fetch('/api/trades').then(y=>y.json())
  ]);
  
  const p = results[0].status === 'fulfilled' ? results[0].value : {equity: 0, cash_balance: 0, unrealized_pnl: 0, realized_pnl: 0};
  const ps = results[2].status === 'fulfilled' ? results[2].value : [];
  const perf = results[3].status === 'fulfilled' ? results[3].value : {win_rate: 0, profit_factor: 0};
  const status = results[4].status === 'fulfilled' ? results[4].value : {paused: false};
  const decisions = results[5].status === 'fulfilled' ? results[5].value : [];
  const trades = results[6].status === 'fulfilled' ? results[6].value : [];

  currentPositions = ps;

  updatePauseButton(status.paused);
  document.getElementById('total-equity').textContent = fmt(p.equity);
  
  const pnlVal = p.unrealized_pnl + p.realized_pnl;
  const pnlPercent = (pnlVal / 200) * 100;
  const pnlDisplay = document.getElementById('pnl-display');
  document.getElementById('pnl-value').textContent = `${pnlVal >= 0 ? '+' : ''}${fmt(pnlVal)} USDT`;
  document.getElementById('pnl-percent').textContent = `(${pnlVal >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`;
  
  if(pnlVal > 0) { pnlDisplay.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-[rgba(0,255,102,0.1)] text-neon-green border border-[rgba(0,255,102,0.3)] shadow-inner"; } 
  else if(pnlVal < 0) { pnlDisplay.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-[rgba(255,0,60,0.1)] text-neon-red border border-[rgba(255,0,60,0.3)] shadow-inner"; } 
  else { pnlDisplay.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-slate-800/50 border border-slate-700 shadow-inner"; }

  document.getElementById('winrate').textContent = perf.win_rate ? fmt(perf.win_rate) + '%' : '0.00%';
  document.getElementById('pf').textContent = (perf.profit_factor === null ? '∞' : (perf.profit_factor ? fmt(perf.profit_factor) : '0.00'));

  updateHeatmap(trades);

  const stratContainer = document.getElementById('strategy-stats');
  if (trades.length > 0) {
      let stratMap = {};
      trades.filter(t => t.status === 'CLOSED').forEach(t => {
          let s = t.strategy || 'unknown';
          if (!stratMap[s]) stratMap[s] = { net: 0, count: 0, wins: 0 };
          stratMap[s].net += Number(t.net_pnl) || 0;
          stratMap[s].count += 1;
          if (Number(t.net_pnl) > 0) stratMap[s].wins += 1;
      });
      
      let html = '';
      for (const [name, data] of Object.entries(stratMap)) {
          let winRate = data.count > 0 ? (data.wins / data.count * 100) : 0;
          let colorClass = data.net >= 0 ? 'bg-neon-green' : 'bg-neon-red';
          let textColor = data.net >= 0 ? 'text-neon-green' : 'text-neon-red';
          html += `
            <div>
                <div class="flex justify-between text-[10px] mb-1">
                    <span class="uppercase text-slate-300">${name}</span>
                    <span class="${textColor}">${data.net >= 0 ? '+' : ''}${fmt(data.net)} USDT (${winRate.toFixed(0)}%)</span>
                </div>
                <div class="progress-bg"><div class="progress-fill ${colorClass}" style="width: ${winRate}%"></div></div>
            </div>
          `;
      }
      stratContainer.innerHTML = html;
  } else {
      stratContainer.innerHTML = '<div class="text-slate-500 text-xs font-mono">No closed trades yet.</div>';
  }

  const posContainer = document.getElementById('active-positions-list');
  document.getElementById('pos-count').textContent = `${ps.length} Open`;
  if(ps.length === 0) {
    posContainer.innerHTML = '<div class="text-center text-slate-500 text-xs py-4 glass rounded-xl font-mono">NO ACTIVE POSITIONS</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => `
      <div class="glass rounded-xl p-4 mb-3 border-l-2 ${pos.side === 'LONG' ? 'border-l-neon-green' : 'border-l-neon-red'}">
        <div class="flex justify-between items-start mb-3">
          <div>
            <h4 class="font-bold text-white text-lg tracking-wide">${pos.symbol}</h4>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded ${pos.side === 'LONG' ? 'bg-[rgba(0,255,102,0.1)] text-neon-green' : 'bg-[rgba(255,0,60,0.1)] text-neon-red'}">${pos.side}</span>
          </div>
          <div class="text-right">
            <p class="text-[10px] text-slate-400 uppercase tracking-wider">Entry</p>
            <p class="font-mono text-sm text-white">${Number(pos.entry_price).toFixed(4)}</p>
          </div>
        </div>
        <div class="flex justify-between items-center pt-3 border-t border-slate-700/50">
           <div class="flex gap-4">
               <div><p class="text-[10px] text-slate-500 uppercase">Target</p><p class="font-mono text-xs text-neon-green">${Number(pos.target_price).toFixed(4)}</p></div>
               <div><p class="text-[10px] text-slate-500 uppercase">Stop</p><p class="font-mono text-xs text-neon-red">${Number(pos.stop_price).toFixed(4)}</p></div>
           </div>
           <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="text-[10px] font-bold text-neon-red border border-neon-red/30 px-3 py-1.5 rounded hover:bg-neon-red/10 active:scale-95 transition-all bg-[rgba(255,0,60,0.05)]">CLOSE</button>
        </div>
      </div>
    `).join('');
  }

  const histContainer = document.getElementById('trade-history');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 10);
  if(closedTrades.length === 0) {
      histContainer.innerHTML = '<div class="text-center text-slate-500 text-xs py-4 font-mono">NO RECENT TRADES</div>';
  } else {
      let html = `<table class="w-full text-left text-xs text-slate-300 min-w-[300px]">
        <thead class="bg-slate-800/50 text-[10px] uppercase text-slate-500">
          <tr><th class="p-2">Asset</th><th class="p-2">Side</th><th class="p-2 text-right">Entry</th><th class="p-2 text-right">Net PnL</th></tr>
        </thead><tbody>`;
      closedTrades.forEach(t => {
          const isWin = Number(t.net_pnl) > 0;
          html += `<tr class="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td class="p-2 font-bold text-white">${t.symbol}</td>
              <td class="p-2"><span class="text-[9px] font-bold ${t.side === 'LONG' ? 'text-neon-green' : 'text-neon-red'}">${t.side}</span></td>
              <td class="p-2 text-right font-mono">${Number(t.entry_price).toFixed(2)}</td>
              <td class="p-2 text-right font-mono font-bold ${isWin ? 'text-neon-green' : 'text-neon-red'}">${isWin ? '+' : ''}${fmt(t.net_pnl)}</td>
          </tr>`;
      });
      html += '</tbody></table>';
      histContainer.innerHTML = html;
  }

  const logContainer = document.getElementById('neural-logs');
  if(decisions.length === 0) {
    logContainer.innerHTML = '<div class="text-slate-500">No scans yet...</div>';
  } else {
    logContainer.innerHTML = decisions.slice(0, 15).map(d => {
        const time = new Date(d.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        let color = d.action.includes('BUY') ? 'text-neon-green' : d.action.includes('SHORT') ? 'text-neon-red' : 'text-slate-400';
        return `<div class="mb-1 flex gap-2"><span class="text-slate-600 shrink-0">[${time}]</span> <span class="text-white shrink-0">${d.symbol}</span> <span class="${color} shrink-0">${d.action}</span> <span class="text-slate-500 truncate">${d.reason.substring(0, 50)}...</span></div>`;
    }).join('');
  }

  const currentSymbolPos = ps.find(p => p.symbol === currentSymbol);
  if (currentSymbolPos) {
      loadChartData(currentSymbol); 
  }

 }catch(e){ console.error('System Error:', e); }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { initTVChart(); }, 200);
    loadLiveTickers();
    load(); 
    setInterval(load, 3000);
    setInterval(loadLiveTickers, 10000);
    setInterval(() => { loadChartData(currentSymbol); }, 30000); 
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
async def risk(request:Request): return request.app.state.engine.risk.get_risk_status()
@router.get("/api/positions")
async def positions(request:Request): return request.app.state.db.get_open_positions()
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
