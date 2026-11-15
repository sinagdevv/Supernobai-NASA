from __future__ import annotations
from datetime import datetime
import numpy as np
from ..schemas import Site, SunSeries
from ..earth.kernels import EarthKernelSet
from .conventions import to_utc
from .ephemeris import sun_alt_az


def sun_series(
    site: Site,
    start: datetime,
    end: datetime,
    step_minutes: float = 1.0,
    *,
    kernels: EarthKernelSet,
) -> SunSeries:
    """Sun elevation/azimuth from start (inclusive) to end (exclusive).
    Naive datetimes are interpreted in the site's local time zone. Earth
    positions require an explicit SPICE kernel set."""
    s, e = to_utc(start, site.tz), to_utc(end, site.tz)
    step_s = int(round(step_minutes * 60))
    t0 = np.datetime64(s.replace(tzinfo=None), "s")
    t1 = np.datetime64(e.replace(tzinfo=None), "s")
    times = np.arange(t0, t1, np.timedelta64(step_s, "s"))
    elev, az = sun_alt_az(site.lat, site.lon, site.elevation_m, times, kernels)
    return SunSeries(site, times, elev, az, step_minutes)
