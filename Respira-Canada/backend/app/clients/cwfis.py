"""Natural Resources Canada — Canadian Wildland Fire Information System (CWFIS).

Replaces the US FEMS GraphQL client. Three WFS layers are used:

* ``firewx_stns_current`` — local-noon weather *and* the full FWI System
  (FFMC, DMC, DC, ISI, BUI, FWI, DSR) for every fire-weather station, in one
  request. FEMS needed separate weather and NFDRS queries per station.
* active fires reported by provincial/territorial agencies (via CIFFC).
* satellite hotspots from the last 24 hours, with fire radiative power.

All three are normalised into plain dicts with stable keys so the rest of the
app never touches raw GeoServer attribute names. Attribute lookups are
case-insensitive and accept a few aliases, because CWFIS is migrating layers to
a new GeoServer and field names are not guaranteed to survive the move.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app import config
from app.clients.http import UpstreamError, get_json
from app.config import Region
from app.science.fwi import complete_indices

logger = logging.getLogger(__name__)

STAGE_OF_CONTROL = {
    "OC": "Out of control",
    "BH": "Being held",
    "UC": "Under control",
    "EX": "Out",
    "UNK": "Unknown",
}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _lower_keys(props: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k).lower(): v for k, v in (props or {}).items()}


def _first(props: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = props.get(k)
        if v not in (None, ""):
            return v
    return None


def _num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or f <= -999:  # common "missing" sentinels
        return None
    return f


def _in_canada_box(lat: float, lon: float) -> bool:
    return 35.0 <= lat <= 85.0 and -170.0 <= lon <= -50.0


def _coords(feature: Dict[str, Any], props: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Latitude/longitude from attributes, falling back to the geometry.

    GeoServer can emit EPSG:4326 in either axis order depending on WFS version,
    so the geometry fallback checks which order is plausible for Canada.
    """
    lat = _num(_first(props, "lat", "latitude", "y"))
    lon = _num(_first(props, "lon", "long", "longitude", "x"))
    if lat is not None and lon is not None:
        return lat, lon

    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if geom.get("type") == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        a, b = float(coords[0]), float(coords[1])
        if _in_canada_box(b, a):
            return b, a
        if _in_canada_box(a, b):
            return a, b
    return None, None


def _in_region(lat: Optional[float], lon: Optional[float], region: Region) -> bool:
    if lat is None or lon is None:
        return False
    s, w, n, e = region.bbox
    return s <= lat <= n and w <= lon <= e


def _latlon_cql(region: Region) -> str:
    s, w, n, e = region.bbox
    return f"lat BETWEEN {s} AND {n} AND lon BETWEEN {w} AND {e}"


def _wfs(
    url: str,
    layer: str,
    *,
    count: int,
    cql: Optional[str] = None,
    sort_by: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": count,
    }
    if cql:
        params["CQL_FILTER"] = cql
    if sort_by:
        params["sortBy"] = sort_by
    data = get_json(url, params)
    if not isinstance(data, dict) or "features" not in data:
        raise UpstreamError(f"Unexpected WFS response for {layer}")
    return data["features"] or []


