"""SPICE kernel loading helpers for lunar reference geometry.

The caller supplies kernels; this package does not silently download large files.
For high-quality lunar orientation use a DE440 binary lunar PCK and its matching
lunar frames kernel, plus a planetary SPK, a leap-seconds kernel, and a generic
text PCK containing lunar radii.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..solar.spice_geometry import furnished_spice_kernels


@dataclass(frozen=True)
class LunarKernelSet:
    """Required local SPICE kernels.

    ``planetary_spk`` must cover the requested dates and contain the Sun and Moon.
    ``lunar_binary_pck`` and ``lunar_frames_fk`` must belong to the same DE release.
    ``generic_pck`` supplies body shape/radii; ``leap_seconds`` converts UTC to ET.
    """

    leap_seconds: Path
    planetary_spk: Path
    lunar_binary_pck: Path
    lunar_frames_fk: Path
    generic_pck: Path

    def paths(self) -> tuple[Path, ...]:
        return (
            self.leap_seconds,
            self.planetary_spk,
            self.lunar_binary_pck,
            self.lunar_frames_fk,
            self.generic_pck,
        )

    def validate(self) -> None:
        missing = [str(path) for path in self.paths() if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing SPICE kernel file(s): " + ", ".join(missing)
            )
        empty = [str(path) for path in self.paths() if Path(path).stat().st_size == 0]
        if empty:
            raise ValueError("Empty SPICE kernel file(s): " + ", ".join(empty))


@contextmanager
def furnished_kernels(kernel_set: LunarKernelSet) -> Iterator[None]:
    """Load a kernel set for one calculation and unload only those files after.

    SPICE's kernel pool is process-global. Avoid concurrent furnish/unload calls
    from different threads or requests; applications should serialize this scope
    or manage one shared, long-lived kernel pool at process startup.
    """
    kernel_set.validate()
    with furnished_spice_kernels(
        kernel_set.paths(),
        missing_dependency_message=(
            "Lunar geometry requires spiceypy. Install the project dependencies."
        ),
    ):
        yield
