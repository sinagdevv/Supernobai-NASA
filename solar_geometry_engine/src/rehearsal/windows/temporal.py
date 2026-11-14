"""Body-neutral temporal aggregation for Layer 4 rehearsal evaluations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Callable, Iterable, Mapping, Sequence

from ..spice_provenance import SpiceKernelIdentity


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def evaluation_intervals(
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
) -> tuple[tuple[datetime, datetime], ...]:
    """Build left-closed, right-open UTC sample intervals ending at end_utc."""
    start = _utc(start_utc, "start_utc")
    end = _utc(end_utc, "end_utc")
    if end <= start:
        raise ValueError("end_utc must be later than start_utc")
    if not isinstance(step, timedelta) or step.total_seconds() <= 0.0:
        raise ValueError("step must be a positive timedelta")

    intervals: list[tuple[datetime, datetime]] = []
    current = start
    while current < end:
        next_time = min(current + step, end)
        intervals.append((current, next_time))
        current = next_time
    return tuple(intervals)


class EvidenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_VALIDATED = "NOT_VALIDATED"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class ScientificEvidence:
    """Structured evidence states; execution is not observational validation."""

    implementation_status: EvidenceStatus = EvidenceStatus.PASS
    synthetic_verification_status: EvidenceStatus = EvidenceStatus.NOT_RUN
    real_terrain_execution_status: EvidenceStatus = EvidenceStatus.NOT_AVAILABLE
    observational_validation_status: EvidenceStatus = EvidenceStatus.NOT_VALIDATED
    details: Mapping[str, str] = field(
        default_factory=lambda: {
            "status_semantics": (
                "Implementation PASS means this temporal evaluation returned successfully; "
                "it does not assert independent correctness or observational accuracy."
            )
        }
    )

    def __post_init__(self) -> None:
        for name in (
            "implementation_status",
            "synthetic_verification_status",
            "real_terrain_execution_status",
            "observational_validation_status",
        ):
            value = getattr(self, name)
            if not isinstance(value, EvidenceStatus):
                try:
                    value = EvidenceStatus(value)
                except ValueError as exc:
                    raise ValueError(f"{name} must be a supported EvidenceStatus") from exc
                object.__setattr__(self, name, value)
        if any(not str(key).strip() or not str(value).strip() for key, value in self.details.items()):
            raise ValueError("evidence details must contain non-empty keys and values")
        object.__setattr__(
            self, "details", {str(key): str(value) for key, value in self.details.items()}
        )


@dataclass(frozen=True)
class RehearsalCriteria:
    """Mission thresholds applied to each continuous target-illumination interval."""

    minimum_continuous_illumination: timedelta = timedelta(0)
    minimum_valid_terrain_coverage_percent: float = 0.0
    solar_elevation_min_deg: float | None = None
    solar_elevation_max_deg: float | None = None
    solar_azimuth_min_deg: float | None = None
    solar_azimuth_max_deg: float | None = None
    maximum_terrain_obstruction_percent: float = 100.0
    additional_condition: Callable[["TemporalObservation"], bool] | None = field(
        default=None, repr=False, compare=False
    )
    additional_condition_name: str = "body-specific condition"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.minimum_continuous_illumination, timedelta)
            or self.minimum_continuous_illumination.total_seconds() < 0.0
        ):
            raise ValueError("minimum_continuous_illumination must be a nonnegative timedelta")
        for name, value in (
            (
                "minimum_valid_terrain_coverage_percent",
                self.minimum_valid_terrain_coverage_percent,
            ),
            (
                "maximum_terrain_obstruction_percent",
                self.maximum_terrain_obstruction_percent,
            ),
        ):
            if not isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be finite and in [0, 100]")
        for name, value in (
            ("solar_elevation_min_deg", self.solar_elevation_min_deg),
            ("solar_elevation_max_deg", self.solar_elevation_max_deg),
        ):
            if value is not None and (not isfinite(value) or not -90.0 <= value <= 90.0):
                raise ValueError(f"{name} must be finite and in [-90, 90]")
        for name, value in (
            ("solar_azimuth_min_deg", self.solar_azimuth_min_deg),
            ("solar_azimuth_max_deg", self.solar_azimuth_max_deg),
        ):
            if value is not None and (not isfinite(value) or not 0.0 <= value <= 360.0):
                raise ValueError(f"{name} must be finite and in [0, 360]")
        if self.additional_condition is not None and not callable(self.additional_condition):
            raise TypeError("additional_condition must be callable or None")
        if not self.additional_condition_name.strip():
            raise ValueError("additional_condition_name must not be empty")


@dataclass(frozen=True)
class TemporalObservation:
    """One epoch's original class distribution and terrain/geometry summaries."""

    time_utc: datetime
    interval_end_utc: datetime
    target_classification: str
    classification_counts: Mapping[str, int]
    ray_status_counts: Mapping[str, int]
    total_cells: int
    valid_terrain_cells: int
    ray_supported_cells: int
    valid_terrain_coverage_percent: float | None
    ray_support_percent_of_valid_terrain: float | None
    illuminated_cells: int
    terrain_obstructed_cells: int
    insufficient_coverage_cells: int
    unknown_cells: int
    no_data_cells: int
    terrain_obstruction_percent: float | None
    solar_elevation_deg: float | None
    solar_azimuth_deg: float | None
    solar_direction_fixed: tuple[float, float, float] | None
    solar_frame: str | None
    sun_distance_km: float | None
    source_dataset_id: str
    source_metadata: Mapping[str, str]
    target_ray_status: str | None = None
    target_ray_status_available: bool = False
    target_surface_valid: bool = False
    target_elevation_valid: bool = False
    target_observation_coverage_status: str = "UNAVAILABLE"
    target_observation_count: int | None = None
    elevation_invalid_cells: int = 0
    surface_invalid_cells: int = 0
    elevation_valid_cells: int = 0
    measured_valid_elevation_cells: int | None = None
    unobserved_valid_elevation_cells: int | None = None
    observation_coverage_unavailable_cells: int = 0
    observation_coverage_availability_percent: float | None = None
    measured_terrain_coverage_percent: float | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.interval_end_utc - self.time_utc).total_seconds()


