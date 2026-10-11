"""Environment and Climate Change Canada — MSC GeoMet OGC API.

Provides the Air Quality Health Index (AQHI), Canada's equivalent of the US
AQI the original app planned to show. Observations are hourly; forecasts are
issued twice a day for roughly the next 48 hours.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app import config
from app.clients.cwfis import haversine_km
from app.clients.http import UpstreamError, get_json
from app.config import Region
from app.science.danger import AQHI_ADVICE, aqhi_category

logger = logging.getLogger(__name__)

OBS_COLLECTION = "aqhi-observations-realtime"
FCST_COLLECTION = "aqhi-forecasts-realtime"


def _items(collection: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{config.ECCC_OGC_API_URL}/collections/{collection}/items"
    data = get_json(url, {"f": "json", **params})
    if not isinstance(data, dict):
        raise UpstreamError(f"Unexpected response from {collection}")
    return data.get("features") or []


def _point(feature: Dict[str, Any]) -> Optional[tuple]:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    return None


def _aqhi_value(value: Any) -> Optional[float]:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def normalise_observation(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = feature.get("properties") or {}
    pt = _point(feature)
    aqhi = _aqhi_value(p.get("aqhi"))
    if pt is None or aqhi is None:
        return None
    category = aqhi_category(aqhi)
    return {
        "location_id": p.get("location_id"),
        "location_name": p.get("location_name_en") or p.get("location_name_fr") or p.get("location_id"),
        "latitude": pt[0],
        "longitude": pt[1],
        "aqhi": aqhi,
        "category": category,
        "advice": AQHI_ADVICE.get(category or "", ""),
        "observed_at": p.get("observation_datetime"),
    }


def get_observations(region: Region, *, hours_back: int = 6) -> List[Dict[str, Any]]:
    s, w, n, e = region.bbox
    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    features = _items(
        OBS_COLLECTION,
        {
            "bbox": f"{w},{s},{e},{n}",
            "datetime": f"{since}/..",
            "sortby": "-observation_datetime",
            "limit": 2000,
        },
    )
    latest: Dict[str, Dict[str, Any]] = {}
    for f in features:
        obs = normalise_observation(f)
        if not obs:
            continue
        key = obs["location_id"] or f"{obs['latitude']},{obs['longitude']}"
        prev = latest.get(key)
        if prev is None or (obs["observed_at"] or "") > (prev["observed_at"] or ""):
            latest[key] = obs
    return sorted(latest.values(), key=lambda o: -(o["aqhi"] or 0))


def get_forecast(location_id: str) -> List[Dict[str, Any]]:
    features = _items(
        FCST_COLLECTION,
        {"location_id": location_id, "sortby": "-publication_datetime", "limit": 200},
    )
    if not features:
        return []
    newest = max((f.get("properties") or {}).get("publication_datetime") or "" for f in features)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for f in features:
        p = f.get("properties") or {}
        if (p.get("publication_datetime") or "") != newest:
            continue
        if (p.get("forecast_datetime") or "") < now_iso:
            continue
        aqhi = _aqhi_value(p.get("aqhi"))
        out.append(
            {
                "forecast_for": p.get("forecast_datetime"),
                "label": p.get("forecast_datetime_text_en"),
                "aqhi": aqhi,
                "category": aqhi_category(aqhi),
            }
        )
    out.sort(key=lambda x: x["forecast_for"] or "")
    return out


def nearest_aqhi(lat: float, lon: float, *, max_km: float = 150.0) -> Optional[Dict[str, Any]]:
    """Latest AQHI reading nearest to a point, with the current forecast."""
    probe = Region("probe", "probe", (lat - 2.0, lon - 3.0, lat + 2.0, lon + 3.0), (lat, lon), 7)
    try:
        observations = get_observations(probe)
    except UpstreamError as exc:
        logger.warning("AQHI lookup failed: %s", exc)
        return None
    if not observations:
        return None
    for obs in observations:
        obs["distance_km"] = round(haversine_km(lat, lon, obs["latitude"], obs["longitude"]), 1)
    best = min(observations, key=lambda o: o["distance_km"])
    if best["distance_km"] > max_km:
        return None
    forecast: List[Dict[str, Any]] = []
    if best.get("location_id"):
        try:
            forecast = get_forecast(best["location_id"])
        except UpstreamError as exc:
            logger.info("AQHI forecast unavailable for %s: %s", best["location_id"], exc)
    return {**best, "forecast": forecast}
