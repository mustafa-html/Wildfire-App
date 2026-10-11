"""Approximate wind-driven smoke plume (cone) model.

Same geometry as the original ``approx_cone_v1``: a wedge downwind of the fire
whose length grows with wind speed x time and whose width grows with sqrt(t).
The fire-intensity inputs are swapped for their Canadian equivalents:

=====================  ===============================================
Original (NFDRS)       Canadian replacement
=====================  ===============================================
Burning Index (0-200)  Fire Weather Index (FWI), normalised on 0-50
1-hour fuel moisture   Fine fuel moisture content derived from FFMC
VIIRS FRP              CWFIS hotspot fire radiative power (MW)
=====================  ===============================================

This is a visual heuristic, not a dispersion model. For operational smoke
forecasts Canada has ECCC's FireWork system, which the frontend can overlay.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from pyproj import Geod
from shapely.geometry import Polygon, mapping

from app.science.fwi import ffmc_to_moisture

geod = Geod(ellps="WGS84")

DEFAULT_FWI = 10.0
DEFAULT_FFMC = 85.0
KMH_PER_MS = 3.6


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_emission_factor(
    *,
    fwi: Optional[float] = None,
    ffmc: Optional[float] = None,
    frp_mw: Optional[float] = None,
    area_m2: Optional[float] = None,
    emission_multiplier: float = 1.0,
) -> Tuple[float, float, float, float, float]:
    intensity_norm = clamp((fwi if fwi is not None else DEFAULT_FWI) / 50.0, 0.0, 1.0)
    fine_moisture = ffmc_to_moisture(ffmc if ffmc is not None else DEFAULT_FFMC)
    dryness_norm = 1.0 - clamp(fine_moisture / 100.0, 0.0, 1.0)
    frp_norm = clamp((frp_mw or 0.0) / 500.0, 0.0, 1.0)
    area_norm = clamp((area_m2 or 0.0) / 1_000_000.0, 0.0, 1.0)

    w_int, w_dry, w_frp, w_area = 0.4, 0.25, 0.25, 0.1
    raw = w_int * intensity_norm + w_dry * dryness_norm + w_frp * frp_norm + w_area * area_norm
    emission = max(0.05, raw) * emission_multiplier
    return emission, intensity_norm, dryness_norm, frp_norm, area_norm


def compute_loft(intensity_norm: float, frp_norm: float, loft_multiplier: float = 1.0) -> float:
    loft = 0.5 + 1.5 * (0.6 * frp_norm + 0.4 * intensity_norm)
    return clamp(loft * loft_multiplier, 0.3, 3.0)


def should_suppress(
    *,
    emission: float,
    fwi: Optional[float],
    frp_mw: Optional[float],
    area_m2: Optional[float],
    confidence: Optional[float],
) -> bool:
    """Hide plumes for small, low-confidence detections in mild weather."""
    conf = confidence or 0.0
    return (emission < 0.08 and (frp_mw or 0) < 30 and (area_m2 or 0) < 10_000 and conf < 40) or (
        conf < 40 and (fwi or 0) < 10 and (area_m2 or 0) < 5_000
    )


def cone_polygon(
    *,
    lat: float,
    lon: float,
    wind_speed_m_s: float,
    wind_dir_from_deg: float,
    hours: float,
    fwi: Optional[float] = None,
    ffmc: Optional[float] = None,
    frp_mw: Optional[float] = None,
    area_m2: Optional[float] = None,
    confidence: Optional[float] = None,
    emission_multiplier: float = 1.0,
    diffusion_multiplier: float = 1.0,
    loft_multiplier: float = 1.0,
    suppress_small_fires: bool = True,
    n_segs: int = 40,
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    emission, intensity_norm, dryness_norm, frp_norm, area_norm = compute_emission_factor(
        fwi=fwi, ffmc=ffmc, frp_mw=frp_mw, area_m2=area_m2, emission_multiplier=emission_multiplier
    )
    loft = compute_loft(intensity_norm, frp_norm, loft_multiplier)

    if suppress_small_fires and should_suppress(
        emission=emission, fwi=fwi, frp_mw=frp_mw, area_m2=area_m2, confidence=confidence
    ):
        return None

    base_distance_m = max(wind_speed_m_s, 0.0) * 3600.0 * hours
    plume_length_m = max(200.0, base_distance_m * (0.8 + 1.2 * emission) * loft)
    base_width_m = max(100.0, plume_length_m * 0.03)
    plume_width_m = base_width_m * (1.0 + 2.5 * math.sqrt(hours) * (0.6 + 0.4 * dryness_norm))
    plume_width_m *= diffusion_multiplier

    bearing_to = (wind_dir_from_deg + 180.0) % 360.0
    half_angle = clamp(math.degrees(math.atan((plume_width_m / 2.0) / max(plume_length_m, 1.0))), 2.0, 40.0)

    # Start at i=1: geod.fwd with r=0 returns the origin with float noise, which
    # made a zero-width spike and an invalid (dropped) polygon at some locations.
    pts: List[Tuple[float, float]] = [(lon, lat)]
    for i in range(1, n_segs + 1):
        frac = i / n_segs
        angle = bearing_to - half_angle + (2 * half_angle) * frac
        r = plume_length_m * (frac ** 0.9)
        dest_lon, dest_lat, _ = geod.fwd(lon, lat, angle, r)
        pts.append((dest_lon, dest_lat))
    pts.append((lon, lat))

    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None

    # Centreline point the dynamic model marches to next (same point the
    # original read from the middle of the arc).
    tip_lon, tip_lat, _ = geod.fwd(lon, lat, bearing_to, plume_length_m * 0.5 ** 0.9)

    return mapping(poly), {
        "tip_lat": round(tip_lat, 6),
        "tip_lon": round(tip_lon, 6),
        "plume_length_m": round(plume_length_m, 1),
        "plume_width_m": round(plume_width_m, 1),
        "emission_factor": round(emission, 4),
        "loft": round(loft, 3),
        "intensity_norm": round(intensity_norm, 4),
        "dryness_norm": round(dryness_norm, 4),
        "frp_norm": round(frp_norm, 4),
        "area_norm": round(area_norm, 4),
    }


def plume_tip(meta: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """(lat, lon) of the plume's downwind centreline point, from cone_polygon meta."""
    if meta.get("tip_lat") is None or meta.get("tip_lon") is None:
        return None
    return meta["tip_lat"], meta["tip_lon"]
