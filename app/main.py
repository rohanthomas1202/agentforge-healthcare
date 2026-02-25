"""FastAPI application entry point for AgentForge Healthcare."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.fhir_client import fhir_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup: verify FHIR connection
    try:
        result = await fhir_client.get("metadata")
        print(f"[startup] Connected to OpenEMR FHIR API (v{result.get('fhirVersion', '?')})")
    except Exception as e:
        print(f"[startup] WARNING: Could not connect to OpenEMR FHIR API: {e}")
        print("[startup] Agent will still start but FHIR tools will fail until OpenEMR is reachable.")

    yield

    # Shutdown: close HTTP client
    await fhir_client.close()


app = FastAPI(
    title="AgentForge Healthcare",
    description="AI-powered healthcare agent built on OpenEMR FHIR R4 APIs",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(router, prefix="/api")
