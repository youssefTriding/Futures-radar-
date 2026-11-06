"""
Futures Radar - Professional Binance USD-M Signal Scanner
Arabic UI • Multi-timeframe • Free to host on Render
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scanner import FuturesScanner

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")

# Global scanner instance
scanner = FuturesScanner()
scheduler = AsyncIOScheduler()

# Paths
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Futures Radar...")
    # First scan immediately
    asyncio.create_task(scanner.run_scan())

    # Schedule recurring scans every 3 minutes
    scheduler.add_job(
        scanner.run_scan,
        trigger=IntervalTrigger(minutes=3),
        id="scan_job",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started (scan every 3 min)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await scanner.close()


app = FastAPI(
    title="رادار الفيوتشر",
    description="نظام إشارات احترافي لعقود بينانس الآجلة",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (if any)
static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main Arabic dashboard"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": scanner.get_status(),
        },
    )


@app.get("/api/signals")
async def get_signals():
    """Return current signals sorted by strength"""
    return {
        "signals": scanner.signals,
        "meta": scanner.get_status(),
    }


@app.get("/api/status")
async def get_status():
    return scanner.get_status()


@app.post("/api/rescan")
async def force_rescan():
    """Manual trigger (protected in production if needed)"""
    if scanner.status == "scanning":
        return JSONResponse(
            {"ok": False, "msg": "المسح جارٍ حالياً، انتظر قليلاً"},
            status_code=429,
        )
    asyncio.create_task(scanner.run_scan())
    return {"ok": True, "msg": "تم بدء المسح"}


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
