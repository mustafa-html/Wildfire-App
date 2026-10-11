"""Respira Canada — FastAPI entry point."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import air, fire, llm, plume
from app.clients import cwfis
from app.clients.http import UpstreamError

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Respira Canada — Wildfire Risk API",
    description="Fire danger (CWFIS / FWI System), active fires, AQHI, smoke plumes and an assistant for Canada.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(fire.router)
app.include_router(air.router)
app.include_router(plume.router)
app.include_router(llm.router)


@app.get("/")
def root():
    return {"message": "Respira Canada — Wildfire Risk API", "version": app.version, "documentation": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    """Checks that CWFIS answers (uses the smallest region)."""
    status = {"timestamp": datetime.now(timezone.utc).isoformat(), "default_region": config.DEFAULT_REGION,
              "assistant": "gemini" if config.GEMINI_API_KEY else "plain summaries (no GEMINI_API_KEY)"}
    try:
        n = len(cwfis.get_stations(config.get_region("PE")))
        return {**status, "status": "healthy", "cwfis": f"connected ({n} stations in PE)"}
    except UpstreamError as exc:
        return {**status, "status": "degraded", "cwfis": f"unavailable: {exc}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
