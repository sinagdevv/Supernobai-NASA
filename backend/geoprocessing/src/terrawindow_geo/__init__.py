"""TERRAWINDOW Layer 3: geospatial terrain processing engine.

Library entry points (importable by Layers 4 and 5):

    from terrawindow_geo import build_profile, compare_profiles, screen_region, extract_dem
"""

__version__ = "0.1.0"

from .compare import compare_profiles  # noqa: E402
from .discovery import screen_region  # noqa: E402
from .errors import GeoError  # noqa: E402
from .profile import build_profile, extract_dem  # noqa: E402

__all__ = [
    "__version__",
    "GeoError",
    "build_profile",
    "compare_profiles",
    "extract_dem",
    "screen_region",
]
