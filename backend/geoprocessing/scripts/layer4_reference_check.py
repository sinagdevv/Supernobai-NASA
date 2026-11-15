"""Cross-check Layer 4 solar elevation against independent calculations.

Earth: NOAA/Meeus solar position (analytic; no SPICE). Mars: Allison & McEwen (2000) Mars24 algorithm
(analytic; no SPICE). Moon: the same SPICE ephemeris but the IAU_MOON orientation (pck00011) instead of
the DE440 principal-axis/mean-Earth frame Layer 4 uses, so only the orientation model is independent.

This compares computed numbers with other computed numbers. It is NOT observational validation: no
measured illumination, shadow or sun-angle record is used. Run from backend/geoprocessing:
    ..\\.venv\\Scripts\\python.exe scripts\\layer4_reference_check.py
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from terrawindow_geo.api.app import app
from terrawindow_geo.rehearsal_service import kernel_dir

START, END, STEP = "2026-11-16T00:00:00Z", "2026-11-17T00:00:00Z", 120
TOL = {"earth": 0.05, "mars": 0.50, "mars_spice": 0.02, "moon": 0.10}  # degrees; Mars24 is an analytic fit good to a few tenths of a degree


def _jd_ut(t: datetime) -> float:
    return t.timestamp() / 86400.0 + 2440587.5


def noaa_elevation(t: datetime, lat: float, lon: float) -> float:
    """Geometric solar elevation (no refraction) by the NOAA/Meeus low-precision algorithm."""
    jc = (_jd_ut(t) - 2451545.0) / 36525.0
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = math.radians(m)
    c = math.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) + math.sin(2 * mr) * (0.019993 - 0.000101 * jc) + math.sin(3 * mr) * 0.000289
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    seconds = 21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))
    obliq = 23 + (26 + seconds / 60) / 60 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obliq)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obliq / 2)) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r) - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    minutes_utc = t.hour * 60 + t.minute + t.second / 60
    solar_time = (minutes_utc + eot + 4 * lon) % 1440
    hour_angle = solar_time / 4 - 180
    cos_zenith = math.sin(math.radians(lat)) * math.sin(math.radians(decl)) + math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(hour_angle))
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def mars24_elevation(t: datetime, lat: float, east_lon: float) -> float:
    """Solar elevation on Mars by Allison & McEwen (2000), as tabulated by NASA GISS Mars24."""
    jd_tt = _jd_ut(t) + 69.184 / 86400.0  # TT-UTC = 37 leap seconds + 32.184 s in 2026
    d = jd_tt - 2451545.0
    m = math.radians(19.3871 + 0.52402073 * d)
    alpha_fms = 270.3863 + 0.52403840 * d
    amp = (0.0071, 0.0057, 0.0039, 0.0037, 0.0021, 0.0020, 0.0018)
    tau = (2.2353, 2.7543, 1.1177, 15.7866, 2.1354, 2.4694, 32.8493)
    phase = (49.409, 168.173, 191.837, 21.736, 15.704, 95.528, 49.095)
    pbs = sum(a * math.cos(math.radians(0.985626 * d / ti + p)) for a, ti, p in zip(amp, tau, phase))
    nu_minus_m = (10.691 + 3.0e-7 * d) * math.sin(m) + 0.623 * math.sin(2 * m) + 0.050 * math.sin(3 * m) + 0.005 * math.sin(4 * m) + 0.0005 * math.sin(5 * m) + pbs
    ls = math.radians((alpha_fms + nu_minus_m) % 360)
    eot = 2.861 * math.sin(2 * ls) - 0.071 * math.sin(4 * ls) + 0.002 * math.sin(6 * ls) - nu_minus_m  # degrees
    mtc_hours = 24.0 * ((_jd_ut(t) - 2451549.5) / 1.0274912517 + 44796.0 - 0.0009626)
    west_lon = (360.0 - east_lon) % 360
    lmst = (mtc_hours - west_lon / 15.0) % 24
    ltst = (lmst + eot / 15.0) % 24
    hour_angle = math.radians((ltst - 12.0) * 15.0)
    dec = math.asin(0.42565 * math.sin(ls)) + math.radians(0.25) * math.sin(ls)
    cos_zenith = math.sin(dec) * math.sin(math.radians(lat)) + math.cos(dec) * math.cos(math.radians(lat)) * math.cos(hour_angle)
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def moon_iau_moon_elevation(times: list[datetime], lat: float, lon: float, elevation_m: float) -> list[float]:
    """Sun elevation from SPICE with IAU_MOON (pck00011) rather than MOON_ME (DE440 binary PCK)."""
    import spiceypy as sp

    base = kernel_dir()
    sp.kclear()
    for name in ("naif0012.tls", "de440s.bsp", "pck00011.tpc"):
        sp.furnsh(str(base / name))
    try:
        radii = sp.bodvrd("MOON", "RADII", 3)[1]
        out = []
        for t in times:
            et = sp.str2et(t.strftime("%Y-%m-%dT%H:%M:%S"))
            sun = sp.spkpos("SUN", et, "IAU_MOON", "NONE", "MOON")[0]
            # Observer on the 1737.4 km sphere used by the LOLA product, planetocentric lat/lon.
            r = 1737.4 + elevation_m / 1000.0
            obs = sp.latrec(r, math.radians(lon), math.radians(lat))
            up = [c / math.sqrt(sum(x * x for x in obs)) for c in obs]
            to_sun = [s - o for s, o in zip(sun, obs)]
            n = math.sqrt(sum(x * x for x in to_sun))
            out.append(math.degrees(math.asin(sum(u * s / n for u, s in zip(up, to_sun)))))
        return out
    finally:
        sp.kclear()


def mars_spice_elevation(times: list[datetime], lat: float, lon: float) -> list[float]:
    """Sun elevation from SPICE IAU_MARS (pck00011 only: no MOLA frame transform) over the PCK ellipsoid normal."""
    import spiceypy as sp

    base = kernel_dir()
    sp.kclear()
    for name in ("naif0012.tls", "de440s.bsp", "mar099s.bsp", "pck00011.tpc"):
        sp.furnsh(str(base / name))
    try:
        radii = sp.bodvrd("MARS", "RADII", 3)[1]
        surface = sp.surfpt([0.0, 0.0, 0.0], sp.latrec(1.0, math.radians(lon), math.radians(lat)), *radii)
        normal = sp.surfnm(*radii, surface)
        out = []
        for t in times:
            et = sp.str2et(t.strftime("%Y-%m-%dT%H:%M:%S"))
            sun = sp.spkpos("SUN", et, "IAU_MARS", "NONE", "MARS")[0]
            to_sun = [a - b for a, b in zip(sun, surface)]
            out.append(math.degrees(math.asin(sum(n * v for n, v in zip(normal, to_sun)) / math.sqrt(sum(v * v for v in to_sun)))))
        return out
    finally:
        sp.kclear()


def main() -> int:
    client = TestClient(app)
    cases = {
        "earth": {"candidate": {"dataset": {"id": "sp-crater-copernicus-glo30"}, "bbox": {"west": -111.67, "south": 35.55, "east": -111.59, "north": 35.61}}},
        "moon": {"candidate": {"dataset": {"id": "lola-5mpp-site01"}, "scales_m": [40]}, "scale_m": 40},
        "mars": {"candidate": {"dataset": {"id": "jezero-mola-megdr128"}, "bbox": {"west": 77.4, "south": 18.35, "east": 77.6, "north": 18.45}}, "max_distance_m": 10000},
    }
    failures = 0
    for body, case in cases.items():
        response = client.post("/v1/rehearsal/evaluate", json={**case, "start_utc": START, "end_utc": END, "step_minutes": STEP})
        if response.status_code != 200:
            print(f"{body}: Layer 4 request failed: {response.status_code} {response.text[:200]}")
            failures += 1
            continue
        result = response.json()
        lat, lon = result["target_latitude_deg"], result["target_longitude_deg"]
        obs = result["observations"]
        times = [datetime.fromisoformat(o["time_utc"]).astimezone(timezone.utc) for o in obs]
        layer4 = [o["solar_elevation_deg"] for o in obs]
        if body == "earth":
            ref, source = [noaa_elevation(t, lat, lon) for t in times], "NOAA/Meeus"
        elif body == "mars":
            ref, source = [mars24_elevation(t, lat, lon) for t in times], "Allison & McEwen (2000) Mars24"
        else:
            elev = result.get("target_elevation_m", 0.0) or 0.0
            ref, source = moon_iau_moon_elevation(times, lat, lon, elev), "SPICE IAU_MOON orientation (same ephemeris)"
        comparisons = [(body, source, ref)]
        if body == "mars":
            comparisons.append(("mars_spice", "SPICE IAU_MARS (pck00011 only; no MOLA frame transform), ellipsoid normal", mars_spice_elevation(times, lat, lon)))
        for key, name, values in comparisons:
            worst = max((x - y for x, y in zip(layer4, values)), key=abs)
            ok = abs(worst) <= TOL[key]
            failures += not ok
            print(f"{body:5s} {len(times)} samples vs {name}: max |diff| {abs(worst):.4f} deg (tolerance {TOL[key]} deg) -> {'OK' if ok else 'OUTSIDE TOLERANCE'}")
    print("Computed-versus-computed agreement only; not observational validation.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
