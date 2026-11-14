"""SPICE kernel requirements for Earth solar geometry."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from ..solar.spice_geometry import furnished_spice_kernels


@dataclass(frozen=True)
class EarthKernelSet:
    """Local kernels for geometric Earth solar position in ITRF93.

    The SPK must contain Sun (10) and Earth (399). The binary Earth PCK must
    provide ITRF93 orientation over the requested epochs; the generic text PCK
    provides Earth radii. WGS84 geodetic coordinates are used for site positions.
    """

    leap_seconds: Path
    planetary_spk: Path
    earth_orientation_pck: Path
    generic_pck: Path
    frame: str = "ITRF93"

    def paths(self) -> tuple[Path, ...]:
        return (
            self.leap_seconds,
            self.planetary_spk,
            self.earth_orientation_pck,
            self.generic_pck,
        )

    def validate(self) -> None:
        if self.frame != "ITRF93":
            raise ValueError("Earth solar geometry requires the high-precision ITRF93 frame")
        missing = [str(path) for path in self.paths() if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing Earth SPICE kernel file(s): " + ", ".join(missing)
            )
        empty = [str(path) for path in self.paths() if Path(path).stat().st_size == 0]
        if empty:
            raise ValueError("Empty Earth SPICE kernel file(s): " + ", ".join(empty))


@contextmanager
def furnished_kernels(kernel_set: EarthKernelSet) -> Generator[object, None, None]:
    """Furnish an explicit Earth kernel set and unload only its kernels."""
    if not isinstance(kernel_set, EarthKernelSet):
        raise TypeError("kernels must be an EarthKernelSet instance")
    kernel_set.validate()
    with furnished_spice_kernels(
        kernel_set.paths(),
        missing_dependency_message=(
            "Earth solar geometry requires spiceypy. Install the project dependencies."
        ),
    ) as spice:
        yield spice
