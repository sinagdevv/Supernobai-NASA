"""TERRAWINDOW Layer 2: scientific data integration.

Finds the open datasets the project uses, retrieves them into a local store, checks that each
file is what it claims to be, and records where it came from. Layer 3 reads the store's
manifest.json, so a dataset fetched here is usable there by id.

    from terrawindow_data import CATALOG, fetch_dataset, prepare_region, load_manifest
"""

__version__ = "0.1.0"

from .catalog import CATALOG, get_entry  # noqa: E402
from .store import data_dir, load_manifest  # noqa: E402
from .fetch import fetch_dataset  # noqa: E402
from .prepare import prepare_region  # noqa: E402
from .validate import validate_raster  # noqa: E402

__all__ = [
    "__version__",
    "CATALOG",
    "get_entry",
    "data_dir",
    "load_manifest",
    "fetch_dataset",
    "prepare_region",
    "validate_raster",
]
