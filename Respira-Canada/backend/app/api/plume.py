"""Smoke plume routes. Same three endpoints as the original; inputs renamed to
their Canadian equivalents (fwi, ffmc, frp_mw) and wind now comes from ECCC's
GEM model at the fire location instead of the nearest station."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from app import config, services
from app.clients import cwfis
from app.clients.http import UpstreamError
from app.science.plume import DEFAULT_FFMC, DEFAULT_FWI, cone_polygon, geod, plume_tip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Plume"])

DEFAULT_HOURS = [0.5, 1.0, 2.0]
STATION_HOURS = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 7, 8, 9, 10, 11, 12,
                 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
REQUERY_DISTANCE_KM = 25.0


class PlumeRequest(BaseModel):
    lat: Optional[float] = Field(None, ge=35, le=85)
    lon: Optional[float] = Field(None, ge=-170, le=-50)
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON Polygon of the burning area")
    hours: List[float] = Field(default_factory=lambda: DEFAULT_HOURS.copy())
    wind_speed: Optional[float] = Field(None, ge=0, description="m/s; fetched from GEM if omitted")
    wind_dir_from: Optional[float] = Field(None, ge=0, le=360)
    fwi: Optional[float] = Field(None, ge=0, description="Fire Weather Index; nearest station if omitted")
    ffmc: Optional[float] = Field(None, ge=0, le=101, description="Fine Fuel Moisture Code")
    frp_mw: Optional[float] = Field(None, ge=0, description="Hotspot fire radiative power, MW")
    confidence: Optional[float] = Field(None, ge=0, le=100, description="Detection confidence, %")
    area_m2: Optional[float] = Field(None, ge=0)
    hectares: Optional[float] = Field(None, ge=0, description="Convenience alias for area (agency fire size)")
    station_id: Optional[str] = Field(None, description="Use this station's FWI instead of the nearest")
    emission_multiplier: float = Field(1.0, ge=0.1, le=3.0)
    diffusion_multiplier: float = Field(1.0, ge=0.5, le=3.0)
    loft_multiplier: float = Field(1.0, ge=0.5, le=3.0)
    suppress_small_fires: bool = False
    step_minutes: int = Field(30, ge=10, le=120)
    simulation_mode: str = Field("segment", pattern="^(segment|cumulative_union|cumulative_last)$")
    only_target_frames: bool = False

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, v: List[float]) -> List[float]:
        vv = sorted({float(h) for h in v if h > 0})
        if not vv:
            raise ValueError("at least one positive hour required")
        if len(vv) > 24:
            raise ValueError("too many hours (max 24 values)")
        if vv[-1] > 48:
            raise ValueError("hours must be <= 48")
        return vv


class PlumeFrame(BaseModel):
    hours: float
    geojson: Dict[str, Any]
    meta: Dict[str, Any]


class PlumeResponse(BaseModel):
    frames: List[PlumeFrame]
    source: str
    inputs: Dict[str, Any] = Field(default_factory=dict)


def _resolve_origin(req: PlumeRequest) -> Tuple[float, float, Optional[float]]:
    area = req.area_m2 if req.area_m2 is not None else (req.hectares * 10_000 if req.hectares is not None else None)
    if req.geometry is None:
        if req.lat is None or req.lon is None:
            raise HTTPException(status_code=400, detail="Provide geometry or lat/lon")
        return req.lat, req.lon, area
    try:
        geom = shape(req.geometry)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid geometry: {exc}") from exc
    if geom.is_empty:
        raise HTTPException(status_code=400, detail="Empty geometry")
    c = geom.centroid
    if area is None:
        area = abs(geod.geometry_area_perimeter(geom)[0])
    return c.y, c.x, area


def _fire_weather_inputs(req: PlumeRequest, lat: float, lon: float) -> Dict[str, Any]:
    """Fill FWI/FFMC and wind from live Canadian data where the caller didn't."""
    station = None
    if req.fwi is None or req.ffmc is None or req.wind_speed is None or req.wind_dir_from is None:
        try:
            if req.station_id:
                station = cwfis.get_station(req.station_id, config.get_region("CA"))
            if station is None:
                near = services.nearest_stations(lat, lon, k=1)
                station = near[0] if near else None
        except UpstreamError as exc:
            logger.info("Station lookup for plume failed: %s", exc)

    fwi_vals = (station or {}).get("fwi", {})
    fwi = req.fwi if req.fwi is not None else fwi_vals.get("fwi")
    ffmc = req.ffmc if req.ffmc is not None else fwi_vals.get("ffmc")

    if req.wind_speed is not None and req.wind_dir_from is not None:
        wind = {"speed_m_s": req.wind_speed, "dir_from": req.wind_dir_from, "source": "request"}
    else:
        wind = services.wind_at(lat, lon, station)
        if req.wind_speed is not None:
            wind["speed_m_s"] = req.wind_speed
        if req.wind_dir_from is not None:
            wind["dir_from"] = req.wind_dir_from

    return {
        "fwi": fwi if fwi is not None else DEFAULT_FWI,
        "ffmc": ffmc if ffmc is not None else DEFAULT_FFMC,
        "wind_speed_m_s": round(wind["speed_m_s"], 2),
        "wind_dir_from": round(wind["dir_from"], 1),
        "wind_source": wind["source"],
        "station_id": station["station_id"] if station else None,
        "station_name": station["station_name"] if station else None,
        "fwi_source": "request" if req.fwi is not None else ("CWFIS station" if station else "default"),
    }


