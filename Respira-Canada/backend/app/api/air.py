"""Air Quality Health Index routes (new — the original only planned an AQI feature)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import config
from app.clients import eccc
from app.clients.http import UpstreamError

router = APIRouter(prefix="/api/air", tags=["Air quality"])


@router.get("/aqhi")
def aqhi_near(
    lat: float = Query(..., ge=35, le=85),
    lon: float = Query(..., ge=-170, le=-50),
    max_km: float = Query(150, gt=0, le=1000),
):
    """Latest AQHI at the nearest reporting community, plus its forecast."""
    result = eccc.nearest_aqhi(lat, lon, max_km=max_km)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No AQHI community reporting within {max_km:.0f} km")
    return result


@router.get("/aqhi/observations")
def aqhi_observations(region: Optional[str] = Query(None)):
    """Latest AQHI for every reporting community in a region."""
    try:
        reg = config.get_region(region)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        obs = eccc.get_observations(reg)
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(obs), "observations": obs, "source": "Environment and Climate Change Canada"}
