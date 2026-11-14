"""Mars terrain metadata and adapter scaffolding for Layer 4.

This is intentionally a narrow foundation: it defines the explicit Mars body-fixed
metadata contract required before direct-illumination and terrain-horizon logic are
implemented. It does not claim a complete Mars terrain engine yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol

import numpy as np


class _Layer3CRS(Protocol):
    def to_wkt(self) -> str: ...


class _Layer3Patch(Protocol):
    body: str
    z: np.ndarray
    transform: Iterable[float]
    crs: _Layer3CRS
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    sources: list[str]
    missing_sources: list[str]
    resampling: str


@dataclass(frozen=True)
class MarsTerrainMetadata:
    """Scientific metadata required to interpret a Mars terrain patch."""

    body_fixed_frame: str
    elevation_reference: str
    reference_radius_m: float
    provenance: Mapping[str, str] = field(default_factory=dict)
    elevation_unit: str = "m"
    latitude_type: str | None = None
    longitude_direction: str | None = None
    longitude_domain: str | None = None
    coordinate_reference_model: str | None = None

    def __post_init__(self) -> None:
        if not self.body_fixed_frame.strip():
            raise ValueError("body_fixed_frame must be specified")
        if not self.elevation_reference.strip():
            raise ValueError("elevation_reference must be specified")
        if not np.isfinite(self.reference_radius_m) or self.reference_radius_m <= 0.0:
            raise ValueError("reference_radius_m must be finite and positive")
        if not self.elevation_unit.strip():
            raise ValueError("elevation_unit must be specified")
        for name in (
            "latitude_type",
            "longitude_direction",
            "longitude_domain",
            "coordinate_reference_model",
        ):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValueError(f"{name} must not be empty when specified")


@dataclass(frozen=True)
class MarsTerrainPatch:
    """In-memory Mars terrain patch adapter for future illumination work."""

    body: str
    z: np.ndarray
    transform: tuple[float, float, float, float, float, float]
    crs: str
    native_crs: str
    pixel_size_m: float
    native_pixel_size_m: float
    sources: tuple[str, ...]
    missing_sources: tuple[str, ...]
    resampling: str
    metadata: MarsTerrainMetadata
    provenance: Mapping[str, str]
    observation_counts: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.body.casefold() != "mars":
            raise ValueError("MarsTerrainPatch only accepts body='mars' Layer 3 patches")
        if self.z.ndim != 2:
            raise ValueError("Mars terrain patch must be a 2D array")
        if not np.isfinite(self.z).any():
            raise ValueError("Mars terrain patch must contain at least one finite elevation value")
        if not np.isfinite(self.pixel_size_m) or self.pixel_size_m <= 0.0:
            raise ValueError("pixel_size_m must be finite and positive")
        if not np.isfinite(self.native_pixel_size_m) or self.native_pixel_size_m <= 0.0:
            raise ValueError("native_pixel_size_m must be finite and positive")
        if self.observation_counts is not None:
            counts = np.ma.asarray(self.observation_counts)
            if counts.ndim != 2 or counts.shape != self.z.shape:
                raise ValueError("observation counts must match the terrain patch shape")
            if np.ma.getmaskarray(counts).any():
                raise ValueError("observation counts must not be masked")
            values = np.asarray(counts)
            if not np.issubdtype(values.dtype, np.number) or not np.isfinite(values).all():
                raise ValueError("observation counts must contain finite numeric values")
            if np.any(values < 0) or not np.equal(values, np.floor(values)).all():
                raise ValueError("observation counts must contain non-negative integers")

    @property
    def shape(self) -> tuple[int, int]:
        return self.z.shape

    @property
    def valid_mask(self) -> np.ndarray:
        return np.isfinite(self.z)

    @property
    def observation_coverage_mask(self) -> np.ndarray | None:
        """True where the source reports one or more observations, not merely an elevation."""
        if self.observation_counts is None:
            return None
        return self.observation_counts > 0

    @classmethod
    def from_layer3_patch(
        cls,
        patch: _Layer3Patch,
        metadata: MarsTerrainMetadata,
        observation_counts: np.ndarray | None = None,
    ) -> "MarsTerrainPatch":
        """Adapt a Layer 3 Mars patch into a terrain object with explicit metadata."""
        if not hasattr(patch, "body") or str(patch.body).casefold() != "mars":
            raise ValueError("Layer 3 patch must identify body='mars'")
        if not hasattr(patch, "z"):
            raise ValueError("Layer 3 patch must expose a 2D z array")
        if not isinstance(metadata, MarsTerrainMetadata):
            raise TypeError("metadata must be a MarsTerrainMetadata instance")

        raw_values = np.ma.asarray(patch.z, dtype=float)
        z = np.ma.filled(raw_values, np.nan)
        if z.ndim != 2:
            raise ValueError("Layer 3 patch must expose a 2D z array")
        transform_values = tuple(patch.transform)
        if len(transform_values) < 6:
            raise ValueError("Layer 3 patch transform must contain six affine components")
        transform = tuple(float(value) for value in transform_values[:6])
        counts = observation_counts
        if counts is None:
            counts = getattr(patch, "observation_counts", None)

        return cls(
            body="mars",
            z=np.asarray(z, dtype=float),
            transform=transform,
            crs=str(patch.crs.to_wkt()),
            native_crs=str(getattr(patch, "native_crs", "native")),
            pixel_size_m=float(getattr(patch, "pixel_size_m", patch.native_pixel_size_m)),
            native_pixel_size_m=float(getattr(patch, "native_pixel_size_m", patch.pixel_size_m)),
            sources=tuple(str(source) for source in getattr(patch, "sources", [])),
            missing_sources=tuple(str(source) for source in getattr(patch, "missing_sources", [])),
            resampling=str(getattr(patch, "resampling", "nearest")),
            metadata=metadata,
            provenance=dict(metadata.provenance),
            observation_counts=None if counts is None else np.asarray(counts),
        )
