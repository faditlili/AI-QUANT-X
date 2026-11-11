import hmac, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import config
from database import Database
from engine import Engine
from telegram_bot import TelegramNotifier
from dashboard import router

logging.basicConfig(level=getattr(logging,config.LOG_LEVEL.upper(),logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
config.validate_config()

@asynccontextmanager
async def lifespan(app:FastAPI):
    db=Database()
    engine=Engine(db)
    telegram=TelegramNotifier(db,engine)
    app.state.db=db; app.state.engine=engine; app.state.telegram=telegram
    engine.notifier=telegram
    try:
        await engine.start()
        await telegram.start()
        yield
    finally:
        await telegram.close()
        await engine.stop()
        db.close()

app=FastAPI(title=config.APP_NAME,version=config.APP_VERSION,lifespan=lifespan)
app.include_router(router)

@app.middleware("http")
async def dashboard_key_guard(request: Request, call_next):
    key=config.DASHBOARD_KEY
    if not key or request.url.path=="/health":
        return await call_next(request)
    supplied=request.query_params.get("key") or request.cookies.get("dash_key") or ""
    if not hmac.compare_digest(supplied.encode(),key.encode()):
        return JSONResponse({"detail":"unauthorized"},status_code=401)
    response=await call_next(request)
    if request.query_params.get("key"):
        response.set_cookie("dash_key",key,httponly=True,samesite="lax",max_age=30*86400,
                            secure=request.headers.get("x-forwarded-proto")=="https")
    return response

@app.get("/health")
async def health(request: Request):
    engine=getattr(request.app.state,"engine",None)
    ready=bool(engine and engine.running)
    payload={"status":"ok" if ready else "starting","mode":"PAPER SIMULATION"}
    return JSONResponse(payload,status_code=200 if ready else 503)

if __name__=="__main__":
    uvicorn.run(app,host=config.HOST,port=config.PORT,workers=1)
