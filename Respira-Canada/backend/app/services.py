"""Business logic shared by the HTTP routes, the chat assistant and the CLI."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import config
from app.clients import cwfis, eccc, openmeteo
from app.clients.http import UpstreamError
from app.config import Region
from app.science.danger import INTERPRETATION, fwi_danger_class, fwi_to_score, score_to_level
from app.science.plume import KMH_PER_MS

logger = logging.getLogger(__name__)


def assess_station(station: Dict[str, Any]) -> Dict[str, Any]:
    fwi = station["fwi"].get("fwi")
    score = fwi_to_score(fwi)
    level = fwi_danger_class(fwi)
    return {
        "station_id": station["station_id"],
        "station_name": station["station_name"],
        "latitude": station["latitude"],
        "longitude": station["longitude"],
        "observation_time": station.get("observation_time"),
        "risk_score": score,
        "risk_level": level,
        "interpretation": INTERPRETATION.get(level or "", "No FWI reported (station may be in seasonal shutdown)."),
        "weather_conditions": station["weather"],
        "fire_indices": station["fwi"],
        **({"distance_km": station["distance_km"]} if "distance_km" in station else {}),
    }


def region_assessment(region: Region, station_ids: Optional[List[str]] = None, limit: int = 2000) -> Dict[str, Any]:
    stations = cwfis.get_stations(region)
    if station_ids:
        wanted = {s.strip() for s in station_ids if s.strip()}
        stations = [s for s in stations if s["station_id"] in wanted]

    assessments = [assess_station(s) for s in stations]
    assessments.sort(key=lambda a: a["risk_score"] if a["risk_score"] is not None else -1, reverse=True)
    assessments = assessments[:limit]
    scored = [a for a in assessments if a["risk_score"] is not None]
    high = [a for a in scored if a["risk_score"] >= 40]
    average = sum(a["risk_score"] for a in scored) / len(scored) if scored else None

    return {
        "region": region.as_dict(),
        "assessment_time": datetime.now(timezone.utc).isoformat(),
        "total_stations": len(assessments),
        "reporting_fwi": len(scored),
        "high_risk_count": len(high),
        "summary": {
            "highest_risk": scored[0] if scored else None,
            "average_risk": round(average, 2) if average is not None else 0.0,
            "average_level": score_to_level(average),
        },
        "assessments": assessments,
        "source": "Natural Resources Canada, CWFIS (firewx_stns_current)",
    }


def _probe_region(lat: float, lon: float, pad_lat: float = 2.0, pad_lon: float = 3.0) -> Region:
    # Snap to whole degrees so nearby lookups share a cached upstream response.
    s, n = math.floor(lat - pad_lat), math.ceil(lat + pad_lat)
    w, e = math.floor(lon - pad_lon), math.ceil(lon + pad_lon)
    return Region("probe", "Nearby", (s, w, n, e), (lat, lon), 7)


def nearest_stations(lat: float, lon: float, *, k: int = 5, require_fwi: bool = True) -> List[Dict[str, Any]]:
    stations = cwfis.get_stations(_probe_region(lat, lon))
    ranked = cwfis.nearest(lat, lon, stations, require_fwi=require_fwi, k=k)
    if not ranked and require_fwi:
        ranked = cwfis.nearest(lat, lon, stations, require_fwi=False, k=k)
    return ranked


def fire_risk_at(lat: float, lon: float) -> Dict[str, Any]:
    """Fire danger from the nearest station that is reporting FWI."""
    try:
        candidates = nearest_stations(lat, lon, k=3)
    except UpstreamError as exc:
        return {"error": f"CWFIS is unavailable: {exc}"}
    if not candidates:
        return {"error": "No fire-weather stations found within about 300 km."}
    return assess_station(candidates[0])


def fires_near(lat: float, lon: float, *, radius_km: float = 150.0, k: int = 5) -> List[Dict[str, Any]]:
    try:
        fires = cwfis.get_active_fires(_probe_region(lat, lon, pad_lat=2.5, pad_lon=4.0))
    except UpstreamError as exc:
        logger.info("Active fires unavailable: %s", exc)
        return []
    ranked = cwfis.nearest(lat, lon, fires, k=50)
    return [f for f in ranked if f["distance_km"] <= radius_km][:k]


def location_context(lat: float, lon: float, name: Optional[str] = None) -> Dict[str, Any]:
    """Everything the chat assistant needs to know about a place."""
    return {
        "location": {"latitude": lat, "longitude": lon, "name": name or f"{lat:.3f}, {lon:.3f}"},
        "fire_risk": fire_risk_at(lat, lon),
        "air_quality": eccc.nearest_aqhi(lat, lon),
        "nearby_fires": fires_near(lat, lon),
    }


def wind_at(lat: float, lon: float, fallback_station: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Current wind for plumes: GEM model first, then the station's noon obs."""
    gem = openmeteo.current_wind(lat, lon)
    if gem:
        return {"speed_m_s": gem[0], "dir_from": gem[1], "source": f"ECCC GEM ({config.OPEN_METEO_MODEL})"}
    if fallback_station:
        w = fallback_station.get("weather") or {}
        if w.get("wind_speed") is not None:
            return {
                "speed_m_s": w["wind_speed"] / KMH_PER_MS,
                "dir_from": w.get("wind_direction") if w.get("wind_direction") is not None else 270.0,
                "source": f"CWFIS noon obs ({fallback_station['station_name']})",
            }
    return {"speed_m_s": 2.0, "dir_from": 270.0, "source": "default (no wind data)"}
