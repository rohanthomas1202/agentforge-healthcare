"""FastAPI application entry point for AgentForge Healthcare."""

import logging
import time as _time
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import setup_logging

# Initialize structured logging BEFORE other app imports
setup_logging()

logger = logging.getLogger(__name__)

from app.api.routes import health_router, router  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import init_db  # noqa: E402
from app.fhir_client import fhir_client  # noqa: E402


# ── Startup validation ───────────────────────────────────────────────────────


def _validate_startup_settings() -> None:
    """Fail fast if critical config is missing."""
    if not settings.anthropic_api_key and not settings.openai_api_key:
        raise RuntimeError(
            "No LLM API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
        )
    if not settings.openemr_username:
        logger.warning("OPENEMR_USERNAME is empty — FHIR tools will not authenticate")
    if not settings.api_keys:
        logger.warning("API_KEYS is empty — API authentication is DISABLED")


# ── Request logging middleware ───────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, latency, and client IP."""

    async def dispatch(self, request: Request, call_next):
        start = _time.time()
        response = await call_next(request)
        latency_ms = (_time.time() - start) * 1000

        client_ip = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else "unknown"
        )

        logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 1),
                "client_ip": client_ip,
            },
        )
        return response


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    _validate_startup_settings()

    # Initialize SQLite database
    init_db()
    logger.info("SQLite database initialized")

    # Startup: verify FHIR connection
    try:
        result = await fhir_client.get("metadata")
        logger.info(
            "Connected to OpenEMR FHIR API (v%s)",
            result.get("fhirVersion", "?"),
        )
    except Exception as e:
        logger.warning(
            "Could not connect to OpenEMR FHIR API: %s. "
            "Agent will still start but FHIR tools will fail until OpenEMR is reachable.",
            e,
        )

    yield

    # Shutdown: close HTTP client
    await fhir_client.close()


# ── App ──────────────────────────────────────────────────────────────────────

# Disable docs in production
_is_production = settings.environment.lower() == "production"

app = FastAPI(
    title="AgentForge Healthcare",
    description="AI-powered healthcare agent built on OpenEMR FHIR R4 APIs",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# Rate limiting
from app.api.routes import limiter  # noqa: E402

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — lock down origins
_allowed_origins = [
    o.strip() for o in settings.allowed_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Mount routers
app.include_router(health_router, prefix="/api")  # Unauthenticated health checks
app.include_router(router, prefix="/api")          # Authenticated endpoints

# Mount new frontend as static files (must be last — catches all non-API routes)
_frontend_v2_dir = Path(__file__).resolve().parent.parent / "frontend-v2"
if _frontend_v2_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_v2_dir), html=True), name="frontend")