def _wfs_region(
    url: str,
    layer: str,
    region: Region,
    *,
    count: int,
    sort_by: Optional[str] = None,
    extra_cql: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Ask GeoServer to filter by lat/lon attributes; if the layer has no such
    attributes, fetch unfiltered and filter locally."""
    cql = _latlon_cql(region)
    if extra_cql:
        cql = f"({cql}) AND ({extra_cql})"
    try:
        return _wfs(url, layer, count=count, cql=cql, sort_by=sort_by)
    except UpstreamError as exc:
        logger.info("Attribute filter rejected for %s (%s); filtering locally", layer, exc)
        return _wfs(url, layer, count=count, cql=extra_cql)


# ----------------------------------------------------------------------------
# fire-weather stations + FWI
# ----------------------------------------------------------------------------
def normalise_station(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = _lower_keys(feature.get("properties") or {})
    lat, lon = _coords(feature, p)
    if lat is None or lon is None:
        return None

    station_id = _first(p, "wmo", "aes", "id", "station_id", "stn_id", "code") or feature.get("id")
    name = str(_first(p, "name", "station_name", "stn_name") or f"Station {station_id}")
    name = " ".join(name.replace("+", " ").split())

    wind = _num(_first(p, "ws", "wind_speed", "wspd"))
    weather = {
        "temperature": _num(_first(p, "temp", "temperature", "tmp")),  # °C
        "relative_humidity": _num(_first(p, "rh", "relative_humidity")),  # %
        "wind_speed": wind,  # km/h
        "wind_direction": _num(_first(p, "wdir", "wind_direction", "wd")),  # degrees from
        "wind_gust": _num(_first(p, "wg", "wind_gust", "gust")),  # km/h
        "precip_24h": _num(_first(p, "precip", "rain", "precipitation", "pcp")),  # mm
        "dewpoint": _num(_first(p, "td", "dewpoint")),
    }

    indices = complete_indices(
        ffmc=_num(p.get("ffmc")),
        dmc=_num(p.get("dmc")),
        dc=_num(p.get("dc")),
        wind=wind,
        isi=_num(p.get("isi")),
        bui=_num(p.get("bui")),
        fwi=_num(p.get("fwi")),
    )
    indices = {k: (round(v, 1) if v is not None else None) for k, v in indices.items()}
    indices["dsr"] = _num(p.get("dsr"))
    calc_status = _num(_first(p, "calcstatus", "calc_status"))
    indices["calc_status"] = int(calc_status) if calc_status is not None else None

    return {
        "station_id": str(station_id),
        "station_name": name,
        "latitude": lat,
        "longitude": lon,
        "elevation": _num(_first(p, "elev", "elevation")),
        "agency": _first(p, "agency", "prov", "province"),
        "observation_time": _first(p, "rep_date", "repdate", "obs_date", "date"),
        "weather": weather,
        "fwi": indices,
    }


def get_stations(region: Region, *, limit: int = 2000) -> List[Dict[str, Any]]:
    features = _wfs_region(config.CWFIS_WFS_URL, config.CWFIS_STATIONS_LAYER, region, count=limit)
    stations = []
    seen = set()
    for f in features:
        s = normalise_station(f)
        if not s or not _in_region(s["latitude"], s["longitude"], region):
            continue
        if s["station_id"] in seen:
            continue
        seen.add(s["station_id"])
        stations.append(s)
    return stations


def get_station(station_id: str, region: Region) -> Optional[Dict[str, Any]]:
    for s in get_stations(region):
        if s["station_id"] == str(station_id):
            return s
    if region.code != "CA":
        return get_station(station_id, config.get_region("CA"))
    return None


def has_fwi(station: Dict[str, Any]) -> bool:
    return station.get("fwi", {}).get("fwi") is not None


# ----------------------------------------------------------------------------
# active fires (agency reported)
# ----------------------------------------------------------------------------
def _stage(value: Any) -> str:
    if value in (None, ""):
        return "UNK"
    v = str(value).strip().upper()
    if v in STAGE_OF_CONTROL:
        return v
    words = {"OUT OF CONTROL": "OC", "BEING HELD": "BH", "UNDER CONTROL": "UC", "OUT": "EX"}
    return words.get(v, "UNK")


def normalise_fire(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = _lower_keys(feature.get("properties") or {})
    lat, lon = _coords(feature, p)
    if lat is None or lon is None:
        return None
    stage = _stage(_first(p, "stage_of_control", "stage_of_control_status", "soc", "fire_status", "status"))
    hectares = _num(_first(p, "hectares", "size_ha", "fire_size", "area_ha", "current_size", "size"))
    name = _first(p, "firename", "fire_name", "name", "fire_id", "fire_number", "incident_name")
    agency = _first(p, "agency", "agency_code", "agency_name", "source_agency")
    return {
        "fire_id": str(_first(p, "fire_id", "fireid", "firename", "fire_name") or feature.get("id")),
        "name": str(name) if name else "Unnamed fire",
        "agency": str(agency).upper() if agency else None,
        "latitude": lat,
        "longitude": lon,
        "hectares": hectares,
        "stage_of_control": stage,
        "stage_label": STAGE_OF_CONTROL[stage],
        "start_date": _first(p, "startdate", "start_date", "fire_start_date", "record_start"),
        "response_type": _first(p, "response_type", "responsetype"),
    }


def get_active_fires(region: Region, *, include_out: bool = False, limit: int = 5000) -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    try:
        features = _wfs(
            config.CWFIF_WFS_URL,
            config.CWFIF_ACTIVEFIRES_LAYER,
            count=limit,
            cql="now() >= record_start AND now() <= record_end",
        )
    except UpstreamError as exc:
        logger.warning("CWFIF active fires unavailable (%s); trying legacy CWFIS layer", exc)

    if not features:
        features = _wfs(config.CWFIS_WFS_URL, config.CWFIS_ACTIVEFIRES_LAYER, count=limit)

    fires = []
    for f in features:
        fire = normalise_fire(f)
        if not fire or not _in_region(fire["latitude"], fire["longitude"], region):
            continue
        if not include_out and fire["stage_of_control"] == "EX":
            continue
        fires.append(fire)
    fires.sort(key=lambda x: x["hectares"] or 0.0, reverse=True)
    return fires


# ----------------------------------------------------------------------------
# satellite hotspots (VIIRS / MODIS, last 24 h)
# ----------------------------------------------------------------------------
def normalise_hotspot(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = _lower_keys(feature.get("properties") or {})
    lat, lon = _coords(feature, p)
    if lat is None or lon is None:
        return None
    return {
        "latitude": lat,
        "longitude": lon,
        "detected_at": _first(p, "rep_date", "acq_date", "date"),
        "frp_mw": _num(_first(p, "frp")),
        "sensor": _first(p, "sensor", "satellite", "source"),
        "fire_type": _first(p, "fire_type", "firetype", "fuel"),
        "hfi": _num(_first(p, "hfi")),
    }


def get_hotspots(region: Region, *, limit: int = 5000) -> List[Dict[str, Any]]:
    features = _wfs_region(
        config.CWFIS_WFS_URL, config.CWFIS_HOTSPOTS_LAYER, region, count=limit, sort_by="rep_date D"
    )
    out = []
    for f in features:
        h = normalise_hotspot(f)
        if h and _in_region(h["latitude"], h["longitude"], region):
            out.append(h)
    return out


# ----------------------------------------------------------------------------
# geometry utilities shared by other modules
# ----------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest(
    lat: float, lon: float, items: Iterable[Dict[str, Any]], *, require_fwi: bool = False, k: int = 1
) -> List[Dict[str, Any]]:
    ranked = []
    for item in items:
        if require_fwi and not has_fwi(item):
            continue
        d = haversine_km(lat, lon, item["latitude"], item["longitude"])
        ranked.append({**item, "distance_km": round(d, 1)})
    ranked.sort(key=lambda x: x["distance_km"])
    return ranked[:k]
