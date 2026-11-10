"""FastAPI dashboard API; no exchange credentials or live trading controls."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
router=APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI QUANT X · Paper Simulation</title>
<style>
body{font:16px system-ui;background:#101827;color:#e5edf7;margin:0;padding:24px}
main{max-width:1050px;margin:auto}h1{margin-bottom:4px}.tag{color:#9bd5b0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
article{background:#1c293b;border:1px solid #33445c;border-radius:12px;padding:16px}
small{color:#a9b8ca}pre{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><main><h1>AI QUANT X</h1><p class="tag">PAPER SIMULATION · No real orders are placed</p>
<section class="grid"><article><small>Virtual equity</small><h2 id="equity">—</h2></article>
<article><small>Cash balance</small><h2 id="cash">—</h2></article>
<article><small>Unrealized PnL</small><h2 id="unrealized">—</h2></article>
<article><small>Realized PnL</small><h2 id="realized">—</h2></article>
<article><small>Aggregate open risk / cap</small><h2 id="risk">—</h2></article>
<article><small>Open positions</small><h2 id="count">—</h2></article></section>
<h2>Open virtual positions</h2><article><pre id="positions">Loading…</pre></article>
<h2>Recent decisions</h2><article><pre id="decisions">Loading…</pre></article>
<p><small>Refreshes automatically. Results are simulated and do not predict future performance.</small></p>
</main><script>
async function load(){
 try{
  const [p,r,ps,ds]=await Promise.all(['/api/portfolio','/api/risk','/api/positions','/api/decisions'].map(x=>fetch(x).then(y=>y.json())));
  document.getElementById('equity').textContent=Number(p.equity).toFixed(2)+' USDT';
  document.getElementById('cash').textContent=Number(p.cash_balance).toFixed(2)+' USDT';
  document.getElementById('unrealized').textContent=Number(p.unrealized_pnl).toFixed(2)+' USDT';
  document.getElementById('realized').textContent=Number(p.realized_pnl).toFixed(2)+' USDT';
  document.getElementById('risk').textContent=Number(r.open_risk).toFixed(2)+' / '+Number(r.risk_cap).toFixed(2)+' USDT';
  document.getElementById('count').textContent=p.open_count;
  document.getElementById('positions').textContent=JSON.stringify(ps,null,2);
  document.getElementById('decisions').textContent=JSON.stringify(ds.slice(0,15),null,2);
 }catch(e){document.getElementById('positions').textContent='Dashboard API unavailable: '+e}
}
load();setInterval(load,15000);
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
