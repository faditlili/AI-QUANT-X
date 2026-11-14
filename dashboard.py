"""The Ultimate AI QUANT X Dashboard - Flawless Themes & UI."""
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
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>AI QUANT X · Ultimate UI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: { 
        extend: { 
          colors: { 
            brand: { bg: 'var(--bg)', card: 'var(--glass-bg)', border: 'var(--glass-border)' }, 
            neon: { 
              primary: 'var(--primary)', 
              secondary: 'var(--secondary)', 
              up: 'var(--up-color)', 
              down: 'var(--down-color)',
              text: 'var(--text-main)',
              muted: 'var(--text-muted)'
            } 
          }, 
          fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['Share Tech Mono', 'monospace'], orbitron: ['Orbitron', 'sans-serif'] } 
        } 
      }
    }
  </script>
  <style>
    /* --- Dynamic Theme Variables --- */
    :root, body.theme-cyber {
        --bg: #03040a;
        --bg-grid: rgba(0, 243, 255, 0.03);
        --primary: #00f3ff;
        --secondary: #b026ff;
        --glass-bg: rgba(10, 15, 30, 0.7);
        --glass-border: rgba(0, 243, 255, 0.2);
        --up-color: #00ff66;
        --down-color: #ff003c;
        --card-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }

    body.theme-matrix {
        --bg: #020a05;
        --bg-grid: rgba(0, 255, 102, 0.05);
        --primary: #00ff66;
        --secondary: #00cc44;
        --up-color: #00ff66;
        --down-color: #ff003c;
        --glass-border: rgba(0, 255, 102, 0.2);
    }

    body.theme-gold {
        --bg: #0b0e11;
        --bg-grid: rgba(252, 213, 53, 0.03);
        --primary: #FCD535;
        --secondary: #F0B90B;
        --up-color: #0ecb81;
        --down-color: #f6465d;
        --glass-border: rgba(252, 213, 53, 0.2);
    }

    body.theme-neumorphism {
        --bg: #1e2129;
        --bg-grid: rgba(255, 255, 255, 0.0);
        --primary: #4ade80;
        --secondary: #818cf8;
        --glass-bg: #1e2129;
        --glass-border: transparent;
        --up-color: #4ade80;
        --down-color: #f87171;
        --card-shadow: 8px 8px 16px #14161b, -8px -8px 16px #282c37;
        --text-main: #e2e8f0;
        --text-muted: #94a3b8;
    }

    body.theme-light {
        --bg: #f8fafc;
        --bg-grid: rgba(0, 0, 0, 0.02);
        --primary: #3b82f6;
        --secondary: #f97316;
        --glass-bg: #ffffff;
        --glass-border: #e2e8f0;
        --up-color: #10b981;
        --down-color: #ef4444;
        --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        --text-main: #0f172a;
        --text-muted: #64748b;
    }

    body { 
        background-color: var(--bg); 
        background-image: radial-gradient(circle at 50% 0%, var(--bg-grid) 0%, transparent 60%), linear-gradient(var(--bg-grid) 1px, transparent 1px), linear-gradient(90deg, var(--bg-grid) 1px, transparent 1px); 
        background-size: 100% 100%, 40px 40px, 40px 40px; 
        color: var(--text-main); 
        font-family: 'Inter', sans-serif; 
        -webkit-tap-highlight-color: transparent;
        transition: background-color 0.3s ease, color 0.3s ease;
    }
    
    .glass { 
        background: var(--glass-bg); 
        backdrop-filter: blur(16px); 
        border: 1px solid var(--glass-border); 
        box-shadow: var(--card-shadow); 
        border-radius: 1rem;
        transition: all 0.3s ease;
    }
    
    .liquid-btn {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 0.5rem;
        transition: all 0.2s ease;
        box-shadow: var(--card-shadow);
    }
    .liquid-btn:active { transform: scale(0.96); }

    .custom-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; opacity: 0.5; }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    
    .tab-btn { 
        padding: 0.75rem 0.5rem; 
        font-size: 0.75rem; 
        font-weight: 600; 
        color: var(--text-muted); 
        border-bottom: 2px solid transparent; 
        transition: all 0.2s; 
        display: flex; 
        align-items: center; 
        gap: 0.25rem; 
        white-space: nowrap; 
    }
    .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
    
    @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .toast { animation: slideDown 0.3s ease-out forwards; }
  </style>
