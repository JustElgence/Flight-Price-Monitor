"""FlyMon backend entrypoint."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import guard, router as auth_router
from .config import BASE_DIR
from .db import init_db
from .routes import router
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="FlyMon", version="0.1.0", docs_url=None, redoc_url=None)
app.include_router(auth_router)
app.include_router(router)

FRONTEND_DIR = BASE_DIR.parent / "frontend"
app.mount("/vendor", StaticFiles(directory=FRONTEND_DIR / "vendor"), name="vendor")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    block = guard(request)
    if block is not None:
        return block
    return await call_next(request)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()
