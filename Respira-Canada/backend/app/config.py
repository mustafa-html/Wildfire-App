"""Runtime configuration. Everything that points at an external service is an
environment variable so a renamed layer or moved endpoint is a config change,
not a code change (CWFIS is part-way through migrating to a new GeoServer)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Tuple

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


# --- Natural Resources Canada: Canadian Wildland Fire Information System ------
CWFIS_WFS_URL = _env("CWFIS_WFS_URL", "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows")
CWFIS_STATIONS_LAYER = _env("CWFIS_STATIONS_LAYER", "public:firewx_stns_current")
CWFIS_HOTSPOTS_LAYER = _env("CWFIS_HOTSPOTS_LAYER", "public:hotspots_24h")

# Agency-reported active fires. CWFIS 2.0 serves these from the new CWFIF
# GeoServer; the legacy layer is used as a fallback.
CWFIF_WFS_URL = _env("CWFIF_WFS_URL", "https://geoserver.cwfif.nrcan.gc.ca/geoserver/wfs")
CWFIF_ACTIVEFIRES_LAYER = _env("CWFIF_ACTIVEFIRES_LAYER", "public:cwfif_national_activefires")
CWFIS_ACTIVEFIRES_LAYER = _env("CWFIS_ACTIVEFIRES_LAYER", "public:activefires_current")

# --- Environment and Climate Change Canada: MSC GeoMet OGC API -----------------
ECCC_OGC_API_URL = _env("ECCC_OGC_API_URL", "https://api.weather.gc.ca")

# --- Open-Meteo, serving ECCC's GEM model (current wind for smoke plumes) ------
OPEN_METEO_URL = _env("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
OPEN_METEO_MODEL = _env("OPEN_METEO_MODEL", "gem_seamless")

# --- App behaviour ---------------------------------------------------------------
DEFAULT_REGION = _env("DEFAULT_REGION", "AB").upper()
HTTP_TIMEOUT_S = float(_env("HTTP_TIMEOUT_S", "20"))
CACHE_TTL_S = int(_env("CACHE_TTL_S", "600"))
USER_AGENT = _env("USER_AGENT", "respira-canada/1.0 (+https://github.com/)")

FRONTEND_URL = _env("FRONTEND_URL", "http://localhost:3000")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    # (south, west, north, east) in decimal degrees
    bbox: Tuple[float, float, float, float]
    center: Tuple[float, float]
    zoom: int

    def as_dict(self) -> dict:
        s, w, n, e = self.bbox
        return {
            "code": self.code,
            "name": self.name,
            "bounds": {"south": s, "west": w, "north": n, "east": e},
            "center": {"lat": self.center[0], "lng": self.center[1]},
            "zoom": self.zoom,
        }


# Bounding boxes are rectangles, so stations just across a border can appear in
# a neighbouring province's view. That's intentional: smoke and fire weather
# don't stop at the border either.
REGIONS: Dict[str, Region] = {
    r.code: r
    for r in [
        Region("CA", "All of Canada", (41.7, -141.0, 70.0, -52.6), (56.0, -96.0), 4),
        Region("BC", "British Columbia", (48.2, -139.1, 60.0, -114.0), (54.0, -125.0), 5),
        Region("AB", "Alberta", (49.0, -120.0, 60.0, -110.0), (54.5, -115.0), 5),
        Region("SK", "Saskatchewan", (49.0, -110.0, 60.0, -101.3), (54.5, -105.7), 5),
        Region("MB", "Manitoba", (49.0, -102.0, 60.0, -88.9), (54.5, -97.5), 5),
        Region("ON", "Ontario", (41.7, -95.2, 56.9, -74.3), (49.5, -85.0), 5),
        Region("QC", "Quebec", (45.0, -79.8, 62.6, -57.1), (51.5, -71.5), 5),
        Region("NB", "New Brunswick", (44.6, -69.1, 48.1, -63.7), (46.5, -66.4), 7),
        Region("NS", "Nova Scotia", (43.4, -66.4, 47.1, -59.7), (45.1, -63.0), 7),
        Region("PE", "Prince Edward Island", (45.9, -64.5, 47.1, -61.9), (46.4, -63.2), 8),
        Region("NL", "Newfoundland and Labrador", (46.6, -67.8, 60.4, -52.6), (53.0, -60.0), 5),
        Region("YT", "Yukon", (60.0, -141.0, 69.7, -123.8), (63.5, -135.5), 5),
        Region("NT", "Northwest Territories", (60.0, -136.5, 70.0, -102.0), (64.0, -119.0), 4),
        Region("NU", "Nunavut", (51.6, -120.7, 70.0, -61.2), (64.0, -90.0), 4),
    ]
}


def get_region(code: str | None) -> Region:
    key = (code or DEFAULT_REGION).upper()
    if key not in REGIONS:
        raise KeyError(f"Unknown region '{code}'. Use one of: {', '.join(REGIONS)}")
    return REGIONS[key]
