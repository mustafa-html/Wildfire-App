"""Current 10 m wind at any point, from Environment Canada's GEM model.

CWFIS station weather is a once-a-day local-noon observation, which is right
for fire danger but stale for a smoke plume at 9 p.m. Open-Meteo serves ECCC's
GEM model output without an API key, so plumes use the current modelled wind
at the fire itself and fall back to the nearest station's noon wind.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from app import config
from app.clients.http import UpstreamError, get_json

logger = logging.getLogger(__name__)


def current_wind(lat: float, lon: float) -> Optional[Tuple[float, float]]:
    """Return (speed m/s, direction degrees-from) or None if unavailable."""
    params = {
        "latitude": round(lat, 3),
        "longitude": round(lon, 3),
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms",
        "models": config.OPEN_METEO_MODEL,
    }
    try:
        data = get_json(config.OPEN_METEO_URL, params)
    except UpstreamError as exc:
        logger.info("GEM wind unavailable at %.3f,%.3f: %s", lat, lon, exc)
        return None
    current = (data or {}).get("current") or {}
    speed = current.get("wind_speed_10m")
    direction = current.get("wind_direction_10m")
    if speed is None or direction is None:
        return None
    return float(speed), float(direction)