</head>
<body class="theme-cyber min-h-screen pb-10">

  <div id="toast-container" class="fixed top-4 left-0 right-0 z-[100] flex flex-col items-center gap-2 px-4 pointer-events-none"></div>

  <nav class="glass sticky top-0 z-30 rounded-none border-t-0 border-x-0" style="border-bottom: 1px solid var(--glass-border);">
    <div class="max-w-md mx-auto px-4">
      <div class="flex justify-between items-center h-14 gap-2">
        <!-- Logo -->
        <div class="flex items-center gap-2 flex-shrink-0">
            <div style="background-color: var(--primary); color: var(--bg); width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 10px var(--primary);">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M9 1v3"/><path d="M15 1v3"/><path d="M9 20v3"/><path d="M15 20v3"/><path d="M20 9h3"/><path d="M20 14h3"/><path d="M1 9h3"/><path d="M1 14h3"/></svg>
            </div>
            <span class="font-bold text-base tracking-tight whitespace-nowrap" style="color: var(--text-main);">AI QUANT</span>
        </div>
        <!-- Buttons -->
        <div class="flex gap-1.5 overflow-x-auto no-scrollbar items-center">
            <button onclick="cycleTheme()" class="p-2 liquid-btn" title="Change Theme">
                <i data-lucide="palette" class="w-3.5 h-3.5" style="color: var(--primary);"></i>
            </button>
            <button onclick="runAutoTune()" class="px-2.5 py-1.5 liquid-btn flex items-center gap-1 whitespace-nowrap text-[10px] font-bold" style="color: var(--secondary);">
                <i data-lucide="cpu" class="w-3.5 h-3.5"></i> AUTO
            </button>
            <button onclick="openBacktest()" class="px-2.5 py-1.5 liquid-btn flex items-center gap-1 whitespace-nowrap text-[10px] font-bold" style="color: var(--text-main);">
                <i data-lucide="flask-conical" class="w-3.5 h-3.5"></i> TEST
            </button>
            <button id="pause-btn" onclick="togglePause()" class="px-2.5 py-1.5 liquid-btn flex items-center gap-1 whitespace-nowrap text-[10px] font-bold" style="color: var(--up-color);">
                <i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE
            </button>
        </div>
      </div>
      <!-- Tabs -->
      <div class="flex gap-1 mt-1 overflow-x-auto custom-scroll border-b text-[11px] px-1" style="border-color: var(--glass-border);">
        <button class="tab-btn active" onclick="switchTab('overview', this)"><i data-lucide="layout-dashboard" class="w-3.5 h-3.5"></i> Overview</button>
        <button class="tab-btn" onclick="switchTab('positions', this)"><i data-lucide="briefcase" class="w-3.5 h-3.5"></i> Positions</button>
        <button class="tab-btn" onclick="switchTab('history', this)"><i data-lucide="history" class="w-3.5 h-3.5"></i> History</button>
        <button class="tab-btn" onclick="switchTab('logs', this)"><i data-lucide="terminal" class="w-3.5 h-3.5"></i> Logs</button>
      </div>
    </div>
  </nav>

  <div class="max-w-md mx-auto px-4 pt-4">
    
    <!-- OVERVIEW TAB -->
    <div id="tab-overview" class="space-y-4">
        <!-- Balance -->
        <section class="glass p-5 relative overflow-hidden">
            <div class="absolute top-0 right-0 p-4 opacity-10"><i data-lucide="wallet" class="w-24 h-24" style="color: var(--primary);"></i></div>
            <p class="text-xs font-semibold uppercase tracking-wider mb-1" style="color: var(--text-muted);">Total Balance</p>
            <div class="flex items-end gap-2 relative z-10">
                <h2 id="total-equity" class="text-4xl font-bold font-mono tracking-tighter" style="color: var(--text-main);">0.00</h2>
                <span class="text-xs mb-1.5 font-bold" style="color: var(--text-muted);">USDT</span>
            </div>
            <div id="pnl-display" class="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border relative z-10" style="background: rgba(255,255,255,0.05); border-color: var(--glass-border);">
                <i data-lucide="minus" class="w-4 h-4" id="pnl-icon" style="color: var(--text-muted);"></i>
                <span id="pnl-value" style="color: var(--text-muted);">0.00 USDT</span>
                <span id="pnl-percent" style="color: var(--text-muted); opacity: 0.7;">(0.00%)</span>
            </div>
        </section>

        <!-- Stats Doughnuts -->
        <section class="grid grid-cols-2 gap-3">
            <div class="glass p-4 flex flex-col items-center justify-center">
                <h3 class="text-[11px] font-bold uppercase mb-2" style="color: var(--text-muted);">Win Rate</h3>
                <div class="relative w-20 h-20">
                    <canvas id="winrateChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="winrate" class="text-sm font-bold font-mono" style="color: var(--text-main);">0%</span>
                    </div>
                </div>
            </div>
            <div class="glass p-4 flex flex-col items-center justify-center">
                <h3 class="text-[11px] font-bold uppercase mb-2" style="color: var(--text-muted);">Profit Factor</h3>
                <div class="relative w-20 h-20">
                    <canvas id="pfChart"></canvas>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <span id="pf" class="text-sm font-bold font-mono" style="color: var(--text-main);">0.0</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Weekly Bar Chart -->
        <section class="glass p-4">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xs font-bold uppercase tracking-wider flex items-center gap-2" style="color: var(--text-main);"><i data-lucide="bar-chart-2" class="w-4 h-4" style="color: var(--primary);"></i> Weekly PnL</h3>
                <span class="text-[10px] font-medium" style="color: var(--text-muted);">Last 7 Days</span>
            </div>
            <div class="h-32 w-full">
                <canvas id="weeklyChart"></canvas>
            </div>
            
            <div class="grid grid-cols-3 gap-2 mt-4 pt-4 border-t" style="border-color: var(--glass-border);">
                <div class="text-center">
                    <p class="text-[10px] uppercase font-bold" style="color: var(--text-muted);">Trades</p>
                    <p id="stat-trades" class="text-sm font-bold font-mono mt-1" style="color: var(--text-main);">0</p>
                </div>
                <div class="text-center border-x" style="border-color: var(--glass-border);">
                    <p class="text-[10px] uppercase font-bold" style="color: var(--text-muted);">Best</p>
                    <p id="stat-best" class="text-sm font-bold font-mono mt-1" style="color: var(--text-muted);">0.00</p>
                </div>
                <div class="text-center">
                    <p class="text-[10px] uppercase font-bold" style="color: var(--text-muted);">Worst</p>
                    <p id="stat-worst" class="text-sm font-bold font-mono mt-1" style="color: var(--text-muted);">0.00</p>
                </div>
            </div>
        </section>

        <!-- Live Chart -->
        <section class="glass p-4">
            <div class="flex justify-between items-center mb-3">
                <h3 class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-main);">Market Chart</h3>
                <select id="chart-symbol" onchange="changeChartSymbol()" class="border text-[11px] rounded-md px-2 py-1 outline-none font-bold" style="background: var(--bg); border-color: var(--glass-border); color: var(--text-main);">
                    <option value="BTCUSDT">BTC/USDT</option>
                    <option value="ETHUSDT">ETH/USDT</option>
                    <option value="SOLUSDT">SOL/USDT</option>
                    <option value="BNBUSDT">BNB/USDT</option>
                </select>
            </div>
            <div id="tvchart" class="w-full h-48 rounded-lg overflow-hidden border" style="border-color: var(--glass-border);"></div>
        </section>

        <!-- Breadth -->
        <section class="glass p-3 flex items-center justify-between">
            <div class="flex items-center gap-2">
                <i data-lucide="bar-chart" class="w-4 h-4" style="color: var(--text-muted);"></i>
                <span class="text-xs font-bold" style="color: var(--text-main);">Market Breadth</span>
            </div>
            <div class="flex items-center gap-3 w-1/2">
                <div class="w-full rounded-full h-1.5 flex-1" style="background: rgba(255,255,255,0.1);">
                    <div id="breadth-bar" class="h-1.5 rounded-full transition-all duration-500" style="width: 50%; background: var(--text-muted);"></div>
                </div>
                <span id="breadth-label" class="text-[10px] font-bold w-12 text-right font-mono" style="color: var(--text-main);">50%</span>
            </div>
        </section>

        <!-- Market Watch -->
        <section class="glass p-4">
            <h3 class="text-xs font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style="color: var(--text-main);"><i data-lucide="globe" class="w-4 h-4" style="color: var(--text-muted);"></i> Market Watch</h3>
            <div class="h-40 overflow-y-auto custom-scroll pr-1" id="market-watch">
                <div class="text-center text-xs py-4" style="color: var(--text-muted);">Loading data...</div>
            </div>
        </section>
    </div>

    <!-- POSITIONS TAB -->
    <div id="tab-positions" class="hidden space-y-3">
        <div class="flex justify-between items-center mb-1">
            <h3 class="text-lg font-bold" style="color: var(--text-main);">Active Positions</h3>
            <span id="pos-count" class="text-xs font-bold px-2 py-1 rounded-md" style="background: var(--glass-bg); color: var(--text-muted); border: 1px solid var(--glass-border);">0 Open</span>
        </div>
        <div id="active-positions-list" class="space-y-3"></div>
    </div>

    <!-- HISTORY TAB -->
    <div id="tab-history" class="hidden space-y-3">
        <h3 class="text-lg font-bold mb-1" style="color: var(--text-main);">Trade History</h3>
        <div class="glass overflow-hidden" id="trade-history">
            <div class="text-center text-xs py-8" style="color: var(--text-muted);">Loading history...</div>
        </div>
    </div>

    <!-- LOGS TAB -->
    <div id="tab-logs" class="hidden space-y-3">
        <h3 class="text-lg font-bold mb-1" style="color: var(--text-main);">AI Neural Logs</h3>
        <div class="glass p-3 h-[calc(100vh-200px)] overflow-y-auto font-mono text-[10px] custom-scroll" style="background: #0f172a; color: #cbd5e1;" id="neural-logs">
            <div style="color: var(--text-muted);">Waiting for scan cycle...</div>
        </div>
    </div>

  </div>

  <!-- Custom Modals (Perfectly Centered) -->
  <div id="backtest-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]" style="display: none;">
    <div class="absolute inset-0 flex items-center justify-center p-4">
        <div class="glass p-5 w-full max-w-sm shadow-2xl">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-base font-bold flex items-center gap-2" style="color: var(--text-main);"><i data-lucide="flask-conical" class="w-4 h-4" style="color: var(--primary);"></i> Run Backtest</h3>
            <button onclick="closeBacktest()" class="liquid-btn p-1" style="color: var(--text-muted);"><i data-lucide="x" class="w-4 h-4"></i></button>
          </div>
          <div class="space-y-3 mb-5">
            <select id="bt-symbol" class="w-full border rounded-lg p-2 text-xs outline-none font-bold" style="background: var(--bg); border-color: var(--glass-border); color: var(--text-main);">
              <option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option><option value="SOLUSDT">SOLUSDT</option>
            </select>
            <select id="bt-strat" class="w-full border rounded-lg p-2 text-xs outline-none font-bold" style="background: var(--bg); border-color: var(--glass-border); color: var(--text-main);">
              <option value="all">All Strategies</option><option value="trend">Trend</option><option value="mean_reversion">Mean Reversion</option><option value="breakout">Breakout</option>
            </select>
          </div>
          <button onclick="runBacktest()" id="bt-run-btn" class="w-full font-bold py-2.5 rounded-lg transition-all flex justify-center items-center gap-2 text-sm shadow-lg" style="background: var(--primary); color: var(--bg);">
            <i data-lucide="play" class="w-4 h-4"></i> Run Simulation
          </button>
          <div id="bt-results" class="mt-3 text-[10px] font-mono whitespace-pre-wrap hidden p-3 rounded-lg border max-h-40 overflow-y-auto custom-scroll" style="background: rgba(0,0,0,0.2); border-color: var(--glass-border); color: var(--text-main);"></div>
        </div>
    </div>
  </div>

  <div id="confirm-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100]" style="display: none;">
    <div class="absolute inset-0 flex items-center justify-center p-4">
        <div class="glass p-6 w-full max-w-sm shadow-2xl text-center">
          <div class="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center" style="background: rgba(255,255,255,0.1);">
              <i data-lucide="alert-circle" class="w-6 h-6" style="color: var(--primary);"></i>
          </div>
          <h3 id="confirm-title" class="text-lg font-bold mb-2" style="color: var(--text-main);">تأكيد</h3>
          <p id="confirm-message" class="text-sm mb-6" style="color: var(--text-muted);">هل أنت متأكد؟</p>
          <div class="grid grid-cols-2 gap-3">
            <button onclick="closeConfirm(false)" class="w-full font-bold py-2.5 rounded-lg transition-all text-sm liquid-btn" style="color: var(--text-main);">إلغاء</button>
            <button onclick="closeConfirm(true)" class="w-full font-bold py-2.5 rounded-lg transition-all text-sm shadow-lg" style="background: var(--primary); color: var(--bg);">حسناً</button>
          </div>
        </div>
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
let confirmCallback = null;