@dataclass(frozen=True)
class RehearsalWindow:
    """One contiguous interval of target-cell illumination and its criteria result."""

    start_utc: datetime
    end_utc: datetime
    duration_seconds: float
    sample_count: int
    minimum_valid_terrain_coverage_percent: float | None
    mean_valid_terrain_coverage_percent: float | None
    maximum_terrain_obstruction_percent: float | None
    mean_illuminated_terrain_percent: float | None
    solar_elevation_min_deg: float | None
    solar_elevation_max_deg: float | None
    solar_azimuth_start_deg: float | None
    solar_azimuth_end_deg: float | None
    solar_azimuth_span_deg: float | None
    classification_counts: Mapping[str, int]
    ray_status_counts: Mapping[str, int]
    criteria_satisfied: tuple[str, ...]
    criteria_failed: tuple[str, ...]
    is_candidate: bool
    observation_coverage_availability_percent: float | None = None
    measured_terrain_coverage_percent: float | None = None


@dataclass(frozen=True)
class TemporalInterruption:
    """A non-illuminated or unsupported gap between illuminated intervals."""

    start_utc: datetime
    end_utc: datetime
    duration_seconds: float
    target_classification_durations_seconds: Mapping[str, float]


@dataclass(frozen=True)
class RehearsalEvaluation:
    """Layer 5 handoff contract for one selected planetary body."""

    body: str
    start_utc: datetime
    end_utc: datetime
    step_seconds: float
    boundary_uncertainty_seconds: float
    target_pixel: tuple[int, int]
    observations: tuple[TemporalObservation, ...]
    continuous_illumination_intervals: tuple[RehearsalWindow, ...]
    candidate_windows: tuple[RehearsalWindow, ...]
    interruptions: tuple[TemporalInterruption, ...]
    total_illumination_duration_seconds: float
    total_qualifying_illumination_duration_seconds: float
    target_classification_durations_seconds: Mapping[str, float]
    classification_counts: Mapping[str, int]
    ray_status_counts: Mapping[str, int]
    valid_terrain_coverage_min_percent: float | None
    valid_terrain_coverage_mean_percent: float | None
    valid_terrain_coverage_max_percent: float | None
    ray_support_mean_percent_of_valid_terrain: float | None
    terrain_obstruction_mean_percent: float | None
    terrain_obstruction_max_percent: float | None
    solar_elevation_min_deg: float | None
    solar_elevation_max_deg: float | None
    solar_azimuth_start_deg: float | None
    solar_azimuth_end_deg: float | None
    solar_azimuth_span_deg: float | None
    criteria: Mapping[str, object]
    provenance: Mapping[str, str]
    scientific_limitations: tuple[str, ...]
    source_grid_id: str | None = None
    source_row: int | None = None
    source_column: int | None = None
    target_longitude_deg: float | None = None
    target_latitude_deg: float | None = None
    target_coordinate_frame: str | None = None
    kernel_identities: tuple[SpiceKernelIdentity, ...] = ()
    evidence: ScientificEvidence = field(default_factory=ScientificEvidence)
    observation_coverage_availability_min_percent: float | None = None
    observation_coverage_availability_mean_percent: float | None = None
    measured_terrain_coverage_min_percent: float | None = None
    measured_terrain_coverage_mean_percent: float | None = None
    measured_terrain_coverage_max_percent: float | None = None
    elevation_valid_coverage_mean_percent: float | None = None

    def __post_init__(self) -> None:
        if (self.source_row is None) != (self.source_column is None):
            raise ValueError("source_row and source_column must be supplied together")
        if self.source_row is not None:
            if (
                isinstance(self.source_row, bool)
                or not isinstance(self.source_row, int)
                or self.source_row < 0
                or isinstance(self.source_column, bool)
                or not isinstance(self.source_column, int)
                or self.source_column < 0
            ):
                raise ValueError("source row and column must be non-negative integers")
            if not self.source_grid_id:
                raise ValueError("source_grid_id is required with global source indices")
        if (self.target_longitude_deg is None) != (self.target_latitude_deg is None):
            raise ValueError("target longitude and latitude must be supplied together")
        if self.target_longitude_deg is not None:
            if (
                not isfinite(self.target_longitude_deg)
                or not isfinite(self.target_latitude_deg)
                or not -90.0 <= self.target_latitude_deg <= 90.0
                or not self.target_coordinate_frame
            ):
                raise ValueError("target coordinates require finite values and a coordinate frame")
        if not isinstance(self.evidence, ScientificEvidence):
            raise TypeError("evidence must be a ScientificEvidence instance")

    @property
    def interruption_count(self) -> int:
        return len(self.interruptions)

    @property
    def interruption_duration_seconds(self) -> float:
        return sum(item.duration_seconds for item in self.interruptions)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible metadata without raster-sized arrays."""
        return _jsonable(self)


@dataclass(frozen=True)
class Layer5TemporalInput:
    """Body-explicit handoff preventing a Layer 5 request from mixing results."""

    selected_body: str
    layer4_result: RehearsalEvaluation

    def __post_init__(self) -> None:
        if self.selected_body not in ("earth", "moon", "mars"):
            raise ValueError("selected_body must be 'earth', 'moon', or 'mars'")
        if not isinstance(self.layer4_result, RehearsalEvaluation):
            raise TypeError("layer4_result must be a RehearsalEvaluation")
        if self.layer4_result.body != self.selected_body:
            raise ValueError("Layer 5 body must match the selected Layer 4 result body")

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_body": self.selected_body,
            "layer4_result": self.layer4_result.to_dict(),
        }


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {
            key: _jsonable(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _circular_range(values: Iterable[float | None]) -> tuple[float | None, float | None, float | None]:
    angles = sorted(
        {float(value) % 360.0 for value in values if value is not None and isfinite(value)}
    )
    if not angles:
        return None, None, None
    if len(angles) == 1:
        return angles[0], angles[0], 0.0
    gaps = [
        (angles[(index + 1) % len(angles)] - angles[index]) % 360.0
        for index in range(len(angles))
    ]
    largest_gap_index = max(range(len(gaps)), key=gaps.__getitem__)
    start = angles[(largest_gap_index + 1) % len(angles)]
    end = angles[largest_gap_index]
    return start, end, (360.0 - gaps[largest_gap_index]) % 360.0


def _weighted_mean(
    values: Iterable[float | None],
    weights: Iterable[float],
) -> float | None:
    present = [
        (float(value), float(weight))
        for value, weight in zip(values, weights)
        if value is not None and isfinite(value) and weight > 0.0
    ]
    total_weight = sum(weight for _, weight in present)
    if not present or total_weight <= 0.0:
        return None
    return sum(value * weight for value, weight in present) / total_weight


def _minimum(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None and isfinite(value)]
    return min(present) if present else None


def _maximum(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None and isfinite(value)]
    return max(present) if present else None


def _azimuth_in_range(
    value: float | None,
    minimum: float | None,
    maximum: float | None,
) -> bool:
    if value is None or not isfinite(value):
        return False
    if minimum is None and maximum is None:
        return True
    angle = value % 360.0
    if minimum is None:
        if maximum == 360.0:
            return True
        return maximum is not None and angle <= maximum
    if maximum is None:
        if minimum == 0.0:
            return True
        return angle >= minimum
    if minimum == 0.0 and maximum == 360.0:
        return True
    lower, upper = minimum % 360.0, maximum % 360.0
    if lower <= upper:
        return lower <= angle <= upper
    return angle >= lower or angle <= upper


def _window(
    observations: Sequence[TemporalObservation],
    criteria: RehearsalCriteria,
) -> RehearsalWindow:
    duration = sum(item.duration_seconds for item in observations)
    counts: dict[str, int] = {}
    for item in observations:
        for name, count in item.classification_counts.items():
            counts[name] = counts.get(name, 0) + count
    ray_status_counts: dict[str, int] = {}
    for item in observations:
        for name, count in item.ray_status_counts.items():
            ray_status_counts[name] = ray_status_counts.get(name, 0) + count

    valid_coverage = [item.valid_terrain_coverage_percent for item in observations]
    observation_coverage = [
        item.observation_coverage_availability_percent for item in observations
    ]
    measured_coverage = [
        item.measured_terrain_coverage_percent for item in observations
    ]
    obstruction = [item.terrain_obstruction_percent for item in observations]
    illuminated_percent = [
        100.0 * item.illuminated_cells / item.valid_terrain_cells
        if item.valid_terrain_cells else None
        for item in observations
    ]
    weights = [item.duration_seconds for item in observations]
    elevations = [item.solar_elevation_deg for item in observations]
    azimuths = [item.solar_azimuth_deg for item in observations]

    satisfied: list[str] = []
    failed: list[str] = []

    def record(name: str, passed: bool) -> None:
        (satisfied if passed else failed).append(name)

    record(
        "minimum_continuous_illumination",
        duration >= criteria.minimum_continuous_illumination.total_seconds(),
    )
    present_coverage = [value for value in valid_coverage if value is not None]
    record(
        "minimum_valid_terrain_coverage_percent",
        bool(present_coverage)
        and min(present_coverage) >= criteria.minimum_valid_terrain_coverage_percent,
    )
    if criteria.solar_elevation_min_deg is not None:
        record(
            "solar_elevation_min_deg",
            all(
                value is not None and value >= criteria.solar_elevation_min_deg
                for value in elevations
            ),
        )
    if criteria.solar_elevation_max_deg is not None:
        record(
            "solar_elevation_max_deg",
            all(
                value is not None and value <= criteria.solar_elevation_max_deg
                for value in elevations
            ),
        )
    if criteria.solar_azimuth_min_deg is not None or criteria.solar_azimuth_max_deg is not None:
        record(
            "solar_azimuth_range",
            all(
                _azimuth_in_range(
                    value,
                    criteria.solar_azimuth_min_deg,
                    criteria.solar_azimuth_max_deg,
                )
                for value in azimuths
            ),
        )
    present_obstruction = [value for value in obstruction if value is not None]
    record(
        "maximum_terrain_obstruction_percent",
        bool(present_obstruction)
        and max(present_obstruction) <= criteria.maximum_terrain_obstruction_percent,
    )
    if criteria.additional_condition is not None:
        extra_results = [criteria.additional_condition(item) for item in observations]
        if any(not isinstance(value, bool) for value in extra_results):
            raise TypeError("additional_condition must return bool for every observation")
        record(criteria.additional_condition_name, all(extra_results))

    azimuth_start, azimuth_end, azimuth_span = _circular_range(azimuths)
    return RehearsalWindow(
        start_utc=observations[0].time_utc,
        end_utc=observations[-1].interval_end_utc,
        duration_seconds=duration,
        sample_count=len(observations),
        minimum_valid_terrain_coverage_percent=_minimum(valid_coverage),
        mean_valid_terrain_coverage_percent=_weighted_mean(valid_coverage, weights),
        maximum_terrain_obstruction_percent=_maximum(obstruction),
        mean_illuminated_terrain_percent=_weighted_mean(illuminated_percent, weights),
        solar_elevation_min_deg=_minimum(elevations),
        solar_elevation_max_deg=_maximum(elevations),
        solar_azimuth_start_deg=azimuth_start,
        solar_azimuth_end_deg=azimuth_end,
        solar_azimuth_span_deg=azimuth_span,
        classification_counts=counts,
        ray_status_counts=ray_status_counts,
        criteria_satisfied=tuple(satisfied),
        criteria_failed=tuple(failed),
        is_candidate=not failed,
        observation_coverage_availability_percent=_weighted_mean(
            observation_coverage, weights
        ),
        measured_terrain_coverage_percent=_weighted_mean(
            measured_coverage, weights
        ),
    )


def _interruptions(
    observations: Sequence[TemporalObservation],
    windows: Sequence[RehearsalWindow],
) -> tuple[TemporalInterruption, ...]:
    if len(windows) < 2:
        return ()
    by_start = {window.start_utc: index for index, window in enumerate(windows)}
    by_end = {window.end_utc: index for index, window in enumerate(windows)}
    interruptions: list[TemporalInterruption] = []
    interval_index = 0
    while interval_index < len(observations):
        current = observations[interval_index]
        if current.target_classification == "ILLUMINATED":
            interval_index += 1
            continue
        gap_start = interval_index
        while (
            interval_index < len(observations)
            and observations[interval_index].target_classification != "ILLUMINATED"
        ):
            interval_index += 1
        if gap_start == 0 or interval_index == len(observations):
            continue
        previous = observations[gap_start - 1]
        following = observations[interval_index]
        previous_window_index = by_end.get(previous.interval_end_utc)
        following_window_index = by_start.get(following.time_utc)
        if previous_window_index is None or following_window_index is None:
            continue
        if following_window_index != previous_window_index + 1:
            continue
        durations: dict[str, float] = {}
        for item in observations[gap_start:interval_index]:
            durations[item.target_classification] = (
                durations.get(item.target_classification, 0.0) + item.duration_seconds
            )
        interruptions.append(
            TemporalInterruption(
                start_utc=observations[gap_start].time_utc,
                end_utc=observations[interval_index - 1].interval_end_utc,
                duration_seconds=sum(durations.values()),
                target_classification_durations_seconds=durations,
            )
        )
    return tuple(interruptions)


def aggregate_rehearsal(
    *,
    body: str,
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
    intervals: Sequence[tuple[datetime, datetime]],
    observations: Sequence[TemporalObservation],
    target_pixel: tuple[int, int],
    criteria: RehearsalCriteria,
    provenance: Mapping[str, str],
    scientific_limitations: Sequence[str],
    source_grid_id: str | None = None,
    source_row: int | None = None,
    source_column: int | None = None,
    target_longitude_deg: float | None = None,
    target_latitude_deg: float | None = None,
    target_coordinate_frame: str | None = None,
    kernel_identities: Sequence[SpiceKernelIdentity] = (),
    evidence: ScientificEvidence | None = None,
) -> RehearsalEvaluation:
    """Aggregate one body's ordered per-epoch summaries without changing classes."""
    if body not in ("earth", "moon", "mars"):
        raise ValueError("body must be 'earth', 'moon', or 'mars'")
    if len(intervals) != len(observations) or not observations:
        raise ValueError("one observation is required for every evaluation interval")
    if evidence is not None and not isinstance(evidence, ScientificEvidence):
        raise TypeError("evidence must be a ScientificEvidence instance")
    ordered = tuple(observations)
    if any(
        ordered[index].time_utc != intervals[index][0]
        or ordered[index].interval_end_utc != intervals[index][1]
        for index in range(len(ordered))
    ):
        raise ValueError("observation timestamps must exactly match their UTC intervals")

    windows: list[RehearsalWindow] = []
    current: list[TemporalObservation] = []
    for observation in ordered:
        if observation.target_classification == "ILLUMINATED":
            current.append(observation)
        elif current:
            windows.append(_window(current, criteria))
            current = []
    if current:
        windows.append(_window(current, criteria))

    interruptions = _interruptions(ordered, windows)
    total_counts: dict[str, int] = {}
    total_ray_status_counts: dict[str, int] = {}
    target_durations: dict[str, float] = {}
    for observation in ordered:
        for name, count in observation.classification_counts.items():
            total_counts[name] = total_counts.get(name, 0) + count
        for name, count in observation.ray_status_counts.items():
            total_ray_status_counts[name] = (
                total_ray_status_counts.get(name, 0) + count
            )
        target_durations[observation.target_classification] = (
            target_durations.get(observation.target_classification, 0.0)
            + observation.duration_seconds
        )
    candidates = tuple(window for window in windows if window.is_candidate)
    candidate_duration = sum(window.duration_seconds for window in candidates)
    elevation_values = [item.solar_elevation_deg for item in ordered]
    azimuth_start, azimuth_end, azimuth_span = _circular_range(
        item.solar_azimuth_deg for item in ordered
    )
    step_seconds = step.total_seconds()

    return RehearsalEvaluation(
        body=body,
        start_utc=_utc(start_utc, "start_utc"),
        end_utc=_utc(end_utc, "end_utc"),
        step_seconds=step_seconds,
        boundary_uncertainty_seconds=step_seconds,
        target_pixel=target_pixel,
        observations=ordered,
        continuous_illumination_intervals=tuple(windows),
        candidate_windows=candidates,
        interruptions=interruptions,
        total_illumination_duration_seconds=sum(
            window.duration_seconds for window in windows
        ),
        total_qualifying_illumination_duration_seconds=candidate_duration,
        target_classification_durations_seconds=target_durations,
        classification_counts=total_counts,
        ray_status_counts=total_ray_status_counts,
        valid_terrain_coverage_min_percent=_minimum(
            item.valid_terrain_coverage_percent for item in ordered
        ),
        valid_terrain_coverage_mean_percent=_weighted_mean(
            (item.valid_terrain_coverage_percent for item in ordered),
            (item.duration_seconds for item in ordered),
        ),
        valid_terrain_coverage_max_percent=_maximum(
            item.valid_terrain_coverage_percent for item in ordered
        ),
        ray_support_mean_percent_of_valid_terrain=_weighted_mean(
            (item.ray_support_percent_of_valid_terrain for item in ordered),
            (item.duration_seconds for item in ordered),
        ),
        terrain_obstruction_mean_percent=_weighted_mean(
            (item.terrain_obstruction_percent for item in ordered),
            (item.duration_seconds for item in ordered),
        ),
        terrain_obstruction_max_percent=_maximum(
            item.terrain_obstruction_percent for item in ordered
        ),
        solar_elevation_min_deg=_minimum(elevation_values),
        solar_elevation_max_deg=_maximum(elevation_values),
        solar_azimuth_start_deg=azimuth_start,
        solar_azimuth_end_deg=azimuth_end,
        solar_azimuth_span_deg=azimuth_span,
        criteria={
            "minimum_continuous_illumination_seconds": (
                criteria.minimum_continuous_illumination.total_seconds()
            ),
            "minimum_valid_terrain_coverage_percent": (
                criteria.minimum_valid_terrain_coverage_percent
            ),
            "solar_elevation_min_deg": criteria.solar_elevation_min_deg,
            "solar_elevation_max_deg": criteria.solar_elevation_max_deg,
            "solar_azimuth_min_deg": criteria.solar_azimuth_min_deg,
            "solar_azimuth_max_deg": criteria.solar_azimuth_max_deg,
            "maximum_terrain_obstruction_percent": (
                criteria.maximum_terrain_obstruction_percent
            ),
            "additional_condition": (
                criteria.additional_condition_name
                if criteria.additional_condition is not None
                else None
            ),
        },
        provenance=dict(provenance),
        scientific_limitations=tuple(scientific_limitations),
        source_grid_id=source_grid_id,
        source_row=source_row,
        source_column=source_column,
        target_longitude_deg=target_longitude_deg,
        target_latitude_deg=target_latitude_deg,
        target_coordinate_frame=target_coordinate_frame,
        kernel_identities=tuple(kernel_identities),
        evidence=ScientificEvidence() if evidence is None else evidence,
        observation_coverage_availability_min_percent=_minimum(
            item.observation_coverage_availability_percent for item in ordered
        ),
        observation_coverage_availability_mean_percent=_weighted_mean(
            (item.observation_coverage_availability_percent for item in ordered),
            (item.duration_seconds for item in ordered),
        ),
        measured_terrain_coverage_min_percent=_minimum(
            item.measured_terrain_coverage_percent for item in ordered
        ),
        measured_terrain_coverage_mean_percent=_weighted_mean(
            (item.measured_terrain_coverage_percent for item in ordered),
            (item.duration_seconds for item in ordered),
        ),
        measured_terrain_coverage_max_percent=_maximum(
            item.measured_terrain_coverage_percent for item in ordered
        ),
        elevation_valid_coverage_mean_percent=_weighted_mean(
            (
                100.0 * item.elevation_valid_cells / item.total_cells
                if item.total_cells else None
                for item in ordered
            ),
            (item.duration_seconds for item in ordered),
        ),
    )


