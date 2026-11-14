"""Memory-bounded temporal illumination products for lunar terrain patches."""

from __future__ import annotations

import csv
import ctypes
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable

import numpy as np

from ..windows.temporal import (
    RehearsalCriteria,
    RehearsalEvaluation,
    ScientificEvidence,
    aggregate_rehearsal,
    evaluation_intervals,
    observation_from_raster,
)
from ..spice_provenance import identify_spice_kernels
from . import _illumination_numba
from .reference import (
    lunar_sun_direction_series_fixed,
    lunar_sun_series,
)
from .terrain import (
    LunarTerrainPatch,
    TerrainIlluminationCode,
    TerrainRayStatus,
)

_CODES = tuple(int(code) for code in TerrainIlluminationCode)
_CODE_NAMES = {int(code): code.name for code in TerrainIlluminationCode}
_RAY_STATUS_CODES = tuple(int(status) for status in TerrainRayStatus)
_RAY_STATUS_NAMES = {
    int(status): status.name for status in TerrainRayStatus
}
_SUPPORTED_RAY_STATUSES = (
    int(TerrainRayStatus.SEARCH_LIMIT_REACHED),
    int(TerrainRayStatus.OBSTRUCTION_FOUND),
    int(TerrainRayStatus.SURFACE_FACING_AWAY),
    int(TerrainRayStatus.VERTICAL_SUN),
)


def _working_set_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = ctypes.c_void_p
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_process_memory_info.restype = ctypes.c_int
    process = get_current_process()
    success = get_process_memory_info(
        process, ctypes.byref(counters), counters.cb
    )
    if not success:
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.WorkingSetSize)


