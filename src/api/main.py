import logging
import sys
import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import download, glossary, jobs, settings, upload
from src.api.websocket import router as websocket_router
from src.core.config import get_settings
from src.core.job_recovery import fail_orphaned_jobs
from src.models.database import get_session_factory, init_db

_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT_PATH = _PROJECT_ROOT / "pyproject.toml"


def _configure_logging() -> None:
    """Bug #6 P0 (Architecture.md "Final Decision" V6, task P0): every
    `logger.warning(exc_info=True)` in best-effort branches across `src/`
    (e.g. `overlay_rotated_text()`'s swallowed exception,
    `job_orchestrator.py:533-539`) was silently discarded in production —
    `logging.getLogger("src.*")` had NO handler configured anywhere, and only
    uvicorn's own access log ever reached stdout (QA Vong 6 muc 8, verified
    by experiment: a real job failure logged nothing beyond the HTTP access
    line). `Settings.log_level` existed in config.py already but nothing
    ever read it.

    Attaches a handler to the `"src"` logger specifically (the common parent
    of every `logging.getLogger(__name__)` call under `src/`, since Python
    module names there all start with `src.`) rather than the root logger —
    this leaves uvicorn's own logging config (`uvicorn`/`uvicorn.access`
    loggers) untouched and avoids double-configuring third-party library
    loggers that also attach to root.
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    app_logger = logging.getLogger("src")
    app_logger.setLevel(level)

    if any(isinstance(h, logging.StreamHandler) for h in app_logger.handlers):
        # Uvicorn's `--reload` re-imports this module per worker restart —
        # avoid stacking duplicate handlers (duplicate log lines) each time.
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    # Explicit `False` (not just relying on `logging`'s own default of True):
    # if this module is ever re-imported with the root logger ALSO holding a
    # handler (e.g. a future `logging.basicConfig()` call elsewhere), this
    # stops every `src.*` log line from being emitted twice.
    app_logger.propagate = False


_configure_logging()


def _read_app_version() -> str:
    """GET /api/version (US moi 2026-09-06): doc truc tiep `pyproject.toml`
    o runtime thay vi hardcode/import metadata, vi app nay chay tu source
    (khong `pip install`), nen `importlib.metadata.version()` khong dam bao
    tim thay package da cai. `tomllib` la stdlib tu Python 3.11+ (pyproject.toml
    yeu cau requires-python >=3.12) nen khong can them dependency moi.
    """
    try:
        with _PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    # Bug #EPUB-3 (Architecture.md §E3): phai chay SAU init_db() (bang/cot
    # phai ton tai truoc khi query) va TRUOC yield (xong truoc khi nhan
    # request dau tien -> khong co race voi job moi tao).
    async with get_session_factory()() as session:
        await fail_orphaned_jobs(session)
    yield


app = FastAPI(title="BB-Translation", version=_read_app_version(), lifespan=lifespan)

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


@app.get("/api/version")
async def get_version() -> dict[str, str]:
    return {"version": _read_app_version()}


# Static frontend (Architecture.md section 1: HTML + Alpine.js + Tailwind CDN,
# no build step) — mounted last so it never shadows the /api/* or /health
# routes above (StaticFiles only serves what's under `web/`, but explicit
# ordering keeps intent obvious).
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
