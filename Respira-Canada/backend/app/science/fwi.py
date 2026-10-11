"""Canadian Forest Fire Weather Index (FWI) System.

Daily equations from Van Wagner & Pickett (1985), *Equations and FORTRAN
program for the Canadian Forest Fire Weather Index System* (Forestry Technical
Report 33), as summarised in Van Wagner (1987).

This is the Canadian replacement for the US NFDRS indices the original app
pulled from FEMS. In normal operation CWFIS already publishes FFMC/DMC/DC/ISI/
BUI/FWI for each station, so these functions are used to:

* fill in ISI / BUI / FWI when a station reports the moisture codes but not
  the derived indices,
* convert FFMC into fine-fuel moisture content (the plume model's analogue of
  NFDRS 1-hour fuel moisture),
* run the full daily chain from raw noon weather (``calc_fwi_day``) for tests,
  scripts, or a future "what if" endpoint.

Inputs use Canadian conventions: temperature in °C, relative humidity in %,
10 m wind speed in km/h, 24 h rain in mm, all observed at local solar noon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

# Day-length adjustment factors by month (index 0 = January), for latitudes
# above ~30°N — i.e. all of Canada.
DMC_DAY_LENGTH = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0]
DC_DAY_LENGTH = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6]

# Standard season start-up values (Lawson & Armitage 2008).
STARTUP_FFMC = 85.0
STARTUP_DMC = 6.0
STARTUP_DC = 15.0


def _clamp_rh(rh: float) -> float:
    return min(max(rh, 0.0), 100.0)


def ffmc_to_moisture(ffmc: float) -> float:
    """Fine fuel moisture content (%) implied by an FFMC value."""
    return 147.2 * (101.0 - ffmc) / (59.5 + ffmc)


def moisture_to_ffmc(m: float) -> float:
    return 59.5 * (250.0 - m) / (147.2 + m)


def calc_ffmc(temp: float, rh: float, wind: float, rain: float, ffmc_prev: float) -> float:
    rh = _clamp_rh(rh)
    mo = ffmc_to_moisture(ffmc_prev)

    if rain > 0.5:
        rf = rain - 0.5
        mr = mo + 42.5 * rf * math.exp(-100.0 / (251.0 - mo)) * (1.0 - math.exp(-6.93 / rf))
        if mo > 150.0:
            mr += 0.0015 * (mo - 150.0) ** 2 * math.sqrt(rf)
        mo = min(mr, 250.0)

    ed = (
        0.942 * rh ** 0.679
        + 11.0 * math.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp) * (1.0 - math.exp(-0.115 * rh))
    )

    if mo > ed:
        ko = 0.424 * (1.0 - (rh / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (1.0 - (rh / 100.0) ** 8)
        kd = ko * 0.581 * math.exp(0.0365 * temp)
        m = ed + (mo - ed) * 10.0 ** (-kd)
    else:
        ew = (
            0.618 * rh ** 0.753
            + 10.0 * math.exp((rh - 100.0) / 10.0)
            + 0.18 * (21.1 - temp) * (1.0 - math.exp(-0.115 * rh))
        )
        if mo < ew:
            k1 = 0.424 * (1.0 - ((100.0 - rh) / 100.0) ** 1.7) + 0.0694 * math.sqrt(wind) * (
                1.0 - ((100.0 - rh) / 100.0) ** 8
            )
            kw = k1 * 0.581 * math.exp(0.0365 * temp)
            m = ew - (ew - mo) * 10.0 ** (-kw)
        else:
            m = mo

    return min(max(moisture_to_ffmc(m), 0.0), 101.0)


def calc_dmc(temp: float, rh: float, rain: float, month: int, dmc_prev: float) -> float:
    rh = _clamp_rh(rh)
    temp = max(temp, -1.1)
    rk = 1.894 * (temp + 1.1) * (100.0 - rh) * DMC_DAY_LENGTH[month - 1] * 1e-4

    pr = dmc_prev
    if rain > 1.5:
        re = 0.92 * rain - 1.27
        mo = 20.0 + math.exp(5.6348 - dmc_prev / 43.43)
        if dmc_prev <= 33.0:
            b = 100.0 / (0.5 + 0.3 * dmc_prev)
        elif dmc_prev <= 65.0:
            b = 14.0 - 1.3 * math.log(dmc_prev)
        else:
            b = 6.2 * math.log(dmc_prev) - 17.2
        mr = mo + 1000.0 * re / (48.77 + b * re)
        pr = max(244.72 - 43.43 * math.log(mr - 20.0), 0.0)

    return max(pr + rk, 0.0)


def calc_dc(temp: float, rain: float, month: int, dc_prev: float) -> float:
    temp = max(temp, -2.8)
    pe = max((0.36 * (temp + 2.8) + DC_DAY_LENGTH[month - 1]) / 2.0, 0.0)

    dr = dc_prev
    if rain > 2.8:
        rd = 0.83 * rain - 1.27
        qo = 800.0 * math.exp(-dc_prev / 400.0)
        qr = qo + 3.937 * rd
        dr = max(400.0 * math.log(800.0 / qr), 0.0)

    return max(dr + pe, 0.0)


def calc_isi(ffmc: float, wind: float) -> float:
    m = ffmc_to_moisture(ffmc)
    f_wind = math.exp(0.05039 * wind)
    f_fuel = 91.9 * math.exp(-0.1386 * m) * (1.0 + m ** 5.31 / 4.93e7)
    return 0.208 * f_wind * f_fuel


def calc_bui(dmc: float, dc: float) -> float:
    if dmc <= 0.0 and dc <= 0.0:
        return 0.0
    if dmc <= 0.4 * dc:
        bui = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        bui = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    return max(bui, 0.0)


def calc_fwi(isi: float, bui: float) -> float:
    if bui <= 80.0:
        fd = 0.626 * bui ** 0.809 + 2.0
    else:
        fd = 1000.0 / (25.0 + 108.64 * math.exp(-0.023 * bui))
    b = 0.1 * isi * fd
    if b <= 1.0:
        return b
    return math.exp(2.72 * (0.434 * math.log(b)) ** 0.647)


def calc_dsr(fwi: float) -> float:
    """Daily Severity Rating."""
    return 0.0272 * fwi ** 1.77


@dataclass
class FWIResult:
    ffmc: float
    dmc: float
    dc: float
    isi: float
    bui: float
    fwi: float
    dsr: float

    def rounded(self, ndigits: int = 1) -> dict:
        return {k: round(v, ndigits) for k, v in asdict(self).items()}


def calc_fwi_day(
    *,
    temp: float,
    rh: float,
    wind: float,
    rain: float,
    month: int,
    ffmc_prev: float = STARTUP_FFMC,
    dmc_prev: float = STARTUP_DMC,
    dc_prev: float = STARTUP_DC,
) -> FWIResult:
    """Run one day of the FWI System from local-noon weather."""
    ffmc = calc_ffmc(temp, rh, wind, rain, ffmc_prev)
    dmc = calc_dmc(temp, rh, rain, month, dmc_prev)
    dc = calc_dc(temp, rain, month, dc_prev)
    isi = calc_isi(ffmc, wind)
    bui = calc_bui(dmc, dc)
    fwi = calc_fwi(isi, bui)
    return FWIResult(ffmc=ffmc, dmc=dmc, dc=dc, isi=isi, bui=bui, fwi=fwi, dsr=calc_dsr(fwi))


def complete_indices(
    *,
    ffmc: Optional[float],
    dmc: Optional[float],
    dc: Optional[float],
    wind: Optional[float],
    isi: Optional[float] = None,
    bui: Optional[float] = None,
    fwi: Optional[float] = None,
) -> dict:
    """Fill in ISI/BUI/FWI from the moisture codes when a source omits them.

    Returns a dict with whatever could be determined; missing values stay None
    (e.g. a station in winter shutdown reports no FFMC at all).
    """
    if isi is None and ffmc is not None and wind is not None:
        isi = calc_isi(ffmc, wind)
    if bui is None and dmc is not None and dc is not None:
        bui = calc_bui(dmc, dc)
    if fwi is None and isi is not None and bui is not None:
        fwi = calc_fwi(isi, bui)
    return {"ffmc": ffmc, "dmc": dmc, "dc": dc, "isi": isi, "bui": bui, "fwi": fwi}
