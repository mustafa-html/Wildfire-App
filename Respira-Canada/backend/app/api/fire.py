"""Fire danger routes (Canadian equivalents of the original FEMS/NFDRS routes).

Original route                     ->  This version
/api/stations/ny                   ->  /api/stations?region=AB
/api/weather/observations          ->  /api/weather/observations
/api/nfdrs/observations            ->  /api/fwi/observations
/api/fire-danger/percentiles       ->  (dropped: no CWFIS equivalent)
/api/fire-risk/calculate           ->  /api/fire-risk/calculate  (FWI based)
/api/fire-risk/assessment          ->  /api/fire-risk/assessment?region=AB
/api/graphql/query                 ->  (dropped: FEMS-specific)
new                                ->  /api/regions, /api/fires/active, /api/fires/hotspots
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import config, services
from app.clients import cwfis
from app.clients.http import UpstreamError
from app.science.danger import INTERPRETATION, fwi_danger_class, fwi_to_score
from app.science.fwi import complete_indices

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Fire danger"])


def _region(code: Optional[str]):
    try:
        return config.get_region(code)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _ids(station_ids: Optional[str]) -> List[str]:
    return [s.strip() for s in (station_ids or "").split(",") if s.strip()]


def _upstream(exc: Exception) -> HTTPException:
    logger.error("Upstream failure: %s", exc)
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/regions")
def list_regions():
    return {"default": config.DEFAULT_REGION, "regions": [r.as_dict() for r in config.REGIONS.values()]}


@router.get("/stations")
def get_stations(region: Optional[str] = Query(None, description="Province/territory code, e.g. AB, BC, ON, or CA")):
    """Fire-weather stations in a region, with their latest noon observation."""
    try:
        stations = cwfis.get_stations(_region(region))
    except UpstreamError as exc:
        raise _upstream(exc)
    return [
        {k: s[k] for k in ("station_id", "station_name", "latitude", "longitude", "elevation", "agency", "observation_time")}
        for s in stations
    ]


@router.get("/weather/observations")
def get_weather_observations(
    station_ids: str = Query(..., description="Comma-separated station IDs"),
    region: Optional[str] = Query(None),
):
    """Latest local-noon weather (°C, %, km/h, mm). CWFIS publishes one
    observation per station per day, so there is no hours_back parameter."""
    ids = set(_ids(station_ids))
    try:
        stations = cwfis.get_stations(_region(region))
    except UpstreamError as exc:
        raise _upstream(exc)
    data = [
        {"station_id": s["station_id"], "station_name": s["station_name"], "latitude": s["latitude"],
         "longitude": s["longitude"], "observation_time": s["observation_time"], **s["weather"]}
        for s in stations if s["station_id"] in ids
    ]
    return {"station_ids": station_ids, "count": len(data), "units": {"temperature": "°C", "wind_speed": "km/h", "precip_24h": "mm"}, "data": data}


@router.get("/fwi/observations")
def get_fwi_observations(
    station_ids: str = Query(..., description="Comma-separated station IDs"),
    region: Optional[str] = Query(None),
):
    """Canadian Forest Fire Weather Index System values for each station."""
    ids = set(_ids(station_ids))
    try:
        stations = cwfis.get_stations(_region(region))
    except UpstreamError as exc:
        raise _upstream(exc)
    data = [
        {"station_id": s["station_id"], "station_name": s["station_name"], "observation_time": s["observation_time"],
         **s["fwi"], "danger_class": fwi_danger_class(s["fwi"].get("fwi"))}
        for s in stations if s["station_id"] in ids
    ]
    return {"station_ids": station_ids, "count": len(data), "data": data}


class RiskCalcRequest(BaseModel):
    fwi_data: dict = Field(..., description="Any of ffmc, dmc, dc, isi, bui, fwi")
    weather_data: dict = Field(default_factory=dict, description="wind_speed in km/h (used to derive ISI)")


@router.post("/fire-risk/calculate")
def calculate_fire_risk(body: RiskCalcRequest):
    f, w = body.fwi_data, body.weather_data
    idx = complete_indices(
        ffmc=f.get("ffmc"), dmc=f.get("dmc"), dc=f.get("dc"), wind=w.get("wind_speed"),
        isi=f.get("isi"), bui=f.get("bui"), fwi=f.get("fwi"),
    )
    if idx["fwi"] is None:
        raise HTTPException(status_code=400, detail="Provide fwi, or isi+bui, or ffmc+dmc+dc with weather_data.wind_speed")
    level = fwi_danger_class(idx["fwi"])
    return {
        "indices": {k: (round(v, 1) if v is not None else None) for k, v in idx.items()},
        "risk_score": fwi_to_score(idx["fwi"]),
        "risk_level": level,
        "interpretation": INTERPRETATION[level],
    }


@router.get("/fire-risk/assessment")
def get_fire_risk_assessment(
    region: Optional[str] = Query(None, description="Province/territory code; defaults to DEFAULT_REGION"),
    station_ids: Optional[str] = Query(None, description="Optional comma-separated subset of stations"),
    limit: int = Query(2000, ge=1, le=5000),
):
    """Fire danger for every station in a region, highest first."""
    try:
        return services.region_assessment(_region(region), _ids(station_ids) or None, limit)
    except UpstreamError as exc:
        raise _upstream(exc)


@router.get("/fires/active")
def get_active_fires(
    region: Optional[str] = Query(None),
    include_out: bool = Query(False, description="Include fires declared out"),
):
    """Wildfires reported by provincial/territorial agencies (via CIFFC)."""
    try:
        fires = cwfis.get_active_fires(_region(region), include_out=include_out)
    except UpstreamError as exc:
        raise _upstream(exc)
    by_stage: dict = {}
    for f in fires:
        by_stage[f["stage_of_control"]] = by_stage.get(f["stage_of_control"], 0) + 1
    return {
        "count": len(fires),
        "total_hectares": round(sum(f["hectares"] or 0 for f in fires), 1),
        "by_stage": by_stage,
        "fires": fires,
        "source": "Natural Resources Canada, CWFIS / CIFFC",
    }


@router.get("/fires/hotspots")
def get_hotspots(region: Optional[str] = Query(None), limit: int = Query(3000, ge=1, le=20000)):
    """Satellite-detected heat sources in the last 24 hours."""
    try:
        hotspots = cwfis.get_hotspots(_region(region), limit=limit)
    except UpstreamError as exc:
        raise _upstream(exc)
    return {"count": len(hotspots), "hotspots": hotspots, "source": "Natural Resources Canada, CWFIS"}