def observation_from_raster(
    *,
    interval: tuple[datetime, datetime],
    classification,
    valid_mask,
    coverage_mask,
    elevation_valid_mask=None,
    class_codes: Iterable[object],
    target_pixel: tuple[int, int],
    solar_elevation_deg: float | None,
    solar_azimuth_deg: float | None,
    source_dataset_id: str,
    source_metadata: Mapping[str, object] | None,
    ray_status=None,
    ray_status_codes: Iterable[object] = (),
    observation_coverage_mask=None,
    observation_coverage_known_mask=None,
    observation_counts=None,
    solar_direction_fixed: Iterable[float] | None = None,
    solar_frame: str | None = None,
    sun_distance_km: float | None = None,
) -> TemporalObservation:
    """Summarize one engine raster while retaining every native class by name."""
    import numpy as np

    classes = np.asarray(classification)
    valid = np.asarray(valid_mask, dtype=bool)
    coverage = np.asarray(coverage_mask, dtype=bool)
    if classes.ndim != 2 or valid.shape != classes.shape or coverage.shape != classes.shape:
        raise ValueError("classification, validity, and coverage arrays must have matching 2D shapes")
    elevation_valid = (
        valid
        if elevation_valid_mask is None
        else np.asarray(elevation_valid_mask, dtype=bool)
    )
    if elevation_valid.shape != classes.shape:
        raise ValueError("elevation_valid_mask must match the illumination raster")
    if bool(np.any(coverage & ~valid)):
        raise ValueError("illumination coverage cannot include invalid terrain cells")
    row, col = target_pixel
    if not 0 <= row < classes.shape[0] or not 0 <= col < classes.shape[1]:
        raise IndexError("target_pixel is outside the illumination raster")

    codes = {int(code): str(getattr(code, "name", code)) for code in class_codes}
    unknown_values = set(int(value) for value in np.unique(classes)) - set(codes)
    if unknown_values:
        raise ValueError(f"illumination raster contains unsupported class values: {sorted(unknown_values)}")
    counts = {
        codes[code]: int(np.count_nonzero(classes == code))
        for code in codes
    }
    ray_counts: dict[str, int] = {}
    target_ray_status = None
    if ray_status is not None:
        statuses = np.asarray(ray_status)
        if statuses.shape != classes.shape:
            raise ValueError("ray_status must match the illumination raster shape")
        status_codes = {
            int(code): str(getattr(code, "name", code))
            for code in ray_status_codes
        }
        if not status_codes:
            raise ValueError("ray_status_codes are required when ray_status is provided")
        unknown_statuses = set(int(value) for value in np.unique(statuses)) - set(status_codes)
        if unknown_statuses:
            raise ValueError(
                f"ray-status raster contains unsupported values: {sorted(unknown_statuses)}"
            )
        ray_counts = {
            status_codes[code]: int(np.count_nonzero(statuses == code))
            for code in status_codes
        }
        target_ray_status = status_codes[int(statuses[row, col])]

    observation_counts_array = None
    observation_known = None
    observation_covered = None
    if observation_counts is not None:
        raw_counts = np.ma.asarray(observation_counts)
        if raw_counts.shape != classes.shape or not np.issubdtype(
            raw_counts.dtype, np.number
        ):
            raise ValueError("observation_counts must be a numeric array matching the raster")
        count_values = np.asarray(raw_counts.data, dtype=np.float64)
        observation_known = (
            np.isfinite(count_values) & ~np.ma.getmaskarray(raw_counts)
        )
        if np.any(
            observation_known
            & (
                (count_values < 0.0)
                | (count_values != np.floor(count_values))
            )
        ):
            raise ValueError("known observation counts must be non-negative integers")
        observation_counts_array = count_values
        observation_covered = observation_known & (count_values > 0.0)
    elif observation_coverage_mask is not None:
        observation_covered = np.asarray(observation_coverage_mask, dtype=bool)
        if observation_covered.shape != classes.shape:
            raise ValueError("observation_coverage_mask must match the illumination raster")
        observation_known = (
            np.ones(classes.shape, dtype=bool)
            if observation_coverage_known_mask is None
            else np.asarray(observation_coverage_known_mask, dtype=bool)
        )
        if observation_known.shape != classes.shape:
            raise ValueError("observation_coverage_known_mask must match the illumination raster")
    elif observation_coverage_known_mask is not None:
        raise ValueError(
            "observation_coverage_mask is required when known coverage is supplied"
        )

    if observation_covered is not None and observation_known is not None:
        if np.any(observation_covered & ~observation_known):
            raise ValueError("observed terrain cannot have unavailable coverage evidence")
        if observation_counts_array is not None and observation_coverage_mask is not None:
            explicit_coverage = np.asarray(observation_coverage_mask, dtype=bool)
            if explicit_coverage.shape != classes.shape or np.any(
                explicit_coverage[observation_known]
                != observation_covered[observation_known]
            ):
                raise ValueError("observation mask conflicts with observation counts")

    total = int(classes.size)
    valid_count = int(np.count_nonzero(valid))
    elevation_valid_count = int(np.count_nonzero(elevation_valid))
    coverage_count = int(np.count_nonzero(coverage))
    elevation_invalid_count = total - elevation_valid_count
    surface_invalid_count = total - valid_count
    if observation_known is None or observation_covered is None:
        measured_count = None
        unobserved_count = None
        observation_unavailable_count = valid_count
        observation_availability_percent = None
        measured_coverage_percent = None
        target_observation_status = "UNAVAILABLE"
        target_observation_count = None
    else:
        measured_count = int(np.count_nonzero(valid & observation_known & observation_covered))
        unobserved_count = int(
            np.count_nonzero(valid & observation_known & ~observation_covered)
        )
        observation_unavailable_count = int(
            np.count_nonzero(valid & ~observation_known)
        )
        known_valid_count = int(np.count_nonzero(valid & observation_known))
        observation_availability_percent = (
            100.0 * known_valid_count / valid_count if valid_count else None
        )
        measured_coverage_percent = (
            100.0 * measured_count / valid_count if valid_count else None
        )
        if not observation_known[row, col]:
            target_observation_status = "UNAVAILABLE"
        elif observation_covered[row, col]:
            target_observation_status = "MEASURED"
        else:
            target_observation_status = "UNOBSERVED"
        target_observation_count = (
            int(observation_counts_array[row, col])
            if observation_counts_array is not None and observation_known[row, col]
            else None
        )
    illuminated = counts.get("ILLUMINATED", 0)
    obstructed = counts.get("TERRAIN_OBSTRUCTED", 0)
    insufficient = counts.get("INSUFFICIENT_COVERAGE", 0)
    unknown = counts.get("UNKNOWN", 0)
    no_data = counts.get("NO_DATA", 0)
    metadata = {
        str(key): str(value)
        for key, value in (source_metadata or {}).items()
    }
    elevation = None if solar_elevation_deg is None else float(solar_elevation_deg)
    azimuth = None if solar_azimuth_deg is None else float(solar_azimuth_deg)
    if elevation is not None and not isfinite(elevation):
        elevation = None
    if azimuth is not None and not isfinite(azimuth):
        azimuth = None
    direction = None
    if solar_direction_fixed is not None:
        direction_values = tuple(float(value) for value in solar_direction_fixed)
        if len(direction_values) != 3 or not all(isfinite(value) for value in direction_values):
            raise ValueError("solar_direction_fixed must contain three finite components")
        norm_squared = sum(value * value for value in direction_values)
        if abs(norm_squared**0.5 - 1.0) > 1e-8:
            raise ValueError("solar_direction_fixed must be a normalized unit vector")
        if solar_frame is None or not str(solar_frame).strip():
            raise ValueError("solar_frame must be specified with solar_direction_fixed")
        direction = direction_values
    if sun_distance_km is not None and (
        not isfinite(sun_distance_km) or sun_distance_km <= 0.0
    ):
        raise ValueError("sun_distance_km must be finite and positive")

    return TemporalObservation(
        time_utc=_utc(interval[0], "interval start"),
        interval_end_utc=_utc(interval[1], "interval end"),
        target_classification=codes[int(classes[row, col])],
        classification_counts=counts,
        ray_status_counts=ray_counts,
        total_cells=total,
        valid_terrain_cells=valid_count,
        ray_supported_cells=coverage_count,
        valid_terrain_coverage_percent=(
            100.0 * valid_count / total if total else None
        ),
        ray_support_percent_of_valid_terrain=(
            100.0 * coverage_count / valid_count if valid_count else None
        ),
        illuminated_cells=illuminated,
        terrain_obstructed_cells=obstructed,
        insufficient_coverage_cells=insufficient,
        unknown_cells=unknown,
        no_data_cells=no_data,
        terrain_obstruction_percent=(
            100.0 * obstructed / valid_count if valid_count else None
        ),
        solar_elevation_deg=elevation,
        solar_azimuth_deg=None if azimuth is None else azimuth % 360.0,
        solar_direction_fixed=direction,
        solar_frame=None if solar_frame is None else str(solar_frame),
        sun_distance_km=None if sun_distance_km is None else float(sun_distance_km),
        source_dataset_id=str(source_dataset_id),
        source_metadata=metadata,
        target_ray_status=target_ray_status,
        target_ray_status_available=ray_status is not None,
        target_surface_valid=bool(valid[row, col]),
        target_elevation_valid=bool(elevation_valid[row, col]),
        target_observation_coverage_status=target_observation_status,
        target_observation_count=target_observation_count,
        elevation_invalid_cells=elevation_invalid_count,
        surface_invalid_cells=surface_invalid_count,
        elevation_valid_cells=elevation_valid_count,
        measured_valid_elevation_cells=measured_count,
        unobserved_valid_elevation_cells=unobserved_count,
        observation_coverage_unavailable_cells=observation_unavailable_count,
        observation_coverage_availability_percent=observation_availability_percent,
        measured_terrain_coverage_percent=measured_coverage_percent,
    )
