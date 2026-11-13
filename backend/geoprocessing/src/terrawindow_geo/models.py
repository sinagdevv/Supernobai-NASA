"""Request and response shapes. These are the contract with the UI and Layers 4-6."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Body = Literal["earth", "moon", "mars"]
Status = Literal["assessed", "insufficient_coverage"]
CriterionStatus = Literal["within_tolerance", "outside_tolerance", "not_assessed"]
ScreenStatus = Literal["pass", "fail", "not_assessed"]

DEFAULT_SLOPE_THRESHOLDS = [5.0, 10.0, 15.0, 20.0, 25.0]


# ---------------------------------------------------------------- requests


class BBox(BaseModel):
    """Bounding box. `crs` says what the numbers mean.

    geographic: longitude/latitude in degrees on the dataset's own body.
    native:     the raster's own coordinate system (use for lunar polar grids in metres).
    """

    west: float
    south: float
    east: float
    north: float
    crs: Literal["geographic", "native"] = "geographic"

    @model_validator(mode="after")
    def _ordered(self) -> "BBox":
        if self.east <= self.west or self.north <= self.south:
            raise ValueError("bbox must satisfy west < east and south < north")
        if self.crs == "geographic" and not (-90 <= self.south and self.north <= 90):
            raise ValueError("geographic bbox latitudes must be within [-90, 90]")
        return self


class DatasetRef(BaseModel):
    """Either a registry `id` (see GET /v1/datasets) or raster `uri`/`uris` from Layer 2."""

    id: str | None = None
    uri: str | None = None
    uris: list[str] | None = None
    name: str | None = None
    body: Body = "earth"
    vertical_scale: float = Field(1.0, description="Multiply stored raster values by this to get metres (e.g. 1000 for km).")

    @model_validator(mode="after")
    def _one_source(self) -> "DatasetRef":
        if sum(x is not None for x in (self.id, self.uri, self.uris)) != 1:
            raise ValueError("give exactly one of: id, uri, uris")
        return self


class PatchRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"dataset": {"id": "copernicus-glo30"}, "bbox": {"west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62}, "scales_m": [30, 60]}]}}

    dataset: DatasetRef
    bbox: BBox | None = Field(None, description="Omit to use the whole raster (single-file datasets only, e.g. a stored lunar site).")
    scales_m: list[float] | None = Field(None, description="Analysis grid spacings in metres. Default: 30/60/120/240 where supported.")
    relief_windows_m: list[float] = [300.0, 1000.0]
    slope_thresholds_deg: list[float] = DEFAULT_SLOPE_THRESHOLDS
    min_coverage: float = Field(0.9, ge=0, le=1)
    include_landcover: bool = Field(False, description="Earth only: add ESA WorldCover class fractions.")


class Tolerances(BaseModel):
    """Screening tolerances. Adjustable assumptions, not validated mission thresholds."""

    slope_mean_deg: float = 3.0
    slope_median_deg: float = 3.0
    slope_p90_deg: float = 5.0
    slope_fraction_abs: float = 0.10
    slope_distribution_deg: float = 3.0
    rms_slope_deg: float = 3.0
    roughness_rel: float = 0.5
    relief_rel: float = 0.5


class Range(BaseModel):
    min: float | None = None
    max: float | None = None


class FractionSteeperRule(BaseModel):
    threshold_deg: float = 15.0
    range: Range = Range(max=0.2)


class LandCoverRule(BaseModel):
    """Fail a patch when excluded ESA WorldCover classes cover too much of it."""

    excluded_classes: list[int] = [10, 40, 50, 70, 80, 90, 95]
    max_excluded_fraction: float = Field(0.2, ge=0, le=1)


class ScreeningCriteria(BaseModel):
    slope_mean_deg: Range | None = None
    slope_median_deg: Range | None = None
    slope_p90_deg: Range | None = None
    fraction_steeper_than: FractionSteeperRule | None = None
    roughness_rms_height_m: Range | None = None
    relief_m: Range | None = None
    min_coverage: float = Field(0.9, ge=0, le=1)
    landcover: LandCoverRule | None = None


class ScreenRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"dataset": {"id": "copernicus-glo30"}, "bbox": {"west": -111.75, "south": 35.5, "east": -111.55, "north": 35.65}, "patch_size_m": 3000, "criteria": {"slope_mean_deg": {"max": 8}}}]}}

    dataset: DatasetRef
    bbox: BBox | None = Field(None, description="Omit to use the whole raster (single-file datasets only, e.g. a stored lunar site).")
    patch_size_m: float = Field(3000.0, gt=0)
    scale_m: float | None = Field(None, description="Analysis grid spacing. Default: the finest supported common scale (30 m for GLO-30).")
    criteria: ScreeningCriteria = ScreeningCriteria()
    reference_profile: "TerrainProfile | None" = Field(None, description="If given, slope/roughness ranges not set in `criteria` are derived from it.")
    tolerances: Tolerances = Tolerances()
    include_rejected: bool = True


class OverlayRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"dataset": {"id": "copernicus-glo30"}, "bbox": {"west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62}, "layer": "hillshade", "sun_azimuth_deg": 120, "sun_elevation_deg": 7}]}}

    dataset: DatasetRef
    bbox: BBox | None = Field(None, description="Omit to use the whole raster (single-file datasets only, e.g. a stored lunar site).")
    layer: Literal["slope", "hillshade", "elevation"] = "slope"
    scale_m: float | None = None
    sun_azimuth_deg: float = 315.0
    sun_elevation_deg: float = 45.0
    slope_max_deg: float = 40.0


class CompareRequest(BaseModel):
    """Give each side as a ready profile or as a patch request to compute."""

    model_config = {"json_schema_extra": {"examples": [{"reference": {"dataset": {"id": "copernicus-glo30"}, "bbox": {"west": -111.67, "south": 35.55, "east": -111.59, "north": 35.62}}, "candidate": {"dataset": {"id": "copernicus-glo30"}, "bbox": {"west": -115.56, "south": 32.9, "east": -115.48, "north": 32.97}}, "scales_m": [30, 60]}]}}

    reference: PatchRequest | None = None
    reference_profile: "TerrainProfile | None" = None
    candidate: PatchRequest | None = None
    candidate_profile: "TerrainProfile | None" = None
    scales_m: list[float] | None = Field(None, description="Overrides scales of both patch requests so the sides share scales.")
    tolerances: Tolerances = Tolerances()

    @model_validator(mode="after")
    def _both_sides(self) -> "CompareRequest":
        for side in ("reference", "candidate"):
            if (getattr(self, side) is None) == (getattr(self, f"{side}_profile") is None):
                raise ValueError(f"give exactly one of {side} or {side}_profile")
        return self


# ---------------------------------------------------------------- responses


class Stats(BaseModel):
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    p10: float | None = None
    p25: float | None = None
    p75: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None
    min: float | None = None
    max: float | None = None
    n_valid: int = 0


class Histogram(BaseModel):
    bin_edges_deg: list[float]
    fractions: list[float]


class SlopeMetrics(BaseModel):
    unit: Literal["degrees"] = "degrees"
    baseline_m: float = Field(description="Horizontal distance the 3x3 slope kernel spans (2 x grid spacing).")
    stats: Stats
    rms_slope_deg: float | None
    fraction_steeper_than: dict[str, float] = Field(description="Key is the threshold in degrees.")
    histogram: Histogram


class RoughnessMetrics(BaseModel):
    unit: Literal["metres"] = "metres"
    window_m: float = Field(description="Side of the moving window the surface is detrended over.")
    rms_height_m: Stats
    tri_m: Stats = Field(description="Terrain Ruggedness Index (Riley et al. 1999).")


class ScaleMetrics(BaseModel):
    scale_m: float
    status: Status
    coverage_fraction: float
    grid_shape: list[int]
    slope: SlopeMetrics | None = None
    roughness: RoughnessMetrics | None = None


class ReliefMetrics(BaseModel):
    window_m: float
    grid_m: float
    unit: Literal["metres"] = "metres"
    stats: Stats


class SkippedItem(BaseModel):
    item: str
    code: str
    reason: str


class Coverage(BaseModel):
    valid_fraction: float
    min_required: float
    sufficient: bool
    largest_void_fraction: float
    missing_sources: list[str] = []


class ElevationSummary(BaseModel):
    unit: Literal["metres"] = "metres"
    min: float | None
    max: float | None
    mean: float | None
    std: float | None
    range: float | None


class LandCoverClass(BaseModel):
    code: int
    label: str
    fraction: float


class LandCoverSummary(BaseModel):
    dataset: str
    valid_fraction: float
    classes: list[LandCoverClass]
    dominant_class: int | None
    excluded_fraction: float | None = None
    screen: ScreenStatus = "not_assessed"
    reason: str | None = None


class PatchInfo(BaseModel):
    body: Body
    bbox: BBox
    center_lon: float
    center_lat: float
    polygon_lonlat: list[list[float]] = Field(description="Closed ring of the analysed footprint, [lon, lat].")
    width_m: float
    height_m: float
    area_km2: float


class Provenance(BaseModel):
    dataset_id: str | None
    dataset_name: str
    sources: list[str]
    citation: str | None = None
    native_crs: str
    native_pixel_size_m: float
    working_crs: str
    working_pixel_size_m: float
    resampling: str
    vertical_unit: str = "metres (as stored in the source raster)"
    methods: dict[str, str]
    engine_version: str
    generated_at: str


class TerrainProfile(BaseModel):
    patch: PatchInfo
    provenance: Provenance
    coverage: Coverage
    elevation: ElevationSummary
    scales: list[ScaleMetrics]
    relief: list[ReliefMetrics]
    landcover: LandCoverSummary | None = None
    skipped: list[SkippedItem] = Field([], description="Requested items that could not be computed, with the reason.")
    limitations: list[str]


class CriterionResult(BaseModel):
    metric: str
    scale_m: float | None
    unit: str
    reference: float | None
    candidate: float | None
    difference: float | None = Field(description="candidate - reference (or a distance, for distributions).")
    tolerance: float | None
    tolerance_kind: Literal["absolute", "relative"]
    normalized_difference: float | None = Field(description="|difference| / allowed difference. <= 1 means within tolerance.")
    status: CriterionStatus
    reason: str | None = None


class ComparisonResult(BaseModel):
    common_scales_m: list[float]
    criteria: list[CriterionResult]
    counts: dict[str, int] = Field(description="Number of criteria per status. Deliberately not a score.")
    notes: list[str]
    tolerances: Tolerances
    reference_profile: TerrainProfile
    candidate_profile: TerrainProfile


class OverlayResponse(BaseModel):
    layer: str
    media_type: Literal["image/png"] = "image/png"
    image_base64: str
    coordinates: list[list[float]] = Field(description="[lon, lat] of top-left, top-right, bottom-right, bottom-left (MapLibre image source order).")
    width: int
    height: int
    scale_m: float
    value_range: list[float]
    unit: str
    legend: list[dict[str, Any]]
    provenance: Provenance


class DatasetInfo(BaseModel):
    id: str
    name: str
    body: Body
    kind: Literal["elevation", "landcover"]
    nominal_resolution_m: float
    coverage: str
    citation: str
    license: str


ScreenRequest.model_rebuild()
CompareRequest.model_rebuild()
