"""SPICE-verified MOLA IAU2000 to current Mars-frame conversion."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, degrees
from pathlib import Path
from typing import Mapping

import numpy as np

from ..solar.spice_geometry import (
    _SPICE_POOL_LOCK,
    furnished_spice_kernels,
    utc_spice_string,
)
from .mola import MarsMolaGeometricWindow, _sha256
from .terrain import MarsTerrainPatch


_IAU2000_PCK_SHA256 = "07ba38b939ae92c085882752a523addd749fde0abb7a3468423099ed02bb3949"
_CURRENT_PCK_SHA256 = "3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1"
_LSK_SHA256 = "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b"
_EXPECTED_FRAME_ID = 10014
_EXPECTED_CENTER_ID = 499
_EXPECTED_FRAME_CLASS = 2
_FRAME_NAME = "IAU_MARS"


@dataclass(frozen=True)
class MarsMolaFrameKernels:
    """Pinned NAIF text kernels used to realize both Mars frame orientations."""

    leap_seconds: Path
    mola_orientation_pck: Path
    current_orientation_pck: Path

    def validate(self) -> None:
        expected = (
            (Path(self.leap_seconds), "naif0012.tls", _LSK_SHA256),
            (Path(self.mola_orientation_pck), "mars_iau2000_v1.tpc", _IAU2000_PCK_SHA256),
            (Path(self.current_orientation_pck), "pck00011.tpc", _CURRENT_PCK_SHA256),
        )
        resolved = [path.resolve() for path, _, _ in expected]
        if len(set(resolved)) != len(resolved):
            raise ValueError("MOLA frame conversion requires three distinct kernel files")
        for path, expected_name, expected_hash in expected:
            path = path.resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Required Mars frame kernel is missing: {path}")
            if path.name.casefold() != expected_name.casefold():
                raise ValueError(
                    f"Expected {expected_name} for this frame realization, got {path.name}"
                )
            actual_hash = _sha256(path)
            if actual_hash != expected_hash:
                raise ValueError(
                    f"SHA-256 mismatch for {path.name}; expected pinned NAIF kernel "
                    f"{expected_hash}, got {actual_hash}"
                )


@dataclass(frozen=True)
class MarsMolaFrameSolution:
    """Rotation and current PCK reference ellipsoid at a specific epoch."""

    time_utc: datetime
    et: float
    source_frame_id: int
    target_frame_id: int
    source_center_id: int
    target_center_id: int
    source_frame_class: int
    target_frame_class: int
    rotation_current_from_mola: np.ndarray
    source_radii_m: tuple[float, float, float]
    current_radii_m: tuple[float, float, float]
    rotation_angle_rad: float
    spice_toolkit_version: str
    leap_seconds_sha256: str = _LSK_SHA256
    mola_pck_sha256: str = _IAU2000_PCK_SHA256
    current_pck_sha256: str = _CURRENT_PCK_SHA256

    @property
    def inverse_rotation(self) -> np.ndarray:
        inverse = self.rotation_current_from_mola.T.copy()
        inverse.setflags(write=False)
        return inverse

    @property
    def rotation_angle_deg(self) -> float:
        return degrees(self.rotation_angle_rad)

    @property
    def rotation_angle_arcsec(self) -> float:
        return self.rotation_angle_deg * 3600.0

    def surface_arc_length_m(self, radius_m: float) -> float:
        if not np.isfinite(radius_m) or radius_m <= 0.0:
            raise ValueError("radius_m must be finite and positive")
        return float(radius_m * self.rotation_angle_rad)

    def maximum_surface_chord_m(self, radius_m: float) -> float:
        if not np.isfinite(radius_m) or radius_m <= 0.0:
            raise ValueError("radius_m must be finite and positive")
        return float(2.0 * radius_m * np.sin(self.rotation_angle_rad / 2.0))


@dataclass(frozen=True)
class MarsMolaCurrentFrameWindow:
    """A read-only transformed view; the original MOLA terrain remains attached."""

    source_window: MarsMolaGeometricWindow
    solution: MarsMolaFrameSolution
    longitude_deg: np.ndarray
    latitude_deg: np.ndarray
    radial_distance_m: np.ndarray
    ellipsoid_radial_distance_m: np.ndarray
    radial_offset_from_ellipsoid_m: np.ndarray
    provenance: Mapping[str, str]

    @property
    def terrain_patch(self) -> MarsTerrainPatch:
        return self.source_window.terrain_patch

    @property
    def observation_coverage_mask(self) -> np.ndarray | None:
        return self.terrain_patch.observation_coverage_mask


class MarsMolaFrameTransform:
    """Realize the epoch-dependent rotation between two SPICE Mars orientations.

    PDS identifies the source as IAU2000_MARS; the old NAIF PCK realizes that
    orientation through SPICE frame IAU_MARS, ID 10014. The current PCK defines
    the same SPICE frame ID with a different orientation, so the two PCKs must
    be evaluated separately, never as simultaneous aliases.
    """

    def __init__(self, kernels: MarsMolaFrameKernels) -> None:
        if not isinstance(kernels, MarsMolaFrameKernels):
            raise TypeError("kernels must be a MarsMolaFrameKernels instance")
        kernels.validate()
        self.kernels = kernels

    @staticmethod
    def _frame_metadata(spice) -> tuple[int, int, int]:
        frame_id = int(spice.namfrm(_FRAME_NAME))
        if frame_id != _EXPECTED_FRAME_ID:
            raise ValueError(f"{_FRAME_NAME} resolved to frame ID {frame_id}, expected 10014")
        center_id, frame_class, class_id = spice.frinfo(frame_id)
        if (
            int(center_id) != _EXPECTED_CENTER_ID
            or int(frame_class) != _EXPECTED_FRAME_CLASS
            or int(class_id) != _EXPECTED_CENTER_ID
        ):
            raise ValueError(
                f"Unexpected {_FRAME_NAME} frame definition: "
                f"center={center_id}, class={frame_class}, class_id={class_id}"
            )
        return frame_id, int(center_id), int(frame_class)

    @staticmethod
    def _mars_radii_m(spice) -> tuple[float, float, float]:
        dimension, radii_km = spice.bodvrd("MARS", "RADII", 3)
        if int(dimension) != 3:
            raise ValueError(f"SPICE returned {dimension} Mars radii; expected 3")
        radii = tuple(float(value) * 1000.0 for value in radii_km)
        if not np.all(np.isfinite(radii)) or min(radii) <= 0.0:
            raise ValueError("SPICE returned invalid Mars reference radii")
        return radii

    def solution_at(self, time_utc: datetime) -> MarsMolaFrameSolution:
        """Return R_current<-MOLA at ``time_utc`` and radii from the current PCK."""
        if not isinstance(time_utc, datetime):
            raise TypeError("time_utc must be a datetime instance")
        utc_text = utc_spice_string(time_utc)

        try:
            import spiceypy as spice
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise RuntimeError("Install spiceypy to transform Mars reference frames") from exc

        with _SPICE_POOL_LOCK:
            if int(spice.ktotal("ALL")) != 0:
                raise RuntimeError(
                    "Mars MOLA frame transformation requires an empty SPICE kernel pool; "
                    "unload existing kernels and retry"
                )

            with furnished_spice_kernels(
                (Path(self.kernels.leap_seconds), Path(self.kernels.mola_orientation_pck))
            ):
                et = float(spice.str2et(utc_text))
                source_id, source_center, source_class = self._frame_metadata(spice)
                source_to_j2000 = np.asarray(
                    spice.pxform(_FRAME_NAME, "J2000", et), dtype=np.float64
                )
                source_radii = self._mars_radii_m(spice)

            if int(spice.ktotal("ALL")) != 0:
                raise RuntimeError("SPICE kernel cleanup did not restore an empty kernel pool")

            with furnished_spice_kernels(
                (Path(self.kernels.leap_seconds), Path(self.kernels.current_orientation_pck))
            ):
                target_id, target_center, target_class = self._frame_metadata(spice)
                j2000_to_current = np.asarray(
                    spice.pxform("J2000", _FRAME_NAME, et), dtype=np.float64
                )
                current_radii = self._mars_radii_m(spice)
                toolkit_version = str(spice.tkvrsn("TOOLKIT"))

            if int(spice.ktotal("ALL")) != 0:
                raise RuntimeError("SPICE kernel cleanup did not restore an empty kernel pool")

        if not np.allclose(source_radii, current_radii, rtol=0.0, atol=1e-9):
            raise ValueError("The IAU2000 and current PCKs do not agree on Mars radii")
        rotation = j2000_to_current @ source_to_j2000
        if rotation.shape != (3, 3) or not np.all(np.isfinite(rotation)):
            raise ValueError("SPICE produced an invalid Mars frame rotation")
        orthogonality_error = float(
            np.linalg.norm(rotation.T @ rotation - np.eye(3), ord=2)
        )
        determinant = float(np.linalg.det(rotation))
        if orthogonality_error > 1e-12 or abs(determinant - 1.0) > 1e-12:
            raise ValueError(
                "SPICE frame rotation failed orthogonality or determinant checks"
            )

        skew = np.array(
            [
                rotation[2, 1] - rotation[1, 2],
                rotation[0, 2] - rotation[2, 0],
                rotation[1, 0] - rotation[0, 1],
            ],
            dtype=np.float64,
        )
        sine = 0.5 * float(np.linalg.norm(skew))
        cosine = float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0))
        angle = atan2(sine, cosine)
        rotation.setflags(write=False)

        return MarsMolaFrameSolution(
            time_utc=time_utc.astimezone(timezone.utc),
            et=et,
            source_frame_id=source_id,
            target_frame_id=target_id,
            source_center_id=source_center,
            target_center_id=target_center,
            source_frame_class=source_class,
            target_frame_class=target_class,
            rotation_current_from_mola=rotation,
            source_radii_m=source_radii,
            current_radii_m=current_radii,
            rotation_angle_rad=angle,
            spice_toolkit_version=toolkit_version,
        )

    def transform_window(
        self,
        window: MarsMolaGeometricWindow,
        time_utc: datetime,
    ) -> MarsMolaCurrentFrameWindow:
        """Rotate MEGR radial points and express them against the current PCK ellipsoid."""
        if not isinstance(window, MarsMolaGeometricWindow):
            raise TypeError("window must be a MarsMolaGeometricWindow instance")
        solution = self.solution_at(time_utc)
        shape = window.terrain_patch.shape

        row_centers = (
            window.row_offset + np.arange(shape[0], dtype=np.float64) + 0.5
        )
        column_centers = (
            window.column_offset + np.arange(shape[1], dtype=np.float64) + 0.5
        )
        longitude_old, latitude_old = np.meshgrid(
            column_centers / 32.0,
            90.0 - row_centers / 32.0,
        )
        longitude_rad = np.deg2rad(longitude_old)
        latitude_rad = np.deg2rad(latitude_old)
        radius_source = window.planetary_radius_m
        source_vectors = np.stack(
            (
                radius_source * np.cos(latitude_rad) * np.cos(longitude_rad),
                radius_source * np.cos(latitude_rad) * np.sin(longitude_rad),
                radius_source * np.sin(latitude_rad),
            ),
            axis=-1,
        )
        current_vectors = source_vectors @ solution.rotation_current_from_mola.T
        radial_distance = np.linalg.norm(current_vectors, axis=-1)
        if not np.allclose(radial_distance, radius_source, rtol=0.0, atol=1e-7):
            raise ValueError("Frame rotation did not preserve MOLA radial distances")

        unit_vectors = current_vectors / radial_distance[..., np.newaxis]
        longitude = np.mod(
            np.rad2deg(np.arctan2(unit_vectors[..., 1], unit_vectors[..., 0])),
            360.0,
        )
        latitude = np.rad2deg(
            np.arctan2(
                unit_vectors[..., 2],
                np.hypot(unit_vectors[..., 0], unit_vectors[..., 1]),
            )
        )
        radii = np.asarray(solution.current_radii_m, dtype=np.float64)
        ellipsoid_denominator = np.sqrt(
            np.sum((unit_vectors / radii) ** 2, axis=-1)
        )
        ellipsoid_radial_distance = 1.0 / ellipsoid_denominator
        radial_offset = radial_distance - ellipsoid_radial_distance

        arrays = (
            longitude,
            latitude,
            radial_distance,
            ellipsoid_radial_distance,
            radial_offset,
        )
        for array in arrays:
            if not np.all(np.isfinite(array)):
                raise ValueError("Mars coordinate transform produced non-finite values")
            array.setflags(write=False)

        provenance = dict(window.terrain_patch.provenance)
        provenance.update(
            {
                "source_coordinate_frame": "PDS IAU2000_MARS; SPICE realization IAU_MARS/10014",
                "target_coordinate_frame": "current SPICE IAU_MARS/10014, center 499",
                "frame_transform_direction": "R_current<-MOLA = pxform(J2000, IAU_MARS)_current * pxform(IAU_MARS, J2000)_IAU2000",
                "frame_transform_time_utc": solution.time_utc.isoformat(),
                "frame_rotation_angle_arcsec": f"{solution.rotation_angle_arcsec:.12g}",
                "frame_rotation_matrix_row_major": np.array2string(
                    solution.rotation_current_from_mola,
                    precision=17,
                    separator=",",
                ),
                "mola_orientation_pck_sha256": solution.mola_pck_sha256,
                "current_orientation_pck_sha256": solution.current_pck_sha256,
                "leap_seconds_kernel_sha256": solution.leap_seconds_sha256,
                "spice_toolkit_version": solution.spice_toolkit_version,
                "surface_position_source": "MEGR90N000FB absolute mean planetary radius",
                "ellipsoid_offset_semantics": (
                    "radial distance minus current ellipsoid radial intersection; "
                    "not geodetic-normal height or areoid elevation"
                ),
            }
        )
        return MarsMolaCurrentFrameWindow(
            source_window=window,
            solution=solution,
            longitude_deg=longitude,
            latitude_deg=latitude,
            radial_distance_m=radial_distance,
            ellipsoid_radial_distance_m=ellipsoid_radial_distance,
            radial_offset_from_ellipsoid_m=radial_offset,
            provenance=provenance,
        )
