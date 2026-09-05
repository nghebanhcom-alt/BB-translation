from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import download, glossary, jobs, settings, upload
from src.api.websocket import router as websocket_router
from src.models.database import init_db

_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(title="BB-Translation", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(jobs.batches_router, prefix="/api/batches", tags=["batches"])
app.include_router(jobs.estimate_router, prefix="/api/estimate", tags=["estimate"])
app.include_router(download.router, prefix="/api/jobs", tags=["download"])
app.include_router(glossary.router, prefix="/api/glossary", tags=["glossary"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(websocket_router, tags=["websocket"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Static frontend (Architecture.md section 1: HTML + Alpine.js + Tailwind CDN,
# no build step) — mounted last so it never shadows the /api/* or /health
# routes above (StaticFiles only serves what's under `web/`, but explicit
# ordering keeps intent obvious).
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