const refreshIcons = () => { try { if (window.lucide) window.lucide.createIcons(); } catch (e) {} };
const fmt = (n) => Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fmtPrice = (n) => { n = Number(n); if (!isFinite(n)) return '-'; const a = Math.abs(n); if (a >= 1000) return fmt(n); if (a >= 1) return n.toFixed(4); return n.toPrecision(4); };

// --- Theme Logic ---
const themes = ['theme-cyber', 'theme-matrix', 'theme-gold', 'theme-neumorphism', 'theme-light'];
let currentThemeIndex = parseInt(localStorage.getItem('themeIndex') || '0');

function applyTheme(index) {
    document.body.className = document.body.className.replace(/theme-\w+/g, '').trim();
    document.body.classList.add(themes[index]);
    localStorage.setItem('themeIndex', index);
    
    const styles = getComputedStyle(document.body);
    const upColor = styles.getPropertyValue('--up-color').trim();
    const downColor = styles.getPropertyValue('--down-color').trim();
    const primaryColor = styles.getPropertyValue('--primary').trim();
    const textColor = styles.getPropertyValue('--text-muted').trim();
    const isLight = themes[index] === 'theme-light';
    
    // Update TradingView Chart
    if (tvChart && candleSeries) {
        candleSeries.applyOptions({
            upColor: upColor,
            downColor: downColor,
            wickUpColor: upColor,
            wickDownColor: downColor
        });
        tvChart.applyOptions({
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: textColor },
            grid: { vertLines: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' }, horzLines: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' } }
        });
        drawPositionOverlays(); 
    }
    
    // Update Doughnut Charts
    if(winrateChart) {
        winrateChart.data.datasets[0].backgroundColor[0] = upColor;
        winrateChart.data.datasets[0].backgroundColor[1] = isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)';
        winrateChart.update();
    }
    if(pfChart) {
        pfChart.data.datasets[0].backgroundColor[0] = '#8b5cf6';
        pfChart.data.datasets[0].backgroundColor[1] = isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)';
        pfChart.update();
    }
    // Update Weekly Chart
    if(weeklyChart) {
        const data = weeklyChart.data.datasets[0].data;
        weeklyChart.data.datasets[0].backgroundColor = data.map(v => v > 0 ? upColor : (v < 0 ? downColor : (isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)')));
        weeklyChart.update();
    }
}

function cycleTheme() {
    currentThemeIndex = (currentThemeIndex + 1) % themes.length;
    applyTheme(currentThemeIndex);
}

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentThemeIndex);
});

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const bgColor = type === 'success' ? 'var(--up-color)' : type === 'error' ? 'var(--down-color)' : 'var(--primary)';
    const textColor = type === 'info' ? 'var(--bg)' : '#fff';
    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info';
    
    toast.className = `toast px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2 pointer-events-auto text-xs font-bold`;
    toast.style.backgroundColor = bgColor;
    toast.style.color = textColor;
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

