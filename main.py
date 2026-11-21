import logging, sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
import uvicorn
import config
from database import Database
from engine import Engine
from telegram_bot import TelegramNotifier
from dashboard import router
from ui import router as ui_router
import security
from login_page import LOGIN_HTML

# INFO إلى stdout (عادي)، والتحذيرات والأخطاء إلى stderr (تظهر حمراء في Railway)
_out=logging.StreamHandler(sys.stdout); _out.addFilter(lambda r: r.levelno<logging.WARNING)
_err=logging.StreamHandler(sys.stderr); _err.setLevel(logging.WARNING)
logging.basicConfig(level=getattr(logging,config.LOG_LEVEL.upper(),logging.INFO),handlers=[_out,_err],
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# روابط طلبات تيليجرام تحتوي توكن البوت: لا نسجّلها أبداً
for _noisy in ("httpx","httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
config.validate_config()
if not config.DASHBOARD_KEY:
    logging.getLogger("security").warning("DASHBOARD_KEY is empty: the dashboard and its control buttons are open to anyone who knows the URL. Set DASHBOARD_KEY in Railway Variables.")

def _client_ip(request: Request):
    return security.client_ip(request.headers.get("x-forwarded-for", ""),
                              request.client.host if request.client else None, config.TRUSTED_PROXY)

def _is_https(request: Request):
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"

@asynccontextmanager
async def lifespan(app:FastAPI):
    db=Database()
    engine=Engine(db)
    telegram=TelegramNotifier(db,engine)
    app.state.db=db; app.state.engine=engine; app.state.telegram=telegram
    engine.notifier=telegram
    storage=db.storage_info()
    if storage["fallback_used"] or storage["on_mount"] is False and storage["path"].startswith("/data"):
        logging.getLogger("storage").warning(
            "Database %s is not on a persistent volume: it will be LOST on redeploy. Mount a Railway volume at /data.",
            storage["path"])
    try:
        await engine.start()
        await telegram.start()
        yield
    finally:
        await telegram.close()
        await engine.stop()
        db.close()

app=FastAPI(title=config.APP_NAME,version=config.APP_VERSION,lifespan=lifespan)
app.include_router(ui_router)   # Dashboard Pro owns "/" and "/pro"; the old dashboard lives on "/legacy"
app.include_router(router)

# --- شاشة تسجيل الدخول الفخمة ---
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return LOGIN_HTML

# --- مسار معالجة تسجيل الدخول ---
@app.post("/api/login")
async def api_login(request: Request, password: str = Form(...)):
    if not config.DASHBOARD_KEY:
        return RedirectResponse("/", status_code=303)

    ip = _client_ip(request)
    if security.is_locked(ip):
        return HTMLResponse("<script>alert('Too many attempts. Try again in 5 minutes.');window.location.href='/login';</script>", status_code=429)

    if security.check_credentials(config.DASHBOARD_KEY, supplied_key=str(password)):
        security.clear_failures(ip)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("dash_key", security.session_token(config.DASHBOARD_KEY), httponly=True, samesite="lax",
                            max_age=30*86400, secure=_is_https(request))
        return response

    security.register_failure(ip)
    return HTMLResponse("""
    <script>
        alert('ACCESS DENIED: Invalid Key');
        window.location.href='/login';
    </script>
    """, status_code=401)

# --- الحارس (Middleware) ---
@app.middleware("http")
async def dashboard_key_guard(request: Request, call_next):
    key=config.DASHBOARD_KEY
    path=request.url.path

    if not key and request.method not in ("GET", "HEAD", "OPTIONS") and path != "/api/login" \
            and not config.ALLOW_INSECURE_DASHBOARD:
        # No DASHBOARD_KEY: the dashboard is read-only. Control actions (pause, close, backtest, auto-tune)
        # need a key, otherwise anyone who finds the URL could drive the simulation.
        return JSONResponse({"detail": "Set DASHBOARD_KEY to enable control actions "
                                       "(or ALLOW_INSECURE_DASHBOARD=true for local use)"}, status_code=403)
    if key and path not in ("/health", "/login", "/api/login"):
        supplied=request.query_params.get("key") or ""
        token=request.cookies.get("dash_key") or ""
        verdict=security.authorize(key, supplied, token, _client_ip(request))
        if verdict=="locked":
            return JSONResponse({"detail":"too many attempts"},status_code=429)
        if verdict!="ok":
            if path.startswith("/api/"):
                return JSONResponse({"detail":"unauthorized"},status_code=401)
            return RedirectResponse(url="/login")
        response=await call_next(request)
        if supplied and security.check_credentials(key, supplied_key=supplied):
            response.set_cookie("dash_key",security.session_token(key),httponly=True,samesite="lax",
                                max_age=30*86400,secure=_is_https(request))
    else:
        response=await call_next(request)

    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    for name,value in security.extra_headers(path, response.headers.get("content-type","")).items():
        response.headers.setdefault(name,value)
    return response

@app.get("/health")
async def health(request: Request):
    """Liveness for Railway. 200 once the engine runs; the body reports data/storage problems without secrets."""
    engine=getattr(request.app.state,"engine",None)
    db=getattr(request.app.state,"db",None)
    ready=bool(engine and engine.running)
    payload={"status":"ok" if ready else "starting","mode":"PAPER SIMULATION","version":config.APP_VERSION}
    if engine:
        st=engine.get_status()
        payload.update({"data_ok":st["data_ok"],"paused":st["paused"],"last_scan":st["last_scan"]})
    if db:
        payload["storage"]=db.storage_info()
    return JSONResponse(payload,status_code=200 if ready else 503)

if __name__=="__main__":
    # access_log=False: the access log would print "?key=<DASHBOARD_KEY>" URLs into the logs
    uvicorn.run(app,host=config.HOST,port=config.PORT,workers=1,access_log=False)
