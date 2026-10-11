"""Risk classification for Canadian data.

Fire danger
-----------
The US version blended NFDRS indices into a home-made 0-100 score. Canada has
a national standard for this, so the score here is anchored to the Fire
Weather Index: each CWFIS FWI map class occupies one 20-point band of the
0-100 scale and the score is interpolated linearly inside the band. That keeps
the original UI's five levels and 0-100 gauge while making the level identical
to the class you would see on the CWFIS national FWI map.

Default class breaks follow the CWFIS national FWI map legend
(Low 0-5, Moderate 6-15, High 16-22, Very High 23-29, Extreme 30+). Provincial
agencies publish their own danger ratings with different breaks (e.g. BC
Wildfire Service), so the breaks are configurable via ``FWI_CLASS_BREAKS``.

Air quality
-----------
Canada reports the Air Quality Health Index (AQHI, 1-10+) rather than the US
AQI. Categories: 1-3 low, 4-6 moderate, 7-10 high, above 10 very high risk.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

LEVELS = ["LOW", "MODERATE", "HIGH", "VERY HIGH", "EXTREME"]

_DEFAULT_BREAKS = (5.5, 15.5, 22.5, 29.5)
# FWI value that maps to a score of 100. Anything above is capped.
_FWI_CAP = 50.0


def _load_breaks() -> Tuple[float, float, float, float]:
    raw = os.getenv("FWI_CLASS_BREAKS")
    if not raw:
        return _DEFAULT_BREAKS
    try:
        parts = tuple(float(x) for x in raw.split(","))
        if len(parts) == 4 and list(parts) == sorted(parts):
            return parts  # type: ignore[return-value]
    except ValueError:
        pass
    return _DEFAULT_BREAKS


FWI_CLASS_BREAKS = _load_breaks()

INTERPRETATION = {
    "LOW": "Fires unlikely to spread far; normal caution with any open flame.",
    "MODERATE": "Fires can start from open flames and spread at a moderate rate.",
    "HIGH": "Fires start easily and spread quickly; avoid burning outdoors.",
    "VERY HIGH": "Fires start very easily, spread fast and are hard to control.",
    "EXTREME": "Explosive fire potential; follow every local fire ban and advisory.",
}


def fwi_danger_class(fwi: Optional[float]) -> Optional[str]:
    if fwi is None:
        return None
    for level, upper in zip(LEVELS, FWI_CLASS_BREAKS):
        if fwi < upper:
            return level
    return "EXTREME"


def fwi_to_score(fwi: Optional[float]) -> Optional[float]:
    """Map FWI onto 0-100 so that each danger class is a 20-point band."""
    if fwi is None:
        return None
    fwi = max(0.0, float(fwi))
    edges = [0.0, *FWI_CLASS_BREAKS, _FWI_CAP]
    for band, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        if fwi < hi or band == len(edges) - 2:
            frac = min((fwi - lo) / (hi - lo), 1.0) if hi > lo else 1.0
            return round(band * 20.0 + frac * 20.0, 2)
    return 100.0


def score_to_level(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score < 20:
        return "LOW"
    if score < 40:
        return "MODERATE"
    if score < 60:
        return "HIGH"
    if score < 80:
        return "VERY HIGH"
    return "EXTREME"


def aqhi_category(aqhi: Optional[float]) -> Optional[str]:
    if aqhi is None:
        return None
    if aqhi <= 3:
        return "LOW"
    if aqhi <= 6:
        return "MODERATE"
    if aqhi <= 10:
        return "HIGH"
    return "VERY HIGH"


AQHI_ADVICE = {
    "LOW": "Ideal air quality for outdoor activities.",
    "MODERATE": "At-risk people (heart or lung conditions, older adults, children) "
    "should consider reducing strenuous outdoor activity if they have symptoms.",
    "HIGH": "At-risk people should reduce or reschedule strenuous outdoor activity; "
    "children and older adults should take it easy.",
    "VERY HIGH": "At-risk people should avoid strenuous activity outdoors; everyone "
    "should reduce or reschedule strenuous outdoor activity.",
}