function showConfirm(title, message, callback) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    confirmCallback = callback;
    document.getElementById('confirm-modal').style.display = 'block';
}

function closeConfirm(isConfirmed) {
    document.getElementById('confirm-modal').style.display = 'none';
    if (isConfirmed && confirmCallback) {
        confirmCallback();
    }
    confirmCallback = null;
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
        btn.style.color = 'var(--down-color)';
        btn.innerHTML = '<i data-lucide="pause-circle" class="w-3.5 h-3.5"></i> PAUSED';
    } else {
        btn.style.color = 'var(--up-color)';
        btn.innerHTML = '<i data-lucide="activity" class="w-3.5 h-3.5"></i> ACTIVE';
    }
    refreshIcons();
}

async function closePosition(id, symbol) {
    showConfirm('إغلاق الصفقة', `هل أنت متأكد من إغلاق صفقة ${symbol} الآن؟`, async () => {
        try {
            const res = await fetch(`/api/close_position/${id}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) showToast(`Closed ${symbol}`, 'success');
            else showToast('Error: ' + (data.error || 'close failed'), 'error');
        } catch (e) { showToast('Failed to close position', 'error'); }
        load();
    });
}

function runAutoTune() {
    showConfirm('الضبط التلقائي', 'هل تريد تشغيل الضبط التلقائي؟ سيختبر البوت أفضل الإعدادات ويطبقها على نفسه.', async () => {
        showToast('Auto-Tuning in progress... (Please wait)', 'info');
        try {
            const res = await fetch('/api/auto_tune?symbol=BTCUSDT&strategy=trend', { method: 'POST' });
            const data = await res.json();
            if(data.success) {
                showToast(`Done! Best: RSI ${data.best_params.RSI} & EMA ${data.best_params.EMA} (${data.return_pct.toFixed(1)}%)`, 'success');
            } else {
                showToast("Error: " + data.error, 'error');
            }
        } catch(e) {
            showToast("Failed to auto-tune", 'error');
        }
    });
}

function openBacktest() { document.getElementById('backtest-modal').style.display = 'block'; }
function closeBacktest() { document.getElementById('backtest-modal').style.display = 'none'; }

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
    btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> Run Simulation'; btn.disabled = false;
    refreshIcons();
}

function initTVChart() {
    const chartElement = document.getElementById('tvchart');
    if(!chartElement) return;
    const width = chartElement.clientWidth > 0 ? chartElement.clientWidth : 350;
    const isLight = document.body.classList.contains('theme-light');
    const textColor = getComputedStyle(document.body).getPropertyValue('--text-muted').trim();
    
    tvChart = LightweightCharts.createChart(chartElement, {
        width: width, height: 192,
        layout: { background: { type: 'solid', color: 'transparent' }, textColor: textColor },
        grid: { vertLines: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' }, horzLines: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    
    candleSeries = tvChart.addCandlestickSeries({
        upColor: getComputedStyle(document.body).getPropertyValue('--up-color').trim(), 
        downColor: getComputedStyle(document.body).getPropertyValue('--down-color').trim(),
        borderVisible: false, 
        wickUpColor: getComputedStyle(document.body).getPropertyValue('--up-color').trim(), 
        wickDownColor: getComputedStyle(document.body).getPropertyValue('--down-color').trim(),
    });
    
    window.addEventListener('resize', () => { tvChart.applyOptions({ width: chartElement.clientWidth }); });
    loadChartData(currentSymbol);

    setTimeout(() => {
        const w = chartElement.clientWidth;
        if (w > 0) {
            tvChart.applyOptions({ width: w, height: 192 });
            tvChart.timeScale().fitContent();
        }
    }, 500);
}

function initCharts() {
    const upColor = getComputedStyle(document.body).getPropertyValue('--up-color').trim();
    const isLight = document.body.classList.contains('theme-light');
    const emptyColor = isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)';

    const ctxWin = document.getElementById('winrateChart').getContext('2d');
    winrateChart = new Chart(ctxWin, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: [upColor, emptyColor], borderWidth: 0, cutout: '75%' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { tooltip: { enabled: false } } }
    });

    const ctxPf = document.getElementById('pfChart').getContext('2d');
    pfChart = new Chart(ctxPf, {
        type: 'doughnut',
        data: { datasets: [{ data: [0, 100], backgroundColor: ['#8b5cf6', emptyColor], borderWidth: 0, cutout: '75%' }] },
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
                backgroundColor: emptyColor,
                borderRadius: 4,
                barPercentage: 0.6
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw > 0 ? '+' : ''}${fmt(ctx.raw)} USDT` } } },
            scales: {
                x: { grid: { display: false }, ticks: { font: { size: 10 }, color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim() } },
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
                let textColor = 'var(--text-muted)';
                let sign = '';
                if (d.change > 0) { textColor = 'var(--up-color)'; sign = '+'; }
                else if (d.change < 0) { textColor = 'var(--down-color)'; }

                return `
                <div class="flex justify-between items-center p-2 rounded-lg mb-1" style="background: rgba(255,255,255,0.03);">
                    <span class="font-bold text-[11px]" style="color: var(--text-main);">${d.symbol}</span>
                    <div class="text-right">
                        <div class="text-[11px] font-mono font-semibold" style="color: var(--text-main);">$${fmtPrice(d.price)}</div>
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
    
    const upColor = getComputedStyle(document.body).getPropertyValue('--up-color').trim();
    const downColor = getComputedStyle(document.body).getPropertyValue('--down-color').trim();
    
    currentPositions.filter(p => p.symbol === currentSymbol).forEach(pos => {
        const entryTime = Math.floor(new Date(pos.opened_at).getTime() / 1000);
        markers.push({
            time: entryTime, position: pos.side === 'LONG' ? 'belowBar' : 'aboveBar',
            color: pos.side === 'LONG' ? upColor : downColor,
            shape: pos.side === 'LONG' ? 'arrowUp' : 'arrowDown', text: pos.side
        });
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.entry_price), color: '#3b82f6', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ENTRY' }));
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.stop_price), color: downColor, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'STOP' }));
        priceLines.push(candleSeries.createPriceLine({ price: Number(pos.target_price), color: upColor, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TARGET' }));
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
    
    const upColor = getComputedStyle(document.body).getPropertyValue('--up-color').trim();
    const downColor = getComputedStyle(document.body).getPropertyValue('--down-color').trim();
    const isLight = document.body.classList.contains('theme-light');
    const emptyColor = isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)';
    
    const bgColors = data.map(v => v > 0 ? upColor : (v < 0 ? downColor : emptyColor));
    
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
    
    const bestEl = document.getElementById('stat-best');
    if (bestTrade > 0) {
        bestEl.style.color = upColor;
        bestEl.textContent = `+${fmt(bestTrade)}`;
    } else {
        bestEl.style.color = 'var(--text-muted)';
        bestEl.textContent = `0.00`;
    }

    const worstEl = document.getElementById('stat-worst');
    if (worstTrade < 0) {
        worstEl.style.color = downColor;
        worstEl.textContent = `${fmt(worstTrade)}`;
    } else {
        worstEl.style.color = 'var(--text-muted)';
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
  
  const upColor = getComputedStyle(document.body).getPropertyValue('--up-color').trim();
  const downColor = getComputedStyle(document.body).getPropertyValue('--down-color').trim();
  const neutralColor = getComputedStyle(document.body).getPropertyValue('--text-muted').trim();
  
  if (pnlVal > 0) {
      pnlValueEl.textContent = `+${fmt(pnlVal)} USDT`;
      pnlPercentEl.textContent = `(+${pnlPercent.toFixed(2)}%)`;
      pnlDisplay.style.borderColor = upColor;
      pnlValueEl.style.color = upColor;
      pnlPercentEl.style.color = upColor;
      pnlIcon.setAttribute('data-lucide', 'trending-up');
      pnlIcon.className = "w-4 h-4";
      pnlIcon.style.color = upColor;
  } else if (pnlVal < 0) {
      pnlValueEl.textContent = `${fmt(pnlVal)} USDT`;
      pnlPercentEl.textContent = `(${pnlPercent.toFixed(2)}%)`;
      pnlDisplay.style.borderColor = downColor;
      pnlValueEl.style.color = downColor;
      pnlPercentEl.style.color = downColor;
      pnlIcon.setAttribute('data-lucide', 'trending-down');
      pnlIcon.className = "w-4 h-4";
      pnlIcon.style.color = downColor;
  } else {
      pnlValueEl.textContent = `0.00 USDT`;
      pnlPercentEl.textContent = `(0.00%)`;
      pnlDisplay.style.borderColor = neutralColor;
      pnlValueEl.style.color = neutralColor;
      pnlPercentEl.style.color = neutralColor;
      pnlIcon.setAttribute('data-lucide', 'minus');
      pnlIcon.className = "w-4 h-4";
      pnlIcon.style.color = neutralColor;
  }
  refreshIcons();

  updateWeeklyStats(trades);

  const breadth = risk.breadth || 50;
  const breadthBar = document.getElementById('breadth-bar');
  const breadthLabel = document.getElementById('breadth-label');
  breadthBar.style.width = `${breadth}%`;
  if(breadth > 60) { breadthBar.style.backgroundColor = upColor; breadthLabel.textContent = 'Bullish'; breadthLabel.style.color = upColor; }
  else if(breadth < 40) { breadthBar.style.backgroundColor = downColor; breadthLabel.textContent = 'Bearish'; breadthLabel.style.color = downColor; }
  else { breadthBar.style.backgroundColor = '#3b82f6'; breadthLabel.textContent = 'Neutral'; breadthLabel.style.color = '#3b82f6'; }

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
    posContainer.innerHTML = '<div class="text-center text-sm py-8 glass" style="color: var(--text-muted);">No active positions</div>';
  } else {
    posContainer.innerHTML = ps.map(pos => {
        const currentPrice = Number(pos.current_price || pos.entry_price);
        const entryPrice = Number(pos.entry_price);
        const qty = Number(pos.quantity);
        const sideMultiplier = pos.side === 'LONG' ? 1 : -1;
        const unrealizedPnl = (currentPrice - entryPrice) * qty * sideMultiplier;
        
        let pnlColor = neutralColor;
        let pnlSign = '';
        if (unrealizedPnl > 0) { pnlColor = upColor; pnlSign = '+'; }
        else if (unrealizedPnl < 0) { pnlColor = downColor; }

        return `
      <div class="glass p-4 border-l-4" style="border-left-color: ${pos.side === 'LONG' ? upColor : downColor};">
        <div class="flex justify-between items-start mb-3">
          <div>
              <h4 class="font-bold text-base" style="color: var(--text-main);">${pos.symbol}</h4>
              <div class="flex gap-2 items-center mt-1">
                  <span class="text-[9px] font-bold px-2 py-0.5 rounded" style="background: rgba(255,255,255,0.1); color: var(--text-main);">${pos.side}</span>
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded" style="color: ${pnlColor}; background: rgba(255,255,255,0.05);">${pnlSign}${fmt(unrealizedPnl)} USDT</span>
              </div>
          </div>
          <div class="text-right">
            <p class="text-[9px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">Entry</p>
            <p class="font-mono text-xs font-bold" style="color: var(--text-main);">${fmtPrice(entryPrice)}</p>
            <p class="text-[9px] font-semibold uppercase tracking-wider mt-1" style="color: var(--text-muted);">Current</p>
            <p class="font-mono text-[11px] font-bold" style="color: var(--text-muted);">${fmtPrice(currentPrice)}</p>
          </div>
        </div>
        <div class="flex justify-between items-center pt-3 border-t" style="border-color: var(--glass-border);">
           <div class="flex gap-4">
               <div><p class="text-[9px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">Target</p><p class="font-mono text-[11px] font-bold" style="color: ${upColor};">${fmtPrice(pos.target_price)}</p></div>
               <div><p class="text-[9px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">Stop</p><p class="font-mono text-[11px] font-bold" style="color: ${downColor};">${fmtPrice(pos.stop_price)}</p></div>
           </div>
           <button onclick="closePosition(${pos.id}, '${pos.symbol}')" class="text-[10px] font-bold border px-3 py-1.5 rounded-lg transition-colors liquid-btn" style="color: ${downColor}; border-color: ${downColor}40;">CLOSE</button>
        </div>
      </div>
    `}).join('');
  }

  const histContainer = document.getElementById('trade-history');
  const closedTrades = trades.filter(t => t.status === 'CLOSED').slice(0, 10);
  if(closedTrades.length === 0) {
      histContainer.innerHTML = '<div class="text-center text-xs py-8" style="color: var(--text-muted);">No recent trades</div>';
  } else {
      let html = `<table class="w-full text-left text-xs" style="color: var(--text-muted);">
        <thead class="text-[10px] font-bold uppercase border-b" style="background: rgba(255,255,255,0.02); border-color: var(--glass-border);">
          <tr><th class="p-3">Asset</th><th class="p-3">Side</th><th class="p-3 text-right">Entry</th><th class="p-3 text-right">Net PnL</th></tr>
        </thead><tbody>`;
      closedTrades.forEach(t => {
          let pnlColor = neutralColor;
          let pnlSign = '';
          if (t.net_pnl > 0) { pnlColor = upColor; pnlSign = '+'; }
          else if (t.net_pnl < 0) { pnlColor = downColor; }

          html += `<tr class="border-b hover:bg-white/5 transition-colors" style="border-color: var(--glass-border);">
              <td class="p-3 font-bold text-[11px]" style="color: var(--text-main);">${t.symbol}</td>
              <td class="p-3"><span class="text-[9px] font-bold px-1.5 py-0.5 rounded" style="color: ${pnlColor}; background: rgba(255,255,255,0.05);">${t.side}</span></td>
              <td class="p-3 text-right font-mono text-[11px]">${fmtPrice(t.entry_price)}</td>
              <td class="p-3 text-right font-mono font-bold text-[11px]" style="color: ${pnlColor};">${pnlSign}${fmt(t.net_pnl)}</td>
          </tr>`;
      });
      html += '</tbody></table>';
      histContainer.innerHTML = html;
  }

  const logContainer = document.getElementById('neural-logs');
  if(decisions.length === 0) {
    logContainer.innerHTML = '<div style="color: var(--text-muted);">No scans yet...</div>';
  } else {
    logContainer.innerHTML = decisions.slice(0, 25).map(d => {
        const time = new Date(d.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        let colorStyle = (d.action.includes('BUY') || d.action.includes('LONG')) ? `color: ${upColor};` : (d.action.includes('SHORT') || d.action.includes('SELL')) ? `color: ${downColor};` : `color: #94a3b8;`;
        return `<div class="mb-1.5 flex gap-2 text-[10px]"><span style="color: var(--text-muted); shrink-0">[${time}]</span> <span class="font-semibold shrink-0" style="color: var(--text-main);">${d.symbol}</span> <span class="shrink-0 font-semibold" style="${colorStyle}">${d.action}</span> <span class="truncate" style="color: var(--text-muted);">${String(d.reason || '').length > 55 ? String(d.reason).substring(0, 55) + '...' : String(d.reason || '')}</span></div>`;
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

@router.post("/api/auto_tune")
async def api_auto_tune(request: Request, symbol: str = "BTCUSDT", strategy: str = "trend"):
    try:
        engine = request.app.state.engine
        db = request.app.state.db
        market = engine.market
        result = await run_auto_tune(db, market, symbol, strategy)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
