"""Runtime settings, read from environment variables (all prefixed TWGEO_)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # The Layer 2 data store. Local rasters requested through the API must live under it.
    data_dir: Path
    cache_dir: Path
    cache_enabled: bool
    # Library callers may read any path; the API only does when this is set.
    allow_any_local_path: bool
    cors_origins: tuple[str, ...]
    # Guards against accidentally requesting a continent.
    max_patch_pixels: int
    max_screen_cells: int


def _default_data_dir() -> Path:
    """The store shared with Layer 2: TWGEO_DATA_DIR, else TERRAWINDOW_DATA_DIR, else backend/data."""
    env = os.environ.get("TWGEO_DATA_DIR") or os.environ.get("TERRAWINDOW_DATA_DIR")
    if env:
        return Path(env).resolve()
    backend = Path(__file__).resolve().parents[3]  # src/terrawindow_geo/config.py -> backend/
    if backend.name == "backend":
        return backend / "data"
    return (Path.cwd() / "data").resolve()


@lru_cache
def get_settings() -> Settings:
    data_dir = _default_data_dir()
    cache_dir = Path(os.environ.get("TWGEO_CACHE_DIR", str(data_dir / "cache"))).resolve()
    origins = os.environ.get("TWGEO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return Settings(
        data_dir=data_dir,
        cache_dir=cache_dir,
        cache_enabled=_flag("TWGEO_CACHE", True),
        allow_any_local_path=_flag("TWGEO_ALLOW_ANY_LOCAL_PATH", False),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        max_patch_pixels=int(os.environ.get("TWGEO_MAX_PATCH_PIXELS", 16_000_000)),
        max_screen_cells=int(os.environ.get("TWGEO_MAX_SCREEN_CELLS", 2500)),
    )