@router.post("/plume", response_model=PlumeResponse)
def plume(req: PlumeRequest = Body(...)) -> PlumeResponse:
    lat, lon, area = _resolve_origin(req)
    ctx = _fire_weather_inputs(req, lat, lon)

    frames: List[PlumeFrame] = []
    for h in req.hours:
        res = cone_polygon(
            lat=lat, lon=lon, wind_speed_m_s=ctx["wind_speed_m_s"], wind_dir_from_deg=ctx["wind_dir_from"],
            hours=h, fwi=ctx["fwi"], ffmc=ctx["ffmc"], frp_mw=req.frp_mw, area_m2=area,
            confidence=req.confidence, emission_multiplier=req.emission_multiplier,
            diffusion_multiplier=req.diffusion_multiplier, loft_multiplier=req.loft_multiplier,
            suppress_small_fires=req.suppress_small_fires,
        )
        if res:
            poly, meta = res
            frames.append(PlumeFrame(hours=h, geojson=poly, meta={**meta, **ctx, "hours": h, "area_m2": area}))
    return PlumeResponse(frames=frames, source="approx_cone_v1_ca", inputs={**ctx, "lat": lat, "lon": lon, "area_m2": area})


@router.post("/plume_dynamic", response_model=PlumeResponse)
def plume_dynamic(req: PlumeRequest = Body(...)) -> PlumeResponse:
    """March the plume forward step by step, re-reading wind as it travels."""
    lat, lon, area = _resolve_origin(req)
    ctx = _fire_weather_inputs(req, lat, lon)
    wind_locked = req.wind_speed is not None and req.wind_dir_from is not None

    step_h = req.step_minutes / 60.0
    targets = req.hours
    total_steps = int(math.ceil(targets[-1] / step_h))
    speed, direction = ctx["wind_speed_m_s"], ctx["wind_dir_from"]
    cur_lat, cur_lon = lat, lon
    since_fetch_km = 0.0
    frames: List[PlumeFrame] = []
    segments: List[Any] = []

    for step in range(1, total_steps + 1):
        elapsed = step * step_h
        seg = cone_polygon(
            lat=cur_lat, lon=cur_lon, wind_speed_m_s=speed, wind_dir_from_deg=direction, hours=step_h,
            fwi=ctx["fwi"], ffmc=ctx["ffmc"], frp_mw=req.frp_mw, area_m2=area, confidence=req.confidence,
            emission_multiplier=req.emission_multiplier, diffusion_multiplier=req.diffusion_multiplier,
            loft_multiplier=req.loft_multiplier, suppress_small_fires=req.suppress_small_fires,
        )
        if not seg:
            break
        poly, meta = seg
        is_target = any(abs(elapsed - t) < 1e-6 for t in targets)

        if req.simulation_mode == "cumulative_union":
            segments.append(shape(poly))
            out_poly = mapping(unary_union(segments))
        else:
            out_poly = poly
            if req.simulation_mode == "cumulative_last":
                frames = []

        if not req.only_target_frames or is_target:
            frames.append(PlumeFrame(
                hours=round(elapsed, 3), geojson=out_poly,
                meta={**meta, **ctx, "wind_speed_m_s": round(speed, 2), "wind_dir_from": round(direction, 1),
                      "segment_hours": step_h, "cumulative_hours": round(elapsed, 3), "target_frame": is_target,
                      "simulation_mode": req.simulation_mode, "area_m2": area},
            ))

        tip = plume_tip(meta)
        if tip is None:
            break
        since_fetch_km += cwfis.haversine_km(cur_lat, cur_lon, tip[0], tip[1])
        cur_lat, cur_lon = tip

        if not wind_locked and since_fetch_km > REQUERY_DISTANCE_KM:
            since_fetch_km = 0.0
            w = services.wind_at(cur_lat, cur_lon)
            if w["source"].startswith("ECCC"):
                speed, direction = w["speed_m_s"], w["dir_from"]

        if elapsed >= targets[-1] - 1e-9:
            break

    return PlumeResponse(frames=frames, source="dynamic_cone_v1_ca", inputs={**ctx, "lat": lat, "lon": lon, "area_m2": area})


@router.get("/stations/{station_id}/plume", response_model=PlumeResponse)
def station_plume(
    station_id: str,
    region: Optional[str] = Query(None),
    hours: List[float] = Query(STATION_HOURS),
) -> PlumeResponse:
    """Where smoke would go if a fire started at this station right now."""
    try:
        reg = config.get_region(region)
        station = cwfis.get_station(station_id, reg)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if station is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    lat, lon = station["latitude"], station["longitude"]
    wind = services.wind_at(lat, lon, station)
    fwi = station["fwi"].get("fwi")
    ffmc = station["fwi"].get("ffmc")
    ctx = {
        "station_id": station["station_id"], "station_name": station["station_name"],
        "fwi": fwi if fwi is not None else DEFAULT_FWI, "ffmc": ffmc if ffmc is not None else DEFAULT_FFMC,
        "wind_speed_m_s": round(wind["speed_m_s"], 2), "wind_dir_from": round(wind["dir_from"], 1),
        "wind_source": wind["source"],
    }
    frames = []
    for h in sorted({h for h in hours if h > 0}):
        res = cone_polygon(
            lat=lat, lon=lon, wind_speed_m_s=ctx["wind_speed_m_s"], wind_dir_from_deg=ctx["wind_dir_from"],
            hours=h, fwi=ctx["fwi"], ffmc=ctx["ffmc"], suppress_small_fires=False,
        )
        if res:
            poly, meta = res
            frames.append(PlumeFrame(hours=h, geojson=poly, meta={**meta, **ctx, "hours": h}))
    return PlumeResponse(frames=frames, source="station_cone_v1_ca", inputs={**ctx, "lat": lat, "lon": lon})
