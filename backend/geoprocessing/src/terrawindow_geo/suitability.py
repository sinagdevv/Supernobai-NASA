"""Explainable Layer 5 mission assessment over Layer 3 and Layer 4 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import ceil, isclose, isfinite
from collections.abc import Sequence
from typing import Any, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from .models import Body, BBox, PatchRequest, TerrainProfile

CriterionStatus = Literal[
    "PASS", "FAIL", "UNVERIFIED", "INDETERMINATE", "NOT_ASSESSED"
]
AssessmentStatus = Literal[
    "SUITABLE", "NOT_SUITABLE", "INDETERMINATE", "PARTIALLY_ASSESSED"
]
SpatialAssociationStatus = Literal[
    "MATCHED_METADATA_UNVERIFIED", "MISMATCHED", "UNPAIRED"
]
EvidenceTrustStatus = Literal[
    "SERVER_COMPUTED", "UNVERIFIED_EXTERNAL", "NOT_SUPPLIED"
]
EvidenceState = Literal[
    "PASS", "FAIL", "NOT_RUN", "NOT_AVAILABLE", "NOT_VALIDATED", "PARTIAL"
]
MissingDataBehavior = Literal["INDETERMINATE", "NOT_ASSESSED"]


@dataclass(frozen=True)
class MetricSpec:
    source_layer: Literal["layer3", "layer4"]
    unit: str
    description: str
    selectors: tuple[str, ...] = ()


METRICS: dict[str, MetricSpec] = {
    "terrain.coverage.valid_fraction": MetricSpec(
        "layer3", "fraction", "Fraction of valid elevation cells in the patch."
    ),
    "terrain.landcover.valid_fraction": MetricSpec(
        "layer3", "fraction", "Fraction of the patch with valid land-cover classification."
    ),
    "terrain.elevation.min_m": MetricSpec(
        "layer3", "metres", "Minimum valid source elevation; datum is source-specific."
    ),
    "terrain.elevation.max_m": MetricSpec(
        "layer3", "metres", "Maximum valid source elevation; datum is source-specific."
    ),
    "terrain.elevation.mean_m": MetricSpec(
        "layer3", "metres", "Mean valid source elevation; datum is source-specific."
    ),
    "terrain.elevation.range_m": MetricSpec(
        "layer3", "metres", "Maximum minus minimum valid source elevation."
    ),
    "terrain.slope.mean_deg": MetricSpec(
        "layer3", "degrees", "Mean Horn slope in degrees at the selected grid scale.", ("scale_m",)
    ),
    "terrain.slope.median_deg": MetricSpec(
        "layer3", "degrees", "Median Horn slope in degrees at the selected grid scale.", ("scale_m",)
    ),
    "terrain.slope.p90_deg": MetricSpec(
        "layer3", "degrees", "90th-percentile Horn slope at the selected grid scale.", ("scale_m",)
    ),
    "terrain.slope.max_deg": MetricSpec(
        "layer3", "degrees", "Maximum Horn slope at the selected grid scale.", ("scale_m",)
    ),
    "terrain.slope.rms_slope_deg": MetricSpec(
        "layer3", "degrees", "RMS slope at the selected grid scale.", ("scale_m",)
    ),
    "terrain.slope.fraction_steeper_than": MetricSpec(
        "layer3",
        "fraction",
        "Fraction of finite slope cells exceeding the selected threshold.",
        ("scale_m", "threshold_deg"),
    ),
    "terrain.roughness.rms_height_median_m": MetricSpec(
        "layer3",
        "metres",
        "Median moving-window detrended RMS height at the selected grid scale.",
        ("scale_m",),
    ),
    "terrain.roughness.tri_median_m": MetricSpec(
        "layer3",
        "metres",
        "Median Terrain Ruggedness Index at the selected grid scale.",
        ("scale_m",),
    ),
    "terrain.relief.median_m": MetricSpec(
        "layer3",
        "metres",
        "Median local relief for the selected window size.",
        ("window_m",),
    ),
    "terrain.landcover.excluded_fraction": MetricSpec(
        "layer3",
        "fraction",
        "Excluded WorldCover fraction computed with Layer 3's default land-cover rule.",
    ),
    "rehearsal.total_illumination_duration_seconds": MetricSpec(
        "layer4", "seconds", "Layer 4 total target-cell illumination duration."
    ),
    "rehearsal.total_qualifying_illumination_duration_seconds": MetricSpec(
        "layer4", "seconds", "Layer 4 qualifying target-cell illumination duration."
    ),
    "rehearsal.candidate_window_count": MetricSpec(
        "layer4", "count", "Number of Layer 4 candidate rehearsal windows."
    ),
    "rehearsal.maximum_candidate_window_duration_seconds": MetricSpec(
        "layer4", "seconds", "Longest existing Layer 4 candidate-window duration."
    ),
    "rehearsal.valid_terrain_coverage_mean_percent": MetricSpec(
        "layer4", "percent", "Layer 4 mean valid-surface coverage."
    ),
    "rehearsal.measured_terrain_coverage_mean_percent": MetricSpec(
        "layer4",
        "percent",
        "Layer 4 mean measured-observation terrain coverage, when available.",
    ),
    "rehearsal.observation_coverage_availability_mean_percent": MetricSpec(
        "layer4",
        "percent",
        "Layer 4 mean availability of observation-count evidence.",
    ),
    "rehearsal.terrain_obstruction_max_percent": MetricSpec(
        "layer4", "percent", "Layer 4 maximum terrain-obstruction percentage."
    ),
    "rehearsal.solar_elevation_min_deg": MetricSpec(
        "layer4", "degrees", "Minimum sampled Layer 4 solar elevation."
    ),
    "rehearsal.solar_elevation_max_deg": MetricSpec(
        "layer4", "degrees", "Maximum sampled Layer 4 solar elevation."
    ),
    "rehearsal.step_seconds": MetricSpec(
        "layer4", "seconds", "Layer 4 temporal sampling step."
    ),
}


def metric_catalog() -> list[dict[str, Any]]:
    """Return the supported metric IDs, units, and required selectors."""
    return [
        {
            "id": metric_id,
            "source_layer": spec.source_layer,
            "unit": spec.unit,
            "description": spec.description,
            "selectors": list(spec.selectors),
        }
        for metric_id, spec in METRICS.items()
    ]


class MissionRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = Field(default=None, allow_inf_nan=False)
    max: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("min", "max", mode="before")
    @classmethod
    def _reject_boolean_bounds(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("range bounds must be numeric, not boolean")
        return value

    @model_validator(mode="after")
    def _valid_range(self) -> "MissionRange":
        if self.min is None and self.max is None:
            raise ValueError("target range must set at least one bound")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("target range min must not exceed max")
        return self


class MissionCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    source_layer: Literal["layer3", "layer4"]
    source_metric: str = Field(min_length=1, max_length=100)
    operator: Literal["gt", "gte", "lt", "lte", "eq", "within_range"]
    target_value: float | None = Field(default=None, allow_inf_nan=False)
    target_range: MissionRange | None = None
    equality_tolerance: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=40)
    required: bool
    missing_data_behavior: MissingDataBehavior
    rationale: str = Field(min_length=1, max_length=1000)
    scale_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    window_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    threshold_deg: float | None = Field(
        default=None, ge=0, le=90, allow_inf_nan=False
    )

    @field_validator(
        "target_value",
        "equality_tolerance",
        "scale_m",
        "window_m",
        "threshold_deg",
        mode="before",
    )
    @classmethod
    def _reject_boolean_numbers(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("criterion numeric fields cannot be boolean")
        return value

    @field_validator("name", "category", "description", "unit", "rationale")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _valid_definition(self) -> "MissionCriterion":
        spec = METRICS.get(self.source_metric)
        if spec is None:
            raise ValueError(f"unsupported source_metric: {self.source_metric}")
        if self.source_layer != spec.source_layer:
            raise ValueError(
                f"{self.source_metric} belongs to {spec.source_layer}, not {self.source_layer}"
            )
        if self.unit != spec.unit:
            raise ValueError(
                f"{self.source_metric} requires unit '{spec.unit}', not '{self.unit}'"
            )
        selectors = {
            "scale_m": self.scale_m,
            "window_m": self.window_m,
            "threshold_deg": self.threshold_deg,
        }
        for selector, value in selectors.items():
            if (selector in spec.selectors) != (value is not None):
                requirement = "requires" if selector in spec.selectors else "does not use"
                raise ValueError(f"{self.source_metric} {requirement} {selector}")
        if self.operator == "within_range":
            if self.target_range is None or self.target_value is not None:
                raise ValueError(
                    "within_range requires target_range and forbids target_value"
                )
        elif self.target_value is None or self.target_range is not None:
            raise ValueError(
                "comparison operators other than within_range require target_value only"
            )
        if self.operator == "eq":
            if self.equality_tolerance is None:
                raise ValueError("eq requires an explicit equality_tolerance in the metric unit")
        elif self.equality_tolerance is not None:
            raise ValueError("equality_tolerance is only valid with eq")
        return self


class MissionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    criteria: list[MissionCriterion] = Field(min_length=1, max_length=100)
    required_categories: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Mission dimensions that must have required criteria before suitability can be concluded.",
    )

    @field_validator("name", "description")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _unique_criteria(self) -> "MissionProfile":
        ids = [criterion.id for criterion in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("criterion IDs must be unique within a mission profile")
        categories = [category.strip() for category in self.required_categories]
        if any(not category for category in categories):
            raise ValueError("required_categories must not contain blank names")
        if len(set(categories)) != len(categories):
            raise ValueError("required_categories must be unique")
        missing = [
            category
            for category in categories
            if not any(
                criterion.required and criterion.category == category
                for criterion in self.criteria
            )
        ]
        if missing:
            raise ValueError(
                "each required category must contain at least one required criterion: "
                + ", ".join(missing)
            )
        self.required_categories = categories
        return self


class Layer4WindowInput(BaseModel):
    """The subset of a serialized Layer 4 window needed by mission criteria."""

    model_config = ConfigDict(extra="allow")

    start_utc: datetime
    end_utc: datetime
    duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    is_candidate: bool
    sample_count: StrictInt | None = Field(default=None, ge=1)
    criteria_satisfied: list[str] | None = None
    criteria_failed: list[str] | None = None

    @field_validator("start_utc", "end_utc")
    @classmethod
    def _utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Layer 4 timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _reject_boolean_duration(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Layer 4 duration must be numeric, not boolean")
        return value

    @model_validator(mode="after")
    def _ordered(self) -> "Layer4WindowInput":
        if self.end_utc <= self.start_utc:
            raise ValueError("Layer 4 window end must be later than its start")
        elapsed = (self.end_utc - self.start_utc).total_seconds()
        if not isclose(self.duration_seconds, elapsed, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("Layer 4 window duration must match its timestamp bounds")
        if (self.criteria_satisfied is None) != (self.criteria_failed is None):
            raise ValueError("Layer 4 window must provide both criteria lists or neither")
        if self.criteria_satisfied is not None and self.criteria_failed is not None:
            if set(self.criteria_satisfied) & set(self.criteria_failed):
                raise ValueError("Layer 4 window criteria cannot be both satisfied and failed")
            if self.is_candidate != (not self.criteria_failed):
                raise ValueError("Layer 4 candidate flag must match its failed-criteria list")
        return self


class Layer4ObservationInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    time_utc: datetime
    interval_end_utc: datetime
    target_classification: Literal[
        "ILLUMINATED",
        "TERRAIN_OBSTRUCTED",
        "SURFACE_FACING_AWAY",
        "INSUFFICIENT_COVERAGE",
        "UNKNOWN",
        "NO_DATA",
    ]
    target_ray_status: str | None = None
    target_surface_valid: bool = False
    target_elevation_valid: bool = False
    target_observation_coverage_status: str = "UNAVAILABLE"
    target_observation_count: StrictInt | None = None

    @field_validator("time_utc", "interval_end_utc")
    @classmethod
    def _utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Layer 4 observation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _ordered_interval(self) -> "Layer4ObservationInput":
        if self.interval_end_utc <= self.time_utc:
            raise ValueError("Layer 4 observation interval end must follow its time")
        if self.target_observation_count is not None and self.target_observation_count < 0:
            raise ValueError("Layer 4 target observation count must be nonnegative")
        return self


class Layer4EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    implementation_status: EvidenceState
    synthetic_verification_status: EvidenceState
    real_terrain_execution_status: EvidenceState
    observational_validation_status: EvidenceState
    details: dict[str, str] = Field(default_factory=dict)


class Layer4TemporalInput(BaseModel):
    """Validated serialized Layer 4 output; no Layer 4 calculation is performed."""

    model_config = ConfigDict(extra="allow")

    body: Body
    start_utc: datetime
    end_utc: datetime
    step_seconds: float = Field(gt=0, allow_inf_nan=False)
    boundary_uncertainty_seconds: float = Field(ge=0, allow_inf_nan=False)
    target_pixel: tuple[StrictInt, StrictInt]
    observations: list[Layer4ObservationInput]
    continuous_illumination_intervals: list[Layer4WindowInput]
    candidate_windows: list[Layer4WindowInput]
    total_illumination_duration_seconds: float = Field(ge=0, allow_inf_nan=False)
    total_qualifying_illumination_duration_seconds: float = Field(
        ge=0, allow_inf_nan=False
    )
    target_classification_durations_seconds: dict[str, float] | None = None
    criteria: dict[str, Any]
    provenance: dict[str, Any]
    scientific_limitations: list[str]
    kernel_identities: list[dict[str, Any]]
    evidence: Layer4EvidenceInput

    valid_terrain_coverage_mean_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    measured_terrain_coverage_mean_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    observation_coverage_availability_mean_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    terrain_obstruction_max_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    valid_terrain_coverage_min_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    solar_elevation_min_deg: float | None = Field(
        default=None, ge=-90, le=90, allow_inf_nan=False
    )
    solar_elevation_max_deg: float | None = Field(
        default=None, ge=-90, le=90, allow_inf_nan=False
    )
    source_grid_id: str | None = None
    source_row: StrictInt | None = Field(default=None, ge=0)
    source_column: StrictInt | None = Field(default=None, ge=0)
    target_longitude_deg: float | None = Field(
        default=None, ge=-360, le=360, allow_inf_nan=False
    )
    target_latitude_deg: float | None = Field(
        default=None, ge=-90, le=90, allow_inf_nan=False
    )
    target_coordinate_frame: str | None = None

    @field_validator("target_classification_durations_seconds", mode="before")
    @classmethod
    def _valid_classification_durations(cls, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("target classification durations must be an object")
        normalized = {}
        for name, duration in value.items():
            if not isinstance(name, str) or isinstance(duration, bool):
                raise ValueError(
                    "target classification durations need string names and numeric values"
                )
            try:
                number = float(duration)
            except (TypeError, ValueError):
                raise ValueError(
                    "target classification durations must be numeric"
                ) from None
            if not isfinite(number) or number < 0:
                raise ValueError(
                    "target classification durations must have finite nonnegative values"
                )
            normalized[name] = number
        return normalized

    @field_validator("start_utc", "end_utc")
    @classmethod
    def _utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Layer 4 timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator(
        "step_seconds",
        "boundary_uncertainty_seconds",
        "total_illumination_duration_seconds",
        "total_qualifying_illumination_duration_seconds",
        "valid_terrain_coverage_mean_percent",
        "measured_terrain_coverage_mean_percent",
        "observation_coverage_availability_mean_percent",
        "terrain_obstruction_max_percent",
        "valid_terrain_coverage_min_percent",
        "target_longitude_deg",
        "target_latitude_deg",
        "solar_elevation_min_deg",
        "solar_elevation_max_deg",
        mode="before",
    )
    @classmethod
    def _reject_boolean_numbers(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Layer 4 numeric fields cannot be boolean")
        return value

    @model_validator(mode="after")
    def _valid_interval(self) -> "Layer4TemporalInput":
        if self.end_utc <= self.start_utc:
            raise ValueError("Layer 4 result end must be later than its start")
        total_seconds = (self.end_utc - self.start_utc).total_seconds()
        tolerance = 1e-6
        if not isclose(
            self.boundary_uncertainty_seconds,
            self.step_seconds,
            rel_tol=1e-9,
            abs_tol=tolerance,
        ):
            raise ValueError(
                "Layer 4 boundary uncertainty must equal its sampling step"
            )
        if (
            self.solar_elevation_min_deg is not None
            and self.solar_elevation_max_deg is not None
            and self.solar_elevation_min_deg > self.solar_elevation_max_deg
        ):
            raise ValueError("Layer 4 solar elevation minimum must not exceed its maximum")
        if (self.source_row is None) != (self.source_column is None):
            raise ValueError("Layer 4 source row and column must be supplied together")
        if self.source_row is not None and not self.source_grid_id:
            raise ValueError("Layer 4 source indices require a source_grid_id")
        if (self.target_longitude_deg is None) != (self.target_latitude_deg is None):
            raise ValueError("Layer 4 target longitude and latitude must be supplied together")
        if self.target_longitude_deg is not None and not self.target_coordinate_frame:
            raise ValueError("Layer 4 target coordinates require a coordinate frame")
        if any(coordinate < 0 for coordinate in self.target_pixel):
            raise ValueError("Layer 4 target_pixel values must be nonnegative integers")
        if not self.observations:
            raise ValueError("Layer 4 result must contain at least one observation")
        expected_observation_count = ceil(
            total_seconds / self.step_seconds - 1e-12
        )
        if len(self.observations) != expected_observation_count:
            raise ValueError(
                "Layer 4 observation count must match the declared interval and sampling step"
            )
        previous_end = self.start_utc
        for index, observation in enumerate(self.observations):
            if observation.time_utc != previous_end:
                raise ValueError(
                    "Layer 4 observations must cover the interval contiguously from start_utc"
                )
            if observation.interval_end_utc > self.end_utc:
                raise ValueError("Layer 4 observations must lie within the result interval")
            duration = (
                observation.interval_end_utc - observation.time_utc
            ).total_seconds()
            expected_duration = min(
                self.step_seconds,
                total_seconds - index * self.step_seconds,
            )
            if not isclose(duration, expected_duration, rel_tol=1e-9, abs_tol=tolerance):
                raise ValueError(
                    "Layer 4 observation interval duration must match its sampling step"
                )
            previous_end = observation.interval_end_utc
        if previous_end != self.end_utc:
            raise ValueError("Layer 4 observations must cover the result through end_utc")
        for window in (*self.continuous_illumination_intervals, *self.candidate_windows):
            if window.start_utc < self.start_utc or window.end_utc > self.end_utc:
                raise ValueError("Layer 4 windows must lie within the result interval")
            if window.sample_count is not None:
                covered = [
                    observation
                    for observation in self.observations
                    if observation.time_utc >= window.start_utc
                    and observation.interval_end_utc <= window.end_utc
                ]
                if window.sample_count != len(covered):
                    raise ValueError("Layer 4 window sample_count does not match its observations")
        if any(window.is_candidate is not True for window in self.candidate_windows):
            raise ValueError("candidate_windows may contain only candidate windows")
        continuous_bounds = {
            (window.start_utc, window.end_utc)
            for window in self.continuous_illumination_intervals
        }
        if any(
            (window.start_utc, window.end_utc) not in continuous_bounds
            for window in self.candidate_windows
        ):
            raise ValueError("Layer 4 candidate windows must be continuous intervals")
        expected_runs: list[tuple[datetime, datetime, float, int]] = []
        run: list[Layer4ObservationInput] = []
        for observation in self.observations:
            if observation.target_classification == "ILLUMINATED":
                run.append(observation)
            elif run:
                expected_runs.append(
                    (
                        run[0].time_utc,
                        run[-1].interval_end_utc,
                        sum(
                            (item.interval_end_utc - item.time_utc).total_seconds()
                            for item in run
                        ),
                        len(run),
                    )
                )
                run = []
        if run:
            expected_runs.append(
                (
                    run[0].time_utc,
                    run[-1].interval_end_utc,
                    sum(
                        (item.interval_end_utc - item.time_utc).total_seconds()
                        for item in run
                    ),
                    len(run),
                )
            )
        if len(expected_runs) != len(self.continuous_illumination_intervals):
            raise ValueError(
                "Layer 4 continuous intervals must match contiguous illuminated observations"
            )
        for expected, window in zip(
            expected_runs, self.continuous_illumination_intervals
        ):
            if (
                window.start_utc != expected[0]
                or window.end_utc != expected[1]
                or not isclose(
                    window.duration_seconds,
                    expected[2],
                    rel_tol=1e-9,
                    abs_tol=tolerance,
                )
                or (window.sample_count is not None and window.sample_count != expected[3])
            ):
                raise ValueError(
                    "Layer 4 continuous interval does not match its illuminated observations"
                )
        expected_candidates = Counter(
            (window.start_utc, window.end_utc)
            for window in self.continuous_illumination_intervals
            if window.is_candidate
        )
        actual_candidates = Counter(
            (window.start_utc, window.end_utc) for window in self.candidate_windows
        )
        if expected_candidates != actual_candidates:
            raise ValueError(
                "Layer 4 candidate_windows must match all intervals marked as candidates"
            )
        illuminated_duration = sum(
            (observation.interval_end_utc - observation.time_utc).total_seconds()
            for observation in self.observations
            if observation.target_classification == "ILLUMINATED"
        )
        if not isclose(
            self.total_illumination_duration_seconds,
            illuminated_duration,
            rel_tol=1e-9,
            abs_tol=tolerance,
        ):
            raise ValueError(
                "Layer 4 total illumination duration must match illuminated observations"
            )
        if self.target_classification_durations_seconds is not None:
            classification_durations: Counter[str] = Counter()
            for observation in self.observations:
                classification_durations[observation.target_classification] += (
                    observation.interval_end_utc - observation.time_utc
                ).total_seconds()
            if set(self.target_classification_durations_seconds) != set(
                classification_durations
            ) or any(
                not isclose(
                    self.target_classification_durations_seconds[key],
                    value,
                    rel_tol=1e-9,
                    abs_tol=tolerance,
                )
                for key, value in classification_durations.items()
            ):
                raise ValueError(
                    "Layer 4 target classification durations must match observations"
                )
        if abs(
            self.total_illumination_duration_seconds
            - sum(
                window.duration_seconds
                for window in self.continuous_illumination_intervals
            )
        ) > max(1e-6, self.total_illumination_duration_seconds * 1e-9):
            raise ValueError("Layer 4 total illumination duration does not match its intervals")
        if abs(
            self.total_qualifying_illumination_duration_seconds
            - sum(window.duration_seconds for window in self.candidate_windows)
        ) > max(1e-6, self.total_qualifying_illumination_duration_seconds * 1e-9):
            raise ValueError("Layer 4 qualifying duration does not match its candidate windows")
        if (
            self.total_qualifying_illumination_duration_seconds
            > self.total_illumination_duration_seconds + 1e-6
        ):
            raise ValueError("Layer 4 qualifying duration cannot exceed total illumination duration")
        try:
            json.dumps(self.model_dump(mode="json"), allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError(
                "Layer 4 result must contain only finite JSON-compatible values"
            ) from None
        return self


class Layer5AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    candidate_name: str | None = Field(default=None, max_length=160)
    candidate: PatchRequest
    mission_profile: MissionProfile
    layer4_result: Layer4TemporalInput | None = None

    @model_validator(mode="before")
    @classmethod
    def _unwrap_layer4_handoff(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        handoff = value.get("layer4_result")
        if not isinstance(handoff, dict) or not {
            "selected_body",
            "layer4_result",
        }.issubset(handoff):
            return value
        temporal_result = handoff["layer4_result"]
        if not isinstance(temporal_result, dict):
            raise ValueError("Layer 4 handoff layer4_result must be an object")
        if handoff["selected_body"] != temporal_result.get("body"):
            raise ValueError("Layer 4 selected_body must match its result body")
        normalized = dict(value)
        normalized["layer4_result"] = temporal_result
        return normalized


class CandidateIdentity(BaseModel):
    id: str
    name: str | None
    body: Body
    dataset_id: str | None
    bbox: BBox
    center_lon: float
    center_lat: float
    area_km2: float
    patch_identity_sha256: str | None = None


class SpatialAssociation(BaseModel):
    status: SpatialAssociationStatus
    candidate_patch_identity_sha256: str | None
    checks: dict[str, str]
    limitations: list[str]


class EvidenceRecord(BaseModel):
    evidence_id: str
    source_layer: Literal["layer3", "layer4"]
    source_identity: str
    source_metric: str
    value: float | None
    claimed_value: float | None = None
    unit: str
    evidence_status: Literal["AVAILABLE", "UNAVAILABLE"]
    trust_status: EvidenceTrustStatus
    spatial_association_status: str
    execution_status: str
    data_status: str
    scientific_validation_status: str
    timestamp_utc: datetime | None = None
    interval_start_utc: datetime | None = None
    interval_end_utc: datetime | None = None
    provenance: dict[str, Any]
    quality: dict[str, Any]
    uncertainty: float | None = None
    limitations: list[str]


class CriterionAssessment(BaseModel):
    criterion_id: str
    name: str
    category: str
    description: str
    rationale: str
    source_layer: str
    source_metric: str
    scale_m: float | None = None
    window_m: float | None = None
    threshold_deg: float | None = None
    required: bool
    status: CriterionStatus
    measured_value: float | None
    claimed_value: float | None = None
    unit: str
    operator: str
    target_value: float | None = None
    target_range: MissionRange | None = None
    equality_tolerance: float | None = None
    evidence_id: str
    explanation: str


class SuitabilityGap(BaseModel):
    id: str
    category: str
    source_layer: str | None
    affected_criteria: list[str]
    description: str
    assessment_effect: str
    additional_evidence_needed: str


class MissionAssessment(BaseModel):
    assessment_id: str
    candidate: CandidateIdentity
    mission_profile_id: str
    mission_profile_name: str
    mission_profile_description: str
    assessed_at_utc: datetime
    overall_status: AssessmentStatus
    overall_explanation: str
    profile_completeness: dict[str, Any]
    spatial_association: SpatialAssociation | None = None
    criterion_results: list[CriterionAssessment]
    evidence: list[EvidenceRecord]
    suitability_gaps: list[SuitabilityGap]
    layer3_provenance: dict[str, Any]
    layer4_provenance: dict[str, Any] | None
    uncertainty_and_limitations: list[str]


def _l3_identity(profile: TerrainProfile) -> str:
    return _l3_patch_identity(profile) or (
        profile.provenance.dataset_id or profile.provenance.dataset_name or "Layer 3 profile"
    )


def _l3_patch_identity(profile: TerrainProfile) -> str | None:
    patch = profile.patch
    if not patch.grid_shape or not patch.grid_transform or not patch.grid_crs_wkt:
        return None
    payload = {
        "body": patch.body,
        "dataset_id": profile.provenance.dataset_id,
        "dataset_version": profile.provenance.dataset_version,
        "sources": profile.provenance.sources,
        "grid_shape": patch.grid_shape,
        "grid_transform": patch.grid_transform,
        "grid_crs_wkt": patch.grid_crs_wkt,
        "vertical_scale_applied": profile.provenance.vertical_scale_applied,
        "source_vertical_reference": profile.provenance.source_vertical_reference,
        "valid_fraction": profile.coverage.valid_fraction,
        "valid_cell_count": profile.coverage.valid_cell_count,
        "total_cell_count": profile.coverage.total_cell_count,
        "minimum_required_valid_fraction": profile.coverage.min_required,
        "missing_sources": profile.coverage.missing_sources,
        "landcover_valid_cell_count": (
            profile.landcover.valid_cell_count if profile.landcover else None
        ),
        "landcover_total_cell_count": (
            profile.landcover.total_cell_count if profile.landcover else None
        ),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _affine6(values: Sequence[float] | None) -> tuple[float, ...] | None:
    """Six affine coefficients; a 9-value row-major matrix is accepted only when its last row is (0, 0, 1)."""
    if values is None:
        return None
    values = tuple(values)
    if len(values) == 9 and tuple(values[6:]) == (0.0, 0.0, 1.0):
        return values[:6]
    return values if len(values) == 6 else None


def _same_crs(left: str | None, right: str | None) -> bool | None:
    """True/False when both WKT strings parse; None when either is missing or unreadable."""
    if not left or not right:
        return None
    if left == right:
        return True
    try:
        from pyproj import CRS

        return CRS.from_wkt(left) == CRS.from_wkt(right)
    except Exception:
        return None


def _layer4_affine(result: Layer4TemporalInput) -> tuple[float, ...] | None:
    raw = result.provenance.get("affine_transform")
    if raw is None:
        raw = result.provenance.get("transform")
    try:
        if isinstance(raw, str):
            values = tuple(float(value.strip()) for value in raw.split(","))
        elif isinstance(raw, (tuple, list)):
            values = tuple(float(value) for value in raw)
        else:
            return None
    except (TypeError, ValueError):
        return None
    if len(values) not in (6, 9) or not all(isfinite(value) for value in values):
        return None
    return values


def _source_tokens(values: Any) -> set[str]:
    if isinstance(values, str):
        raw = values.split(";")
    elif isinstance(values, (tuple, list)):
        raw = [str(value) for value in values]
    else:
        return set()
    return {value.strip() for value in raw if value.strip()}


def _spatial_association(
    profile: TerrainProfile, result: Layer4TemporalInput | None
) -> SpatialAssociation | None:
    if result is None:
        return None
    patch_identity = _l3_patch_identity(profile)
    checks: dict[str, str] = {}
    limitations = [
        "Layer 4 metadata is caller-supplied and is not authenticated by this API."
    ]

    grid_shape = profile.patch.grid_shape
    if grid_shape and len(grid_shape) == 2:
        row, column = result.target_pixel
        checks["target_pixel_in_candidate_grid"] = (
            "MATCH"
            if 0 <= row < grid_shape[0] and 0 <= column < grid_shape[1]
            else "MISMATCH"
        )
    else:
        checks["target_pixel_in_candidate_grid"] = "UNAVAILABLE"

    candidate_crs = profile.patch.grid_crs_wkt
    layer4_crs = result.provenance.get("working_crs_wkt")
    same_crs = _same_crs(candidate_crs, layer4_crs)
    checks["working_crs"] = "UNAVAILABLE" if same_crs is None else "MATCH" if same_crs else "MISMATCH"

    candidate_transform = _affine6(profile.patch.grid_transform)
    layer4_transform = _affine6(_layer4_affine(result))
    checks["affine_transform"] = (
        "MATCH"
        if candidate_transform
        and layer4_transform
        and len(candidate_transform) == len(layer4_transform)
        and all(
            isclose(left, right, rel_tol=1e-12, abs_tol=1e-9)
            for left, right in zip(candidate_transform, layer4_transform)
        )
        else "MISMATCH"
        if candidate_transform and layer4_transform
        else "UNAVAILABLE"
    )

    candidate_sources = _source_tokens(profile.provenance.sources)
    if profile.provenance.dataset_id:
        candidate_sources.add(profile.provenance.dataset_id)
    layer4_sources = set()
    for key in ("dataset_id", "source_dataset_id", "source.dataset_id", "terrain_sources"):
        layer4_sources.update(_source_tokens(result.provenance.get(key)))
    if not layer4_sources:
        layer4_sources.update(_source_tokens(result.provenance.get("sources")))
    checks["source_identity"] = (
        "MATCH"
        if candidate_sources == layer4_sources and candidate_sources
        else "MISMATCH"
        if candidate_sources and layer4_sources
        else "UNAVAILABLE"
    )

    candidate_version = profile.provenance.dataset_version
    layer4_version = result.provenance.get(
        "dataset_version", result.provenance.get("source_version")
    )
    checks["dataset_version"] = (
        "MATCH"
        if candidate_version and layer4_version == candidate_version
        else "MISMATCH"
        if candidate_version and layer4_version
        else "UNAVAILABLE"
    )

    candidate_vertical_reference = profile.provenance.source_vertical_reference
    layer4_vertical_reference = result.provenance.get(
        "vertical_reference", result.provenance.get("elevation_reference")
    )
    checks["vertical_reference"] = (
        "MATCH"
        if candidate_vertical_reference
        and layer4_vertical_reference == candidate_vertical_reference
        else "MISMATCH"
        if candidate_vertical_reference and layer4_vertical_reference
        else "UNAVAILABLE"
    )

    candidate_vertical_scale = profile.provenance.vertical_scale_applied
    layer4_vertical_scale = result.provenance.get("vertical_scale_applied")
    if layer4_vertical_scale is not None:
        try:
            scale_matches = isclose(
                float(layer4_vertical_scale),
                candidate_vertical_scale,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        except (TypeError, ValueError):
            scale_matches = False
        checks["vertical_scale"] = "MATCH" if scale_matches else "MISMATCH"
    elif candidate_vertical_scale != 1.0:
        checks["vertical_scale"] = "UNAVAILABLE"
    else:
        checks["vertical_scale"] = "UNAVAILABLE"

    pixel_claim = result.provenance.get("solar_geometry_pixel")
    if pixel_claim is not None:
        try:
            claimed_pixel = tuple(int(value.strip()) for value in str(pixel_claim).split(","))
        except ValueError:
            claimed_pixel = ()
        checks["target_pixel_claim"] = (
            "MATCH" if claimed_pixel == result.target_pixel else "MISMATCH"
        )

    if "MISMATCH" in checks.values():
        status: SpatialAssociationStatus = "MISMATCHED"
        limitations.append(
            "Layer 4 grid, source, or target-pixel metadata conflicts with the Layer 3 candidate."
        )
    elif all(
        checks.get(name) == "MATCH"
        for name in (
            "target_pixel_in_candidate_grid",
            "working_crs",
            "affine_transform",
            "source_identity",
        )
    ) and all(
        checks.get(name) == "MATCH"
        for name, candidate_value in (
            ("dataset_version", candidate_version),
            ("vertical_reference", candidate_vertical_reference),
        )
        if candidate_value is not None
    ) and (
        candidate_vertical_scale == 1.0
        or checks.get("vertical_scale") == "MATCH"
    ):
        status = "MATCHED_METADATA_UNVERIFIED"
        limitations.append(
            "The supplied source, CRS, affine transform, and pixel metadata match the candidate; "
            "the match is not authenticated and does not establish source-content identity."
        )
    else:
        status = "UNPAIRED"
        limitations.append(
            "The available metadata cannot establish that the Layer 4 target is on the Layer 3 candidate grid."
        )
        limitations.append(
            "No coordinate transformation or body-fixed-frame equivalence is inferred from numeric coordinates."
        )
    return SpatialAssociation(
        status=status,
        candidate_patch_identity_sha256=patch_identity,
        checks=checks,
        limitations=limitations,
    )


def _select_scale(profile: TerrainProfile, scale_m: float):
    return next(
        (
            scale
            for scale in profile.scales
            if abs(scale.scale_m - scale_m) <= max(1e-6, scale_m * 1e-6)
        ),
        None,
    )


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _count_fraction(valid_count: int | None, total_count: int | None) -> float | None:
    if valid_count is None or total_count is None or total_count <= 0:
        return None
    return valid_count / total_count


def _read_layer3(
    criterion: MissionCriterion, profile: TerrainProfile
) -> tuple[float | None, str | None, dict[str, Any]]:
    metric = criterion.source_metric
    valid_fraction = _count_fraction(
        profile.coverage.valid_cell_count, profile.coverage.total_cell_count
    )
    quality: dict[str, Any] = {
        "valid_fraction": (
            valid_fraction
            if valid_fraction is not None
            else profile.coverage.valid_fraction
        ),
        "valid_cell_count": profile.coverage.valid_cell_count,
        "total_cell_count": profile.coverage.total_cell_count,
        "minimum_required_valid_fraction": profile.coverage.min_required,
        "coverage_sufficient": profile.coverage.sufficient,
    }

    if metric == "terrain.coverage.valid_fraction":
        exact_fraction = _count_fraction(
            profile.coverage.valid_cell_count, profile.coverage.total_cell_count
        )
        return (
            exact_fraction
            if exact_fraction is not None
            else profile.coverage.valid_fraction,
            None,
            quality,
        )

    if metric == "terrain.landcover.valid_fraction":
        if profile.landcover is None:
            return None, "Layer 3 did not compute land-cover coverage for this profile.", quality
        quality.update(
            {
                "landcover_valid_cell_count": profile.landcover.valid_cell_count,
                "landcover_total_cell_count": profile.landcover.total_cell_count,
                "landcover_valid_fraction": _count_fraction(
                    profile.landcover.valid_cell_count,
                    profile.landcover.total_cell_count,
                )
                if profile.landcover.valid_cell_count is not None
                and profile.landcover.total_cell_count
                else profile.landcover.valid_fraction,
            }
        )
        exact_fraction = _count_fraction(
            profile.landcover.valid_cell_count,
            profile.landcover.total_cell_count,
        )
        return (
            exact_fraction
            if exact_fraction is not None
            else profile.landcover.valid_fraction,
            None,
            quality,
        )

    if metric.startswith("terrain.elevation."):
        if not profile.coverage.sufficient:
            return (
                None,
                "Layer 3 elevation summaries use valid cells only; the candidate coverage requirement is not met.",
                quality,
            )
        key = metric.rsplit(".", 1)[1]
        field_name = {"min_m": "min", "max_m": "max", "mean_m": "mean", "range_m": "range"}[key]
        return _number(getattr(profile.elevation, field_name)), None, quality

    if metric == "terrain.landcover.excluded_fraction":
        if profile.landcover is None:
            return None, "Layer 3 did not compute land-cover fractions for this profile.", quality
        quality["landcover_dataset"] = profile.landcover.dataset
        quality["landcover_valid_fraction"] = _count_fraction(
            profile.landcover.valid_cell_count,
            profile.landcover.total_cell_count,
        ) or profile.landcover.valid_fraction
        quality["landcover_valid_cell_count"] = profile.landcover.valid_cell_count
        quality["landcover_total_cell_count"] = profile.landcover.total_cell_count
        quality["landcover_excluded_cell_count"] = (
            profile.landcover.excluded_cell_count
        )
        quality["landcover_screen_status"] = profile.landcover.screen
        landcover_fraction = _count_fraction(
            profile.landcover.valid_cell_count,
            profile.landcover.total_cell_count,
        )
        if landcover_fraction is None or landcover_fraction < profile.coverage.min_required:
            return (
                None,
                "Land-cover excluded fraction is not representative because valid classification coverage is below the configured minimum.",
                quality,
            )
        if (
            profile.landcover.excluded_cell_count is not None
            and profile.landcover.valid_cell_count
        ):
            excluded_fraction = (
                profile.landcover.excluded_cell_count
                / profile.landcover.valid_cell_count
            )
            return excluded_fraction, None, quality
        if profile.landcover.excluded_fraction is None:
            return None, profile.landcover.reason or "Excluded land-cover fraction is unavailable.", quality
        return profile.landcover.excluded_fraction, None, quality

    if not profile.coverage.sufficient:
        return (
            None,
            "The configured Layer 3 elevation coverage requirement is not met.",
            quality,
        )

    if metric.startswith("terrain.slope.") or metric.startswith("terrain.roughness."):
        if criterion.scale_m is None:
            raise ValueError(f"{metric} requires scale_m")
        scale = _select_scale(profile, criterion.scale_m)
        if scale is None:
            available = [item.scale_m for item in profile.scales]
            return (
                None,
                f"Layer 3 did not return the requested {criterion.scale_m:g} m scale; available scales are {available}.",
                quality,
            )
        quality["scale_m"] = scale.scale_m
        quality["scale_status"] = scale.status
        quality["scale_coverage_fraction"] = scale.coverage_fraction
        if scale.status != "assessed":
            return None, f"Layer 3 marked the {scale.scale_m:g} m scale as {scale.status}.", quality
        if metric.startswith("terrain.slope."):
            if scale.slope is None:
                return None, "Layer 3 slope metrics are unavailable at this scale.", quality
            quality["sample_count"] = scale.slope.stats.n_valid
            quality["sample_grid_cells"] = (
                scale.grid_shape[0] * scale.grid_shape[1]
            )
            key = metric.rsplit(".", 1)[1]
            if key == "fraction_steeper_than":
                if criterion.threshold_deg is None:
                    raise ValueError(f"{metric} requires threshold_deg")
                if scale.slope.stats.n_valid == 0:
                    return (
                        None,
                        "Layer 3 has no valid slope samples at this scale.",
                        quality,
                    )
                threshold_key = f"{criterion.threshold_deg:g}"
                value = scale.slope.fraction_steeper_than.get(threshold_key)
                if value is None:
                    return (
                        None,
                        f"Layer 3 did not compute the requested slope threshold {threshold_key} degrees.",
                        quality,
                    )
                quality["threshold_deg"] = criterion.threshold_deg
                return value, None, quality
            if key == "rms_slope_deg":
                return _number(scale.slope.rms_slope_deg), None, quality
            stats_key = {
                "mean_deg": "mean",
                "median_deg": "median",
                "p90_deg": "p90",
                "max_deg": "max",
            }[key]
            return _number(getattr(scale.slope.stats, stats_key)), None, quality

        if scale.roughness is None:
            return None, "Layer 3 roughness metrics are unavailable at this scale.", quality
        key = metric.rsplit(".", 1)[1]
        stats = (
            scale.roughness.rms_height_m
            if key == "rms_height_median_m"
            else scale.roughness.tri_m
        )
        quality["sample_count"] = stats.n_valid
        quality["sample_grid_cells"] = (
            scale.grid_shape[0] * scale.grid_shape[1]
        )
        return _number(stats.median), None, quality

    if metric == "terrain.relief.median_m":
        if criterion.window_m is None:
            raise ValueError(f"{metric} requires window_m")
        relief = next(
            (
                item
                for item in profile.relief
                if abs(item.window_m - criterion.window_m)
                <= max(1e-6, criterion.window_m * 1e-6)
            ),
            None,
        )
        if relief is None:
            available = [item.window_m for item in profile.relief]
            return (
                None,
                f"Layer 3 did not return the requested {criterion.window_m:g} m relief window; available windows are {available}.",
                quality,
            )
        quality["window_m"] = relief.window_m
        quality["sample_count"] = relief.stats.n_valid
        quality["sample_grid_cells"] = (
            profile.patch.grid_shape[0] * profile.patch.grid_shape[1]
            if profile.patch.grid_shape
            else None
        )
        return _number(relief.stats.median), None, quality

    raise ValueError(f"Metric is not implemented: {metric}")


def _layer4_identity(result: Layer4TemporalInput) -> str:
    payload = json.dumps(
        result.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _layer4_quality(result: Layer4TemporalInput) -> dict[str, Any]:
    return {
        "trust_status": "UNVERIFIED_EXTERNAL",
        "implementation_status": result.evidence.implementation_status,
        "synthetic_verification_status": result.evidence.synthetic_verification_status,
        "real_terrain_execution_status": result.evidence.real_terrain_execution_status,
        "observational_validation_status": result.evidence.observational_validation_status,
        "target_pixel": list(result.target_pixel),
        "source_grid_id": result.source_grid_id,
        "source_row": result.source_row,
        "source_column": result.source_column,
        "target_longitude_deg": result.target_longitude_deg,
        "target_latitude_deg": result.target_latitude_deg,
        "target_coordinate_frame": result.target_coordinate_frame,
        "target_observation_count": len(result.observations),
        "target_classification_counts": dict(
            Counter(
                observation.target_classification
                for observation in result.observations
            )
        ),
        "target_ray_status_counts": dict(
            Counter(
                observation.target_ray_status
                for observation in result.observations
                if observation.target_ray_status is not None
            )
        ),
        "target_surface_valid_observation_count": sum(
            observation.target_surface_valid for observation in result.observations
        ),
        "target_elevation_valid_observation_count": sum(
            observation.target_elevation_valid for observation in result.observations
        ),
        "target_observation_coverage_status_counts": dict(
            Counter(
                observation.target_observation_coverage_status
                for observation in result.observations
            )
        ),
        "window_criteria_claims_status": "UNVERIFIED_EXTERNAL",
        "window_criteria_claims_note": (
            "Per-window criteria results are caller-supplied. When both per-window "
            "criteria lists are supplied, Layer 5 checks local candidate-flag "
            "consistency but does not recompute results against the top-level "
            "criteria configuration."
        ),
        "claimed_observational_validation_status": (
            result.evidence.observational_validation_status
        ),
        "boundary_uncertainty_seconds": result.boundary_uncertainty_seconds,
    }


def _layer4_claimed_value(
    criterion: MissionCriterion, result: Layer4TemporalInput
) -> float | None:
    metric = criterion.source_metric
    if metric == "rehearsal.total_illumination_duration_seconds":
        value = result.total_illumination_duration_seconds
    elif metric == "rehearsal.total_qualifying_illumination_duration_seconds":
        value = result.total_qualifying_illumination_duration_seconds
    elif metric == "rehearsal.candidate_window_count":
        value = float(len(result.candidate_windows))
    elif metric == "rehearsal.maximum_candidate_window_duration_seconds":
        value = (
            max(window.duration_seconds for window in result.candidate_windows)
            if result.candidate_windows
            else None
        )
    elif metric == "rehearsal.valid_terrain_coverage_mean_percent":
        value = result.valid_terrain_coverage_mean_percent
    elif metric == "rehearsal.measured_terrain_coverage_mean_percent":
        value = result.measured_terrain_coverage_mean_percent
    elif metric == "rehearsal.observation_coverage_availability_mean_percent":
        value = result.observation_coverage_availability_mean_percent
    elif metric == "rehearsal.terrain_obstruction_max_percent":
        value = result.terrain_obstruction_max_percent
    elif metric == "rehearsal.solar_elevation_min_deg":
        value = result.solar_elevation_min_deg
    elif metric == "rehearsal.solar_elevation_max_deg":
        value = result.solar_elevation_max_deg
    elif metric == "rehearsal.step_seconds":
        value = result.step_seconds
    else:
        raise ValueError(f"Metric is not implemented: {metric}")
    return _number(value)


def _read_layer4(
    criterion: MissionCriterion,
    result: Layer4TemporalInput | None,
    result_identity: str | None,
    quality: dict[str, Any],
    spatial_association: SpatialAssociation | None,
) -> tuple[float | None, str | None, str, dict[str, Any]]:
    if result is None or result_identity is None:
        return None, "No serialized Layer 4 temporal result was supplied.", "NOT_RUN", {}
    supplied_quality = dict(quality)
    claimed_value = _layer4_claimed_value(criterion, result)
    supplied_quality["claimed_metric_value"] = claimed_value
    supplied_quality["spatial_association_status"] = (
        spatial_association.status if spatial_association else "UNPAIRED"
    )
    if claimed_value is None:
        supplied_quality["claimed_metric_status"] = "UNAVAILABLE"
    else:
        supplied_quality["claimed_metric_status"] = "UNVERIFIED_EXTERNAL"

    if (
        spatial_association is None
        or spatial_association.status == "UNPAIRED"
        or spatial_association.status == "MISMATCHED"
    ):
        return (
            None,
            "The Layer 4 result has no verified spatial association with this Layer 3 candidate; "
            "any supplied metric remains an unpaired external claim.",
            "NOT_ASSESSED",
            supplied_quality,
        )
    if claimed_value is None:
        reason = (
            "Layer 4 did not provide a finite value for this metric; unavailable coverage "
            "is not interpreted as zero."
        )
        return None, reason, "UNVERIFIED_EXTERNAL", supplied_quality
    return (
        None,
        "The Layer 4 metric is structurally paired by matching metadata but remains an unverified external claim.",
        "UNVERIFIED_EXTERNAL",
        supplied_quality,
    )


def _compare(criterion: MissionCriterion, value: float) -> bool:
    if criterion.operator != "within_range":
        target_value = criterion.target_value
        if target_value is None:
            raise ValueError(f"{criterion.operator} requires target_value")
        if criterion.operator == "gt":
            return value > target_value
        if criterion.operator == "gte":
            return value >= target_value
        if criterion.operator == "lt":
            return value < target_value
        if criterion.operator == "lte":
            return value <= target_value
        if criterion.operator == "eq":
            tolerance = criterion.equality_tolerance
            if tolerance is None:
                raise ValueError("eq requires an explicit equality_tolerance")
            return abs(value - target_value) <= tolerance
    target = criterion.target_range
    if target is None:
        raise ValueError("within_range requires target_range")
    return (target.min is None or value >= target.min) and (
        target.max is None or value <= target.max
    )


def _target_text(criterion: MissionCriterion) -> str:
    if criterion.operator == "within_range":
        if criterion.target_range is None:
            raise ValueError("within_range requires target_range")
        return (
            f"within [{criterion.target_range.min}, {criterion.target_range.max}] "
            f"{criterion.unit}, inclusive"
        )
    labels = {
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "eq": "==",
    }
    if criterion.operator == "eq":
        return (
            f"== {criterion.target_value} {criterion.unit} "
            f"within ±{criterion.equality_tolerance} {criterion.unit}"
        )
    return f"{labels[criterion.operator]} {criterion.target_value} {criterion.unit}"


def _criterion_assessment(
    criterion: MissionCriterion,
    profile: TerrainProfile,
    layer4_result: Layer4TemporalInput | None,
    layer4_identity: str | None,
    layer4_quality: dict[str, Any],
    spatial_association: SpatialAssociation | None,
    assessment_id: str,
) -> tuple[CriterionAssessment, EvidenceRecord]:
    spec = METRICS[criterion.source_metric]
    if spec.source_layer == "layer3":
        value, unavailable_reason, quality = _read_layer3(criterion, profile)
        source_identity = _l3_identity(profile)
        execution_status = "PASS"
        scientific_validation_status = "NOT_REPORTED"
        trust_status: EvidenceTrustStatus = "SERVER_COMPUTED"
        spatial_status = "NOT_APPLICABLE"
        claimed_value = None
        timestamp = profile.provenance.generated_at
        interval_start = interval_end = None
        provenance = profile.provenance.model_dump(mode="json")
        limitations = list(profile.limitations)
    else:
        value, unavailable_reason, execution_status, quality = _read_layer4(
            criterion,
            layer4_result,
            layer4_identity,
            layer4_quality,
            spatial_association,
        )
        source_identity = layer4_identity or "Layer 4 result not supplied"
        trust_status = (
            "UNVERIFIED_EXTERNAL"
            if layer4_result is not None
            else "NOT_SUPPLIED"
        )
        spatial_status = (
            spatial_association.status if spatial_association else "UNPAIRED"
        )
        claimed_value = quality.get("claimed_metric_value")
        scientific_validation_status = (
            "UNVERIFIED_EXTERNAL" if layer4_result is not None else "NOT_REPORTED"
        )
        if claimed_value is not None:
            quality["claimed_criterion_comparison"] = (
                "PASS" if _compare(criterion, claimed_value) else "FAIL"
            )
        timestamp = None
        interval_start = layer4_result.start_utc if layer4_result else None
        interval_end = layer4_result.end_utc if layer4_result else None
        provenance = (
            {
                "payload_identity_sha256": layer4_identity,
                "result_provenance": layer4_result.provenance,
                "kernel_identities": layer4_result.kernel_identities,
                "claimed_evidence_status": layer4_result.evidence.model_dump(
                    mode="json"
                ),
                "spatial_association": (
                    spatial_association.model_dump(mode="json")
                    if spatial_association
                    else None
                ),
            }
            if layer4_result
            else {}
        )
        limitations = (
            list(layer4_result.scientific_limitations) if layer4_result else []
        )

    if value is not None and not isfinite(value):
        value = None
        unavailable_reason = "Source metric was not finite."
    data_status = "AVAILABLE" if value is not None else "UNAVAILABLE"
    evidence_status = "AVAILABLE" if value is not None else "UNAVAILABLE"
    evidence_id = f"{assessment_id}:evidence:{criterion.id}"
    evidence = EvidenceRecord(
        evidence_id=evidence_id,
        source_layer=criterion.source_layer,
        source_identity=source_identity,
        source_metric=criterion.source_metric,
        value=value,
        claimed_value=claimed_value,
        unit=criterion.unit,
        evidence_status=evidence_status,
        trust_status=trust_status,
        spatial_association_status=spatial_status,
        execution_status=execution_status,
        data_status=data_status,
        scientific_validation_status=scientific_validation_status,
        timestamp_utc=timestamp,
        interval_start_utc=interval_start,
        interval_end_utc=interval_end,
        provenance=provenance,
        quality=quality,
        uncertainty=None,
        limitations=limitations,
    )

    if value is None:
        if execution_status == "NOT_ASSESSED":
            status = "NOT_ASSESSED"
            explanation = unavailable_reason or "Evidence was not spatially associated."
        elif execution_status == "UNVERIFIED_EXTERNAL" and claimed_value is not None:
            status = "UNVERIFIED"
            explanation = (
                f"Layer 4 claims {claimed_value} {criterion.unit}; "
                f"its configured comparison is {quality['claimed_criterion_comparison']}, "
                "but the claim is not independently verified."
            )
        else:
            status = criterion.missing_data_behavior
            explanation = (
                f"{unavailable_reason or 'The source value is unavailable'} "
                f"Configured missing-data behavior: {status}."
            )
    else:
        passed = _compare(criterion, value)
        status = "PASS" if passed else "FAIL"
        explanation = (
            f"Measured {value} {criterion.unit}; required {_target_text(criterion)}. "
            f"Criterion {status}."
        )

    result = CriterionAssessment(
        criterion_id=criterion.id,
        name=criterion.name,
        category=criterion.category,
        description=criterion.description,
        rationale=criterion.rationale,
        source_layer=criterion.source_layer,
        source_metric=criterion.source_metric,
        scale_m=criterion.scale_m,
        window_m=criterion.window_m,
        threshold_deg=criterion.threshold_deg,
        required=criterion.required,
        status=status,
        measured_value=value,
        claimed_value=claimed_value,
        unit=criterion.unit,
        operator=criterion.operator,
        target_value=criterion.target_value,
        target_range=criterion.target_range,
        equality_tolerance=criterion.equality_tolerance,
        evidence_id=evidence_id,
        explanation=explanation,
    )
    return result, evidence


def _profile_completeness(
    required_categories: list[str], results: list[CriterionAssessment]
) -> dict[str, Any]:
    if not required_categories:
        return {
            "status": "NOT_CONFIGURED",
            "required_categories": [],
            "category_statuses": {},
            "note": "No universal mission profile is defined; the caller must declare mission-specific required categories.",
        }

    category_statuses: dict[str, str] = {}
    for category in required_categories:
        required_results = [
            result
            for result in results
            if result.category == category and result.required
        ]
        statuses = {result.status for result in required_results}
        if "FAIL" in statuses:
            category_statuses[category] = "FAIL"
        elif "UNVERIFIED" in statuses:
            category_statuses[category] = "UNVERIFIED"
        elif "INDETERMINATE" in statuses:
            category_statuses[category] = "INDETERMINATE"
        elif "NOT_ASSESSED" in statuses:
            category_statuses[category] = "NOT_ASSESSED"
        else:
            category_statuses[category] = "PASS"
    complete_statuses = {"PASS", "FAIL"}
    return {
        "status": (
            "COMPLETE"
            if all(status in complete_statuses for status in category_statuses.values())
            else "INCOMPLETE"
        ),
        "required_categories": required_categories,
        "category_statuses": category_statuses,
        "note": "Completeness categories are mission-profile declarations, not a universal rover-suitability standard.",
    }


def _overall_status(
    results: list[CriterionAssessment],
    profile: TerrainProfile,
    layer4_result: Layer4TemporalInput | None,
    required_categories: list[str],
) -> tuple[AssessmentStatus, str]:
    required = [result for result in results if result.required]
    failed_required = [result for result in required if result.status == "FAIL"]
    unresolved_required = [
        result
        for result in required
        if result.status in ("UNVERIFIED", "INDETERMINATE", "NOT_ASSESSED")
    ]
    unresolved_optional = [
        result
        for result in results
        if not result.required and result.status != "PASS"
    ]

    if failed_required:
        ids = ", ".join(result.criterion_id for result in failed_required)
        return "NOT_SUITABLE", f"Required criterion failure(s): {ids}."
    if unresolved_required:
        ids = ", ".join(result.criterion_id for result in unresolved_required)
        return (
            "INDETERMINATE",
            f"Required criterion evidence is incomplete for: {ids}; suitability cannot be concluded.",
        )
    if not required:
        return (
            "PARTIALLY_ASSESSED",
            "No required criteria were configured; optional checks alone do not establish suitability.",
        )
    if unresolved_optional:
        ids = ", ".join(result.criterion_id for result in unresolved_optional)
        return (
            "PARTIALLY_ASSESSED",
            f"All required criteria passed, but optional criterion(s) remain unresolved or failed: {ids}.",
        )
    if not required_categories:
        return (
            "PARTIALLY_ASSESSED",
            "The mission profile does not declare required completeness categories; passing configured criteria alone cannot establish suitability.",
        )
    if not profile.coverage.sufficient:
        return (
            "PARTIALLY_ASSESSED",
            "All configured criteria passed, but Layer 3 reports insufficient patch coverage.",
        )
    layer4_criteria = [result for result in results if result.source_layer == "layer4"]
    if layer4_criteria and layer4_result is not None:
        return (
            "PARTIALLY_ASSESSED",
            "Layer 4 claims remain external and unverified; they cannot support a definitive suitability result.",
        )
    return (
        "SUITABLE",
        "Every required and optional criterion passed using the configured evidence; this is not a safety or operational-readiness finding.",
    )


def assess_mission(
    request: Layer5AssessmentRequest,
    profile: TerrainProfile,
    *,
    assessed_at: datetime | None = None,
) -> MissionAssessment:
    """Assess one candidate against an explicit mission profile and existing Layer 4 data."""
    assessment_time = assessed_at or datetime.now(timezone.utc)
    if assessment_time.tzinfo is None or assessment_time.utcoffset() is None:
        raise ValueError("assessed_at must be timezone-aware")
    assessment_time = assessment_time.astimezone(timezone.utc)
    if request.layer4_result is not None and request.layer4_result.body != profile.patch.body:
        raise ValueError(
            "Layer 4 body does not match the body of the Layer 3 candidate profile"
        )

    assessment_id = str(uuid4())
    l4_identity = (
        _layer4_identity(request.layer4_result)
        if request.layer4_result is not None
        else None
    )
    l4_quality = (
        _layer4_quality(request.layer4_result)
        if request.layer4_result is not None
        else {}
    )
    spatial_association = _spatial_association(profile, request.layer4_result)
    results: list[CriterionAssessment] = []
    evidence: list[EvidenceRecord] = []
    for criterion in request.mission_profile.criteria:
        result, record = _criterion_assessment(
            criterion,
            profile,
            request.layer4_result,
            l4_identity,
            l4_quality,
            spatial_association,
            assessment_id,
        )
        results.append(result)
        evidence.append(record)

    completeness = _profile_completeness(
        request.mission_profile.required_categories, results
    )
    status, explanation = _overall_status(
        results,
        profile,
        request.layer4_result,
        request.mission_profile.required_categories,
    )
    gaps: list[SuitabilityGap] = []
    for result in results:
        if result.status in ("INDETERMINATE", "NOT_ASSESSED"):
            gaps.append(
                SuitabilityGap(
                    id=f"criterion-evidence-{result.criterion_id}",
                    category="unavailable_measurement",
                    source_layer=result.source_layer,
                    affected_criteria=[result.criterion_id],
                    description=result.explanation,
                    assessment_effect=(
                        "This criterion has no measured value and cannot be treated as zero or as a failure."
                    ),
                    additional_evidence_needed=(
                        f"Provide valid {result.source_layer} evidence for {result.source_metric}."
                    ),
                )
            )

    if not profile.coverage.sufficient:
        gaps.append(
            SuitabilityGap(
                id="layer3-insufficient-patch-coverage",
                category="insufficient_spatial_coverage",
                source_layer="layer3",
                affected_criteria=[
                    result.criterion_id
                    for result in results
                    if result.source_layer == "layer3"
                ],
                description=(
                    f"Layer 3 valid fraction {profile.coverage.valid_fraction:.4f} is below "
                    f"its requested minimum {profile.coverage.min_required:.4f}; Layer 5 withholds dependent metrics."
                ),
                assessment_effect=(
                    "Unsupported elevation, morphology, and relief summaries are not used to produce definitive criterion results."
                ),
                additional_evidence_needed=(
                    "Provide a better-covered patch or choose a scientifically justified coverage requirement."
                ),
            )
        )

    if (
        profile.landcover is not None
        and profile.landcover.valid_fraction < profile.coverage.min_required
        and any(
            result.source_metric == "terrain.landcover.excluded_fraction"
            for result in results
        )
    ):
        gaps.append(
            SuitabilityGap(
                id="layer3-insufficient-landcover-coverage",
                category="insufficient_data_coverage",
                source_layer="layer3",
                affected_criteria=[
                    result.criterion_id
                    for result in results
                    if result.source_metric == "terrain.landcover.excluded_fraction"
                ],
                description=(
                    f"WorldCover validity {profile.landcover.valid_fraction:.4f} is below "
                    f"the configured minimum {profile.coverage.min_required:.4f}."
                ),
                assessment_effect=(
                    "The excluded fraction is withheld because its valid-classification denominator "
                    "does not adequately cover the candidate."
                ),
                additional_evidence_needed=(
                    "Provide adequate land-cover classification coverage or reassess using a justified coverage minimum."
                ),
            )
        )

    if not request.mission_profile.required_categories:
        gaps.append(
            SuitabilityGap(
                id="mission-profile-completeness-not-configured",
                category="incomplete_mission_profile",
                source_layer=None,
                affected_criteria=[],
                description=(
                    "The mission profile does not declare which categories are essential."
                ),
                assessment_effect=(
                    "Passing configured criteria cannot produce SUITABLE without an explicit completeness declaration."
                ),
                additional_evidence_needed=(
                    "Declare the mission-specific required_categories and include at least one required criterion in each."
                ),
            )
        )

    for skipped in profile.skipped:
        affected = [
            result.criterion_id
            for result in results
            if (
                skipped.item == "landcover"
                and result.source_metric == "terrain.landcover.excluded_fraction"
            )
            or (
                result.scale_m is not None
                and skipped.item == f"scale {result.scale_m:g} m"
                and result.source_metric.startswith(
                    ("terrain.slope.", "terrain.roughness.")
                )
            )
            or (
                result.window_m is not None
                and skipped.item == f"relief window {result.window_m:g} m"
                and result.source_metric == "terrain.relief.median_m"
            )
        ]
        if not affected:
            continue
        gaps.append(
            SuitabilityGap(
                id=f"layer3-skipped-{len(gaps) + 1}",
                category="metric_not_computed",
                source_layer="layer3",
                affected_criteria=affected,
                description=f"{skipped.item}: {skipped.reason}",
                assessment_effect="The skipped Layer 3 product is not available as assessment evidence.",
                additional_evidence_needed=(
                    "Supply a compatible patch or request parameters that allow the metric to be computed."
                ),
            )
        )

    uses_layer4 = any(result.source_layer == "layer4" for result in results)
    if uses_layer4 and request.layer4_result is not None:
        association_status = (
            spatial_association.status if spatial_association else "UNPAIRED"
        )
        if association_status != "MATCHED_METADATA_UNVERIFIED":
            gaps.append(
                SuitabilityGap(
                    id="layer4-spatial-association",
                    category="unpaired_spatial_evidence",
                    source_layer="layer4",
                    affected_criteria=[
                        result.criterion_id
                        for result in results
                        if result.source_layer == "layer4"
                    ],
                    description=(
                        "Layer 4 target metadata cannot establish a shared candidate grid "
                        f"(association status: {association_status})."
                    ),
                    assessment_effect=(
                        "Layer 4 claimed metrics are retained for inspection but are NOT_ASSESSED "
                        "and do not enter criterion comparisons."
                    ),
                    additional_evidence_needed=(
                        "Provide a Layer 4 result whose source identity, CRS, affine transform, "
                        "and target pixel match the Layer 3 candidate grid."
                    ),
                )
            )
        gaps.append(
            SuitabilityGap(
                id="layer4-external-evidence-trust",
                category="unverified_external_evidence",
                source_layer="layer4",
                affected_criteria=[
                    result.criterion_id
                    for result in results
                    if result.source_layer == "layer4"
                ],
                description=(
                    "Layer 4 JSON, execution statuses, kernel identities, and observational "
                    "validation status are caller-supplied and not authenticated."
                ),
                assessment_effect=(
                    "Metadata-matched Layer 4 values are reported as UNVERIFIED and cannot "
                    "support definitive PASS, FAIL, SUITABLE, or NOT_SUITABLE findings."
                ),
                additional_evidence_needed=(
                    "Use a trusted server-side execution record or verifiable signed evidence "
                    "and an independent validation record."
                ),
            )
        )
        real_execution = request.layer4_result.evidence.real_terrain_execution_status
        if real_execution != "PASS":
            gaps.append(
                SuitabilityGap(
                    id="layer4-real-terrain-execution",
                    category="incomplete_real_terrain_execution",
                    source_layer="layer4",
                    affected_criteria=[
                        result.criterion_id
                        for result in results
                        if result.source_layer == "layer4"
                    ],
                    description=(
                        "Layer 4 claims real_terrain_execution_status="
                        f"{real_execution}; synthetic execution is not a substitute for candidate terrain evidence."
                    ),
                    assessment_effect=(
                        "The claim is retained as unverified metadata; it is not proof of real-terrain execution."
                    ),
                    additional_evidence_needed=(
                        "Provide a Layer 4 result computed on the corresponding real terrain patch."
                    ),
                )
            )
        validation = request.layer4_result.evidence.observational_validation_status
        gaps.append(
            SuitabilityGap(
                id="layer4-observational-validation",
                category="unverified_scientific_validation",
                source_layer="layer4",
                affected_criteria=[
                    result.criterion_id
                    for result in results
                    if result.source_layer == "layer4"
                ],
                description=(
                    "Layer 4 claims observational_validation_status="
                    f"{validation}; the claim is not independently verified."
                ),
                assessment_effect=(
                    "Layer 4 evidence remains unverified regardless of the supplied status."
                ),
                additional_evidence_needed=(
                    "Provide independent observations and a trusted validation record for the relevant geometry and shadow outputs."
                ),
            )
        )

    limitations = list(profile.limitations)
    if request.layer4_result is not None:
        limitations.extend(request.layer4_result.scientific_limitations)
        limitations.append(
            "Layer 4 temporal JSON is supplied by the caller; structural checks do not authenticate its metrics, execution statuses, kernels, or validation claims."
        )
    else:
        limitations.append(
            "No Layer 4 result was supplied; only criteria backed by Layer 3 evidence were assessable."
        )
    if any(result.source_metric.startswith("terrain.elevation.") for result in results):
        limitations.append(
            "Layer 3 elevations are source-datum specific; their values do not imply a common vertical datum across bodies."
        )
    if any(
        result.source_metric.startswith(("terrain.slope.", "terrain.roughness.", "terrain.relief."))
        for result in results
    ):
        limitations.append(
            "Terrain metrics at their stated spatial scales do not establish rover-scale obstacle safety, soil strength, or mobility."
        )
    limitations = list(dict.fromkeys(limitations))

    candidate = CandidateIdentity(
        id=request.candidate_id,
        name=request.candidate_name,
        body=profile.patch.body,
        dataset_id=profile.provenance.dataset_id,
        bbox=profile.patch.bbox,
        center_lon=profile.patch.center_lon,
        center_lat=profile.patch.center_lat,
        area_km2=profile.patch.area_km2,
        patch_identity_sha256=_l3_patch_identity(profile),
    )
    layer4_provenance = (
        {
            "payload_identity_sha256": l4_identity,
            "trust_status": "UNVERIFIED_EXTERNAL",
            "window_criteria_claims_status": "UNVERIFIED_EXTERNAL",
            "spatial_association": (
                spatial_association.model_dump(mode="json")
                if spatial_association
                else None
            ),
            "body": request.layer4_result.body,
            "start_utc": request.layer4_result.start_utc,
            "end_utc": request.layer4_result.end_utc,
            "step_seconds": request.layer4_result.step_seconds,
            "boundary_uncertainty_seconds": request.layer4_result.boundary_uncertainty_seconds,
            "target_pixel": request.layer4_result.target_pixel,
            "target_classification_counts": l4_quality[
                "target_classification_counts"
            ],
            "target_ray_status_counts": l4_quality["target_ray_status_counts"],
            "source_grid_id": request.layer4_result.source_grid_id,
            "source_row": request.layer4_result.source_row,
            "source_column": request.layer4_result.source_column,
            "target_longitude_deg": request.layer4_result.target_longitude_deg,
            "target_latitude_deg": request.layer4_result.target_latitude_deg,
            "target_coordinate_frame": request.layer4_result.target_coordinate_frame,
            "provenance": request.layer4_result.provenance,
            "kernel_identities": request.layer4_result.kernel_identities,
            "claimed_evidence_status": request.layer4_result.evidence.model_dump(
                mode="json"
            ),
        }
        if request.layer4_result is not None
        else None
    )
    layer3_provenance = profile.provenance.model_dump(mode="json")
    layer3_provenance.update(
        {
            "patch_identity_sha256": _l3_patch_identity(profile),
            "patch_identity_scope": (
                "hash of the Layer 3 analysis-grid and coverage metadata; not a raster-content hash"
            ),
            "grid_shape": profile.patch.grid_shape,
            "grid_transform": profile.patch.grid_transform,
            "grid_crs_wkt": profile.patch.grid_crs_wkt,
            "identity_trust_status": "SERVER_COMPUTED_METADATA_FINGERPRINT",
        }
    )
    return MissionAssessment(
        assessment_id=assessment_id,
        candidate=candidate,
        mission_profile_id=request.mission_profile.id,
        mission_profile_name=request.mission_profile.name,
        mission_profile_description=request.mission_profile.description,
        assessed_at_utc=assessment_time,
        overall_status=status,
        overall_explanation=explanation,
        profile_completeness=completeness,
        spatial_association=spatial_association,
        criterion_results=results,
        evidence=evidence,
        suitability_gaps=gaps,
        layer3_provenance=layer3_provenance,
        layer4_provenance=layer4_provenance,
        uncertainty_and_limitations=limitations,
    )


def suitability_metrics_response() -> dict[str, Any]:
    return {
        "metrics": metric_catalog(),
        "operators": ["gt", "gte", "lt", "lte", "eq", "within_range"],
        "criterion_statuses": [
            "PASS",
            "FAIL",
            "UNVERIFIED",
            "INDETERMINATE",
            "NOT_ASSESSED",
        ],
        "overall_statuses": [
            "SUITABLE",
            "NOT_SUITABLE",
            "INDETERMINATE",
            "PARTIALLY_ASSESSED",
        ],
        "missing_data_behaviors": ["INDETERMINATE", "NOT_ASSESSED"],
        "evidence_trust_statuses": [
            "SERVER_COMPUTED",
            "UNVERIFIED_EXTERNAL",
            "NOT_SUPPLIED",
        ],
        "spatial_association_statuses": [
            "MATCHED_METADATA_UNVERIFIED",
            "MISMATCHED",
            "UNPAIRED",
        ],
        "mission_profile_completeness": (
            "SUITABLE requires a non-empty required_categories declaration and at least "
            "one required criterion in every declared category."
        ),
    }
