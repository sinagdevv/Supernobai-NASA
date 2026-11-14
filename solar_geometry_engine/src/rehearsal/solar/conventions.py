"""Angle and time conventions. Most bugs hide here, so it is one small file.

Azimuth: degrees clockwise from TRUE north. 0=N, 90=E, 180=S, 270=W.
Longitude: east positive. Elevation: degrees above the geometric horizon.
"""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def normalize_azimuth(az):
    return np.mod(az, 360.0)


def relative_bearing(sun_az, heading):
    """Sun azimuth relative to travel heading, in (-180, 180].
    0 = sun dead ahead (worst glare), +90 = sun on the right, 180 = behind."""
    d = np.mod(np.asarray(sun_az) - np.asarray(heading), 360.0)
    return np.where(d > 180.0, d - 360.0, d)


def compass_label(az: float) -> str:
    return COMPASS[int((az % 360.0) / 22.5 + 0.5) % 16]


def circular_mean_deg(az) -> float:
    r = np.radians(az)
    return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())) % 360.0)


def to_utc(dt: datetime, tz: str | None = None) -> datetime:
    if dt.tzinfo is None:
        if tz is None:
            raise ValueError("naive datetime needs a tz name")
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(timezone.utc)


def to_local(dt_utc: datetime, tz: str) -> datetime:
    return dt_utc.astimezone(ZoneInfo(tz))


def dt64_to_datetime(t: np.datetime64) -> datetime:
    return datetime.fromtimestamp(int(t.astype("datetime64[s]").astype("int64")), tz=timezone.utc)
