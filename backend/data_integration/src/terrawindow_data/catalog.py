"""The datasets TERRAWINDOW knows about, and exactly where each one comes from.

Two kinds of entry:
  file  : a fixed set of downloadable rasters (the lunar south-pole site models).
  tiled : a global dataset served as cloud-optimised tiles; regions are cut out on request.

Every URL pattern here was checked against the live server when this catalog was written.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

BODY_RADIUS_M = {"earth": 6378137.0, "moon": 1737400.0, "mars": 3396190.0}


@dataclass(frozen=True)
class Product:
    """One raster of a dataset."""

    key: str  # surface, uncertainty, slope, counts
    url: str
    quantity: str
    unit: str


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    body: str
    kind: str  # elevation | landcover
    access: str  # file | tiled
    nominal_resolution_m: float
    citation: str
    license: str
    source_page: str
    coverage: str
    vertical_datum: str = ""
    products: tuple[Product, ...] = ()
    primary: str = "surface"
    limitations: tuple[str, ...] = ()
    tile_degrees: int = 0
    extra: dict = field(default_factory=dict)


# ----------------------------------------------------------------- lunar: PGDA LOLA 5 m/pix sites

_PGDA = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
_LOLA_CITATION = (
    "Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: "
    "Error estimates and their impact on illumination conditions. Planetary and Space Science, 203, 105119. "
    "https://doi.org/10.1016/j.pss.2020.105119"
)
_LOLA_LIMITS = (
    "Surface heights fill pixels with no laser return by interpolation; the counts product shows where.",
    "Interpolated areas are smoother than the real surface, which lowers slope and roughness there.",
    "5 m pixels do not resolve rover-scale rocks or small craters.",
)
# directory on the server -> (catalog suffix, place name)
LOLA_SITES = {
    "Site01": ("site01", "Connecting ridge"),
    "Site04": ("site04", "Shackleton rim"),
    "Site06": ("site06", "Nobile rim 1"),
    "Site07": ("site07", "Peak near Shackleton"),
    "Site11": ("site11", "de Gerlache rim"),
    "Site20": ("site20", "Leibnitz beta plateau"),
    "Site23": ("site23", "Malapert massif"),
    "Haworth": ("haworth", "Haworth"),
    "Shoemaker": ("shoemaker", "Shoemaker"),
    "DM2": ("dm2", "Nobile rim 2"),
}
_LOLA_PRODUCTS = (
    ("surface", "surf", "surface height above the 1737.4 km reference sphere", "metres"),
    ("uncertainty", "toterr", "total height uncertainty (RMS error)", "metres"),
    ("slope", "slp", "slope published with the dataset", "degrees"),
    ("slope_uncertainty", "slperr", "slope uncertainty (RMS error)", "degrees"),
    ("counts", "ldec", "number of LOLA returns per pixel (0 = interpolated)", "count"),
)


def _lola_entry(directory: str, suffix: str, place: str) -> CatalogEntry:
    return CatalogEntry(
        id=f"lola-5mpp-{suffix}",
        name=f"LOLA 5 m/pix south-pole site model: {place} ({directory})",
        body="moon",
        kind="elevation",
        access="file",
        nominal_resolution_m=5.0,
        citation=_LOLA_CITATION,
        license="NASA data, public domain; cite the dataset paper.",
        source_page="https://pgda.gsfc.nasa.gov/products/78",
        coverage=f"Lunar south-polar candidate landing region '{place}'.",
        vertical_datum="Height above a 1737.4 km sphere, MOON_ME frame (DE421); south polar stereographic, metres.",
        products=tuple(
            Product(key, f"{_PGDA}/{directory}/{directory}_final_adj_5mpp_{code}.tif", quantity, unit)
            for key, code, quantity, unit in _LOLA_PRODUCTS
        ),
        limitations=_LOLA_LIMITS,
        extra={"site": directory, "place": place},
    )


# ----------------------------------------------------------------- Earth: tiled global datasets

GLO30 = CatalogEntry(
    id="copernicus-glo30",
    name="Copernicus DEM GLO-30 (public COGs on AWS Open Data)",
    body="earth",
    kind="elevation",
    access="tiled",
    nominal_resolution_m=30.0,
    citation="European Space Agency (2024). Copernicus Global Digital Elevation Model. Distributed by OpenTopography. https://doi.org/10.5069/G9028PQB",
    license="Copernicus DEM licence: free of charge, attribution required.",
    source_page="https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM",
    coverage="Global land, 1 x 1 degree tiles.",
    vertical_datum="Orthometric height, EGM2008 geoid; WGS84 geographic grid.",
    limitations=(
        "A surface model: vegetation and buildings are included in the heights.",
        "About 30 m pixels do not resolve rover-scale obstacles.",
        "Tiles over open ocean do not exist.",
    ),
    tile_degrees=1,
)

WORLDCOVER = CatalogEntry(
    id="esa-worldcover",
    name="ESA WorldCover 10 m 2021 v200",
    body="earth",
    kind="landcover",
    access="tiled",
    nominal_resolution_m=10.0,
    citation="Zanaga, D., et al. (2022). ESA WorldCover 10 m 2021 v200. https://doi.org/10.5281/zenodo.7254221",
    license="CC BY 4.0",
    source_page="https://esa-worldcover.org",
    coverage="Global land, 3 x 3 degree tiles, 11 land-cover classes.",
    limitations=("A 2021 snapshot; land use may have changed.", "Class accuracy is about 77 % globally and varies by class."),
    primary="classes",
    tile_degrees=3,
)

CATALOG: dict[str, CatalogEntry] = {e.id: e for e in [*(_lola_entry(d, s, p) for d, (s, p) in LOLA_SITES.items()), GLO30, WORLDCOVER]}


def get_entry(dataset_id: str) -> CatalogEntry:
    try:
        return CATALOG[dataset_id]
    except KeyError:
        raise KeyError(f"Unknown dataset id '{dataset_id}'. Known ids: {', '.join(sorted(CATALOG))}") from None


# ----------------------------------------------------------------- tile naming


def _ns(lat: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"


def _ew(lon: int) -> str:
    return f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def tile_urls(entry: CatalogEntry, west: float, south: float, east: float, north: float) -> list[str]:
    """URLs of the tiles of a tiled dataset that touch a lon/lat box."""
    if entry.access != "tiled":
        raise ValueError(f"{entry.id} is not a tiled dataset")
    step, eps = entry.tile_degrees, 1e-9
    urls = []
    lat = math.floor(south / step) * step
    while lat < north - eps:
        lon = math.floor(west / step) * step
        while lon < east - eps:
            if entry.id == GLO30.id:
                name = f"Copernicus_DSM_COG_10_{_ns(lat)}_00_{_ew(lon)}_00_DEM"
                urls.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif")
            else:
                urls.append(
                    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                    f"ESA_WorldCover_10m_2021_v200_{_ns(lat)}{_ew(lon)}_Map.tif"
                )
            lon += step
        lat += step
    return urls
