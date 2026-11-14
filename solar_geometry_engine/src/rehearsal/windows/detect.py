from __future__ import annotations
from pathlib import Path
import numpy as np
import yaml
from ..schemas import SunSeries, Window
from ..solar.conventions import circular_mean_deg, dt64_to_datetime

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "thresholds.yaml"


def load_thresholds(path: Path = DEFAULT_CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text())


def find_windows(series: SunSeries, min_elev: float = 0.0, max_elev: float = 7.0,
                 min_window_minutes: float = 0.0) -> list[Window]:
    """Group consecutive samples with min_elev <= elevation <= max_elev into windows.
    All thresholds are parameters so Test 4 can sweep them."""
    el = series.elevation_deg
    mask = (el >= min_elev) & (el <= max_elev)
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False]))
    d = np.diff(padded.astype(np.int8))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0] - 1   # inclusive indices
    out = []
    for i, j in zip(starts, ends):
        n = j - i + 1
        dur = n * series.step_minutes
        if dur < min_window_minutes:
            continue
        out.append(Window(
            start_utc=dt64_to_datetime(series.times_utc[i]),
            end_utc=dt64_to_datetime(series.times_utc[j]),
            duration_min=dur,
            mean_azimuth_deg=circular_mean_deg(series.azimuth_deg[i:j + 1]),
            min_elevation_deg=float(el[i:j + 1].min()),
            max_elevation_deg=float(el[i:j + 1].max()),
            truncated_start=(i == 0),
            truncated_end=(j == len(mask) - 1),
        ))
    return out