def run_terrain_illumination_series(
    terrain: LunarTerrainPatch,
    sun_directions: Iterable[object],
    output_directory: str | Path,
    *,
    step_size_m: float = 5.0,
    max_distance_m: float = 2500.0,
    tolerance: float = 1e-9,
    chunk_rows: int = 256,
    chunk_cols: int = 256,
    radius_pixels: int = 1,
) -> dict[str, object]:
    """Run Numba illumination for ordered Sun directions and write reusable products.

    The classification, support-mask, and ray-status stacks are NumPy memory maps,
    so the complete time stack is not retained in process memory. Persistence
    counts are updated by row blocks and include only definitive terrain
    classifications (codes 1-3).
    """
    directions = list(sun_directions)
    if not directions:
        raise ValueError("sun_directions must contain at least one observation")
    if not _illumination_numba.is_available():
        raise RuntimeError(
            "Numba is required for temporal terrain illumination; install the 'performance' extra"
        )
    if not np.isfinite(step_size_m) or step_size_m <= 0.0:
        raise ValueError("step_size_m must be finite and positive")
    if not np.isfinite(max_distance_m) or max_distance_m <= 0.0:
        raise ValueError("max_distance_m must be finite and positive")
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and nonnegative")
    for name, value in (("chunk_rows", chunk_rows), ("chunk_cols", chunk_cols)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if isinstance(radius_pixels, bool) or not isinstance(radius_pixels, int) or radius_pixels < 1:
        raise ValueError("radius_pixels must be an integer >= 1")
    timestamps: list[datetime] = []
    for index, sun in enumerate(directions):
        time_utc = getattr(sun, "time_utc", None)
        frame = getattr(sun, "frame", None)
        if not isinstance(time_utc, datetime) or time_utc.tzinfo is None or time_utc.utcoffset() is None:
            raise ValueError(f"Sun direction {index} must have a timezone-aware time_utc")
        if frame != terrain.body_fixed_frame:
            raise ValueError(
                f"Sun direction {index} frame {frame!r} does not match terrain frame "
                f"{terrain.body_fixed_frame!r}"
            )
        if not hasattr(sun, "direction_fixed") or not hasattr(sun, "sun_distance_km"):
            raise ValueError(
                f"Sun direction {index} must include direction_fixed and sun_distance_km"
            )
        terrain._sun_direction_and_distance(sun)
        timestamps.append(time_utc.astimezone(timezone.utc))
    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        raise ValueError("sun_directions must be in strictly increasing timestamp order")

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    output_names = (
        "illumination_classifications.npy",
        "coverage_mask.npy",
        "ray_status.npy",
        "illuminated_count.npy",
        "evaluable_count.npy",
        "illumination_persistence_fraction.npy",
        "classification_counts.csv",
        "ray_status_counts.csv",
        "transition_counts.csv",
        "metadata.json",
        "report.md",
    )
    existing = [destination / name for name in output_names if (destination / name).exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite temporal products: {existing[0]}")

    row_count, col_count = terrain.shape
    time_count = len(directions)
    chunks_per_execution = (
        (row_count + chunk_rows - 1) // chunk_rows
    ) * ((col_count + chunk_cols - 1) // chunk_cols)
    stack_shape = (time_count, row_count, col_count)
    classifications = np.lib.format.open_memmap(
        destination / "illumination_classifications.npy",
        mode="w+",
        dtype=np.int16,
        shape=stack_shape,
    )
    coverage_stack = np.lib.format.open_memmap(
        destination / "coverage_mask.npy",
        mode="w+",
        dtype=np.bool_,
        shape=stack_shape,
    )
    ray_status_stack = np.lib.format.open_memmap(
        destination / "ray_status.npy",
        mode="w+",
        dtype=np.int8,
        shape=stack_shape,
    )
    illuminated_count = np.lib.format.open_memmap(
        destination / "illuminated_count.npy",
        mode="w+",
        dtype=np.uint32,
        shape=terrain.shape,
    )
    evaluable_count = np.lib.format.open_memmap(
        destination / "evaluable_count.npy",
        mode="w+",
        dtype=np.uint32,
        shape=terrain.shape,
    )
    illuminated_count[:] = 0
    evaluable_count[:] = 0
    memory_samples = [{
        "stage": "before_normal_cache",
        "working_set_bytes": _working_set_bytes(),
    }]
    cache_start = perf_counter()
    cache = terrain.prepare_illumination_cache(
        chunk_rows=chunk_rows,
        chunk_cols=chunk_cols,
        radius_pixels=radius_pixels,
    )
    cache_seconds = perf_counter() - cache_start
    memory_samples.append({
        "stage": "after_normal_cache",
        "working_set_bytes": _working_set_bytes(),
    })

    per_time: list[dict[str, object]] = []
    transition_counts: dict[tuple[int, int, int], int] = {}
    previous: np.ndarray | None = None
    run_start = perf_counter()
    execution_seconds = []
    for time_index, sun in enumerate(directions):
        execution_start = perf_counter()
        result = terrain.terrain_illumination_raster(
            sun,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            chunk_rows=chunk_rows,
            chunk_cols=chunk_cols,
            radius_pixels=radius_pixels,
            observation_time_utc=timestamps[time_index],
            source_dataset_id=str(terrain.provenance.get("dataset_id", "unknown")),
            source_metadata={str(key): str(value) for key, value in terrain.provenance.items()},
            precomputation=cache,
        )
        classification = result.classification
        classifications[time_index] = classification
        coverage_stack[time_index] = result.coverage_mask
        ray_status_stack[time_index] = result.ray_status
        elapsed = perf_counter() - execution_start
        execution_seconds.append(elapsed)
        memory_samples.append({
            "stage": f"after_illumination_{time_index}",
            "working_set_bytes": _working_set_bytes(),
        })

        counts = {
            code: int(np.count_nonzero(classification == code))
            for code in _CODES
        }
        ray_status_counts = {
            status: int(np.count_nonzero(result.ray_status == status))
            for status in _RAY_STATUS_CODES
        }
        if sum(counts.values()) != row_count * col_count:
            raise RuntimeError(
                f"classification at {timestamps[time_index].isoformat()} contains "
                "unsupported values or missing pixels"
            )
        if sum(ray_status_counts.values()) != row_count * col_count:
            raise RuntimeError(
                f"ray status at {timestamps[time_index].isoformat()} contains "
                "unsupported values or missing pixels"
            )
        expected_support = np.isin(result.ray_status, _SUPPORTED_RAY_STATUSES)
        if not np.array_equal(result.coverage_mask, expected_support):
            raise RuntimeError(
                f"classification-support mask disagrees with ray status at "
                f"{timestamps[time_index].isoformat()}"
            )
        if not np.array_equal(
            result.valid_mask,
            result.ray_status != int(TerrainRayStatus.NO_DATA),
        ):
            raise RuntimeError(
                f"terrain validity disagrees with ray status at "
                f"{timestamps[time_index].isoformat()}"
            )
        coverage_count = int(np.count_nonzero(result.coverage_mask))
        terrain_valid_count = int(np.count_nonzero(result.valid_mask))
        previous_interval_seconds = (
            None
            if time_index == 0
            else (timestamps[time_index] - timestamps[time_index - 1]).total_seconds()
        )
        time_record = {
            "sequence_index": time_index,
            "sequence_id": f"obs-{time_index:04d}",
            "time_utc": timestamps[time_index].isoformat(),
            "interval_from_previous_seconds": previous_interval_seconds,
            "frame": result.solar_frame,
            "direction_fixed": [float(value) for value in result.solar_direction_fixed],
            "sun_distance_km": float(getattr(sun, "sun_distance_km")),
            "spice_et_seconds": getattr(sun, "ephemeris_time_seconds", None),
            "execution_seconds": elapsed,
            "coverage_pixels": coverage_count,
            "coverage_denominator": "valid_terrain_pixels",
            "coverage_percent": (
                100.0 * coverage_count / terrain_valid_count
                if terrain_valid_count
                else 0.0
            ),
            "terrain_valid_pixels": terrain_valid_count,
            "classification_counts": {
                _CODE_NAMES[code]: counts[code] for code in _CODES
            },
            "classification_percentages": {
                _CODE_NAMES[code]: 100.0 * counts[code] / (row_count * col_count)
                for code in _CODES
            },
            "ray_status_counts": {
                _RAY_STATUS_NAMES[status]: ray_status_counts[status]
                for status in _RAY_STATUS_CODES
            },
            "ray_status_percentages": {
                _RAY_STATUS_NAMES[status]: (
                    100.0 * ray_status_counts[status] / (row_count * col_count)
                )
                for status in _RAY_STATUS_CODES
            },
        }
        per_time.append(time_record)

        for row0 in range(0, row_count, chunk_rows):
            row1 = min(row0 + chunk_rows, row_count)
            current = classification[row0:row1]
            illuminated_count[row0:row1] += current == int(TerrainIlluminationCode.ILLUMINATED)
            evaluable = (
                (current == int(TerrainIlluminationCode.ILLUMINATED))
                | (current == int(TerrainIlluminationCode.TERRAIN_OBSTRUCTED))
                | (current == int(TerrainIlluminationCode.SURFACE_FACING_AWAY))
            )
            evaluable_count[row0:row1] += evaluable

        if previous is not None:
            for row0 in range(0, row_count, chunk_rows):
                row1 = min(row0 + chunk_rows, row_count)
                prior_block = previous[row0:row1]
                current_block = classification[row0:row1]
                for from_code in _CODES:
                    prior_mask = prior_block == from_code
                    if not np.any(prior_mask):
                        continue
                    for to_code in _CODES:
                        key = (time_index - 1, from_code, to_code)
                        transition_counts.setdefault(key, 0)
                        transition_counts[key] += int(
                            np.count_nonzero(prior_mask & (current_block == to_code))
                        )
        previous = classifications[time_index]
        classifications.flush()
        coverage_stack.flush()
        ray_status_stack.flush()
        illuminated_count.flush()
        evaluable_count.flush()

    total_execution_seconds = perf_counter() - run_start
    persistence = np.lib.format.open_memmap(
        destination / "illumination_persistence_fraction.npy",
        mode="w+",
        dtype=np.float32,
        shape=terrain.shape,
    )
    for row0 in range(0, row_count, chunk_rows):
        row1 = min(row0 + chunk_rows, row_count)
        observed = evaluable_count[row0:row1]
        fraction = np.full(observed.shape, np.nan, dtype=np.float32)
        np.divide(
            illuminated_count[row0:row1],
            observed,
            out=fraction,
            where=observed > 0,
        )
        persistence[row0:row1] = fraction
    persistence.flush()

    transition_intervals = []
    for interval_index in range(time_count - 1):
        interval = {
            f"{from_code}->{to_code}": count
            for (index, from_code, to_code), count in transition_counts.items()
            if index == interval_index
        }
        if sum(interval.values()) != row_count * col_count:
            raise RuntimeError(
                f"transition counts between {timestamps[interval_index].isoformat()} and "
                f"{timestamps[interval_index + 1].isoformat()} do not cover every pixel"
            )
        changed_pixels = sum(
            count
            for (index, from_code, to_code), count in transition_counts.items()
            if index == interval_index and from_code != to_code
        )
        transition_intervals.append({
            "from_time_utc": timestamps[interval_index].isoformat(),
            "to_time_utc": timestamps[interval_index + 1].isoformat(),
            "changed_pixels": changed_pixels,
            "changed_percent": 100.0 * changed_pixels / (row_count * col_count),
            "transition_counts": interval,
        })

    with (destination / "classification_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_utc", "classification", "code", "pixel_count", "percent"))
        for record in per_time:
            for code in _CODES:
                writer.writerow((
                    record["time_utc"],
                    _CODE_NAMES[code],
                    code,
                    record["classification_counts"][_CODE_NAMES[code]],
                    record["classification_percentages"][_CODE_NAMES[code]],
                ))
    with (destination / "transition_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow((
            "from_time_utc",
            "to_time_utc",
            "from_code",
            "from_classification",
            "to_code",
            "to_classification",
            "pixel_count",
        ))
        for (interval_index, from_code, to_code), count in sorted(transition_counts.items()):
            writer.writerow((
                timestamps[interval_index].isoformat(),
                timestamps[interval_index + 1].isoformat(),
                from_code,
                _CODE_NAMES[from_code],
                to_code,
                _CODE_NAMES[to_code],
                count,
            ))
    with (destination / "ray_status_counts.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_utc", "ray_status", "code", "pixel_count", "percent"))
        for record in per_time:
            for status in _RAY_STATUS_CODES:
                status_name = _RAY_STATUS_NAMES[status]
                writer.writerow((
                    record["time_utc"],
                    status_name,
                    status,
                    record["ray_status_counts"][status_name],
                    record["ray_status_percentages"][status_name],
                ))

    observation_schedule = [
        {
            "sequence_index": record["sequence_index"],
            "sequence_id": record["sequence_id"],
            "time_utc": record["time_utc"],
            "interval_from_previous_seconds": record[
                "interval_from_previous_seconds"
            ],
        }
        for record in per_time
    ]
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "Numba parallel",
        "numba_threads": _illumination_numba.thread_count(),
        "source_dataset_id": str(terrain.provenance.get("dataset_id", "unknown")),
        "source_metadata": {str(key): str(value) for key, value in terrain.provenance.items()},
        "shape": [row_count, col_count],
        "pixel_count": row_count * col_count,
        "terrain_valid_pixels": int(np.count_nonzero(terrain.valid_mask)),
        "chunks_per_execution": chunks_per_execution,
        "total_chunks_processed": chunks_per_execution * time_count,
        "frame": terrain.body_fixed_frame,
        "frame_realization": terrain.frame_realization,
        "elevation_reference": terrain.elevation_reference,
        "working_crs_wkt": terrain.working_crs_wkt,
        "transform": list(terrain.transform),
        "parameters": {
            "step_size_m": step_size_m,
            "max_distance_m": max_distance_m,
            "tolerance": tolerance,
            "chunk_rows": chunk_rows,
            "chunk_cols": chunk_cols,
            "normal_radius_pixels": radius_pixels,
            "effective_search_limit_m": (
                max(1, int(max_distance_m / step_size_m)) * step_size_m
            ),
        },
        "classification_codes": {
            str(code): _CODE_NAMES[code] for code in _CODES
        },
        "ray_status_codes": {
            str(status): _RAY_STATUS_NAMES[status]
            for status in _RAY_STATUS_CODES
        },
        "coverage_semantics": {
            "coverage_mask": (
                "True when a valid terrain normal supports a definitive "
                "classification (ILLUMINATED, TERRAIN_OBSTRUCTED, or "
                "SURFACE_FACING_AWAY); it does not mean every pixel traversed "
                "the full search distance."
            ),
            "coverage_percent_denominator": "valid_terrain_pixels",
            "ray_status_percentage_denominator": "all_raster_pixels",
        },
        "cache_key": cache.cache_key,
        "cache_bytes": int(cache.normals_fixed.nbytes + cache.normal_valid_mask.nbytes),
        "timing_seconds": {
            "terrain_normal_cache": cache_seconds,
            "illumination_executions": execution_seconds,
            "total_illumination_execution": total_execution_seconds,
        },
        "memory_samples": memory_samples,
        "observations": per_time,
        "observation_schedule": observation_schedule,
        "transition_intervals": transition_intervals,
        "outputs": {
            "classification_stack": "illumination_classifications.npy",
            "coverage_stack": "coverage_mask.npy",
            "ray_status_stack": "ray_status.npy",
            "illuminated_count": "illuminated_count.npy",
            "evaluable_count": "evaluable_count.npy",
            "persistence_fraction": "illumination_persistence_fraction.npy",
            "classification_counts": "classification_counts.csv",
            "ray_status_counts": "ray_status_counts.csv",
            "transition_counts": "transition_counts.csv",
        },
    }
    (destination / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Temporal lunar illumination report",
        "",
        f"- Dataset: `{metadata['source_dataset_id']}`",
        f"- Raster: {col_count} x {row_count} ({row_count * col_count:,} pixels)",
        f"- Frame: `{terrain.body_fixed_frame}` / `{terrain.frame_realization}`",
        f"- Engine: {metadata['engine']}",
        f"- Numba threads: {metadata['numba_threads']}",
        f"- Observation count: {time_count}",
        f"- Chunks per observation: {chunks_per_execution}",
        f"- Terrain-normal cache: {cache_seconds:.3f} s, {metadata['cache_bytes']:,} bytes",
        f"- Total illumination execution: {total_execution_seconds:.3f} s",
        "",
        "| UTC | Runtime (s) | Supported (%) | Search limit (%) | Obstructed (%) | DEM edge (%) | Ray NoData (%) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for record in per_time:
        percentages = record["classification_percentages"]
        lines.append(
            f"| {record['time_utc']} | {record['execution_seconds']:.3f} "
            f"| {record['coverage_percent']:.4f} "
            f"| {record['ray_status_percentages']['SEARCH_LIMIT_REACHED']:.4f} "
            f"| {record['ray_status_percentages']['OBSTRUCTION_FOUND']:.4f} "
            f"| {record['ray_status_percentages']['DEM_BOUNDARY']:.4f} "
            f"| {record['ray_status_percentages']['TERRAIN_NODATA']:.4f} |"
        )
    if transition_intervals:
        lines.extend((
            "",
            "## Changes between observations",
            "",
            "| From UTC | To UTC | Changed pixels | Changed (%) |",
            "|---|---|---:|---:|",
        ))
        for interval in transition_intervals:
            lines.append(
                f"| {interval['from_time_utc']} | {interval['to_time_utc']} "
                f"| {interval['changed_pixels']:,} | {interval['changed_percent']:.4f} |"
            )
    lines.extend((
        "",
        "Supported (%) uses valid terrain pixels as its denominator. Ray-status "
        "percentages use all raster pixels. The coverage mask denotes classification "
        "support, not a ray that necessarily reached the configured search limit. "
        "Persistence is the fraction of evaluable observations classified "
        "ILLUMINATED; codes UNKNOWN, NO_DATA, and INSUFFICIENT_COVERAGE are "
        "excluded from its denominator. Locations with no evaluable observations "
        "are NaN. See `coverage_mask.npy`, `ray_status.npy`, and the CSV/JSON "
        "products for per-time coverage and transition details.",
        "",
    ))
    (destination / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return metadata


def evaluate_lunar_rehearsal_windows(
    terrain: LunarTerrainPatch,
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
    *,
    kernels,
    criteria: RehearsalCriteria | None = None,
    target_pixel: tuple[int, int] | None = None,
    frame: str | None = None,
    step_size_m: float = 5.0,
    max_distance_m: float = 2500.0,
    tolerance: float = 1e-9,
    chunk_rows: int = 256,
    chunk_cols: int = 256,
    radius_pixels: int = 1,
    evidence: ScientificEvidence | None = None,
) -> RehearsalEvaluation:
    """Evaluate target-cell rehearsal intervals on one lunar terrain patch."""
    from .kernels import LunarKernelSet

    if not isinstance(terrain, LunarTerrainPatch):
        raise TypeError("terrain must be a LunarTerrainPatch")
    if not isinstance(kernels, LunarKernelSet):
        raise TypeError("kernels must be a LunarKernelSet")
    selected_frame = terrain.body_fixed_frame if frame is None else frame
    if selected_frame != terrain.body_fixed_frame:
        raise ValueError("the requested lunar frame must match the terrain patch frame")
    selected_criteria = criteria or RehearsalCriteria()
    intervals = evaluation_intervals(start_utc, end_utc, step)
    target = (
        (terrain.shape[0] // 2, terrain.shape[1] // 2)
        if target_pixel is None
        else target_pixel
    )
    row, col = target
    if (
        isinstance(row, bool) or isinstance(col, bool)
        or not isinstance(row, int) or not isinstance(col, int)
        or not 0 <= row < terrain.shape[0] or not 0 <= col < terrain.shape[1]
    ):
        raise ValueError("target_pixel must be an in-bounds (row, column) pair")

    longitude, latitude = terrain.pixel_to_lonlat(row, col)
    elevation = float(terrain.elevations_m[row, col])
    if not np.isfinite(elevation):
        elevation = 0.0
    times = tuple(interval[0] for interval in intervals)
    directions = lunar_sun_direction_series_fixed(times, kernels, frame=selected_frame)
    geometries = lunar_sun_series(
        latitude,
        longitude,
        times,
        kernels,
        altitude_m=elevation,
        frame=selected_frame,
        latitude_type="planetocentric",
    )
    cache = terrain.prepare_illumination_cache(
        chunk_rows=chunk_rows,
        chunk_cols=chunk_cols,
        radius_pixels=radius_pixels,
    )

    source_id = str(terrain.provenance.get("dataset_id", terrain.sources[0]))
    source_metadata = {
        str(key): str(value) for key, value in terrain.provenance.items()
    }
    kernel_identities = identify_spice_kernels(
        (
            ("leap-seconds kernel", kernels.leap_seconds),
            ("planetary ephemeris SPK", kernels.planetary_spk),
            ("lunar orientation binary PCK", kernels.lunar_binary_pck),
            ("lunar frames FK", kernels.lunar_frames_fk),
            ("planetary constants text PCK", kernels.generic_pck),
        )
    )
    observations = []
    for interval, sun, geometry in zip(intervals, directions, geometries):
        result = terrain.terrain_illumination_raster(
            sun,
            step_size_m=step_size_m,
            max_distance_m=max_distance_m,
            tolerance=tolerance,
            chunk_rows=chunk_rows,
            chunk_cols=chunk_cols,
            radius_pixels=radius_pixels,
            observation_time_utc=interval[0],
            source_dataset_id=source_id,
            source_metadata=source_metadata,
            precomputation=cache,
        )
        observations.append(
            observation_from_raster(
                interval=interval,
                classification=result.classification,
                valid_mask=result.valid_mask,
                coverage_mask=result.coverage_mask,
                class_codes=TerrainIlluminationCode,
                ray_status=getattr(result, "ray_status", None),
                ray_status_codes=TerrainRayStatus,
                observation_counts=terrain.observation_counts,
                target_pixel=target,
                solar_elevation_deg=geometry.solar_elevation_deg,
                solar_azimuth_deg=geometry.solar_azimuth_deg,
                source_dataset_id=result.source_dataset_id,
                source_metadata=result.source_metadata,
                solar_direction_fixed=sun.direction_fixed,
                solar_frame=sun.frame,
                sun_distance_km=sun.sun_distance_km,
            )
        )

    provenance = {
        "body": "moon",
        "frame": terrain.body_fixed_frame,
        "frame_realization": terrain.frame_realization,
        "frame_alignment_note": terrain.frame_alignment_note,
        "elevation_reference": terrain.elevation_reference,
        "reference_radius_m": str(terrain.reference_radius_m),
        "working_crs_wkt": terrain.working_crs_wkt,
        "native_crs": terrain.native_crs,
        "resampling": terrain.resampling,
        "terrain_sources": ";".join(terrain.sources),
        "pixel_size_m": str(terrain.pixel_size_m),
        "native_pixel_size_m": str(terrain.native_pixel_size_m),
        "affine_transform": ",".join(str(value) for value in terrain.transform),
        "spice_kernel_paths": ";".join(str(path) for path in kernels.paths()),
        "observation_coverage_status": str(
            terrain.provenance.get("observation_coverage_status", "UNAVAILABLE")
        ),
        "observation_counts_sources": ";".join(
            terrain.observation_counts_sources
        ),
        **{f"source.{key}": str(value) for key, value in terrain.provenance.items()},
    }
    return aggregate_rehearsal(
        body="moon",
        start_utc=start_utc,
        end_utc=end_utc,
        step=step,
        intervals=intervals,
        observations=observations,
        target_pixel=target,
        criteria=selected_criteria,
        provenance=provenance,
        source_grid_id=source_id,
        target_longitude_deg=longitude,
        target_latitude_deg=latitude,
        target_coordinate_frame=terrain.body_fixed_frame,
        kernel_identities=kernel_identities,
        evidence=evidence,
        scientific_limitations=(
            "Lunar solar geometry uses the selected SPICE body-fixed frame and supplied kernels.",
            "Terrain and shadow coverage are limited to the supplied LOLA-derived patch.",
            "LOLA surface elevations may be interpolated where no laser return is present; observation coverage is unavailable unless an aligned count patch is supplied.",
            "Illumination is determined only over the configured ray search distance.",
            "No independent observational shadow-accuracy validation is included.",
        ),
    )
