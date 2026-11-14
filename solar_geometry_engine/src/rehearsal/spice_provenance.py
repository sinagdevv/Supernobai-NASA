"""Content identities for the SPICE kernels furnished by one evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SpiceKernelIdentity:
    roles: tuple[str, ...]
    filename: str
    source_path: str
    sha256: str | None
    status: str
    warning: str | None = None


def identify_spice_kernels(
    kernels: Iterable[tuple[str, Path]],
) -> tuple[SpiceKernelIdentity, ...]:
    """Hash each distinct furnished kernel once; preserve failures explicitly."""
    grouped: dict[str, dict[str, object]] = {}
    for role, value in kernels:
        if not role.strip():
            raise ValueError("kernel role must not be empty")
        path = Path(value).expanduser()
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            resolved = path.absolute()
            key = os.path.normcase(str(resolved))
            entry = grouped.get(key)
            if entry is None:
                grouped[key] = {
                    "roles": [role],
                    "filename": resolved.name,
                    "source_path": str(resolved),
                    "sha256": None,
                    "status": "NOT_AVAILABLE",
                    "warning": f"Kernel path could not be resolved: {exc}",
                }
            else:
                roles = entry["roles"]
                assert isinstance(roles, list)
                if role not in roles:
                    roles.append(role)
            continue
        key = os.path.normcase(str(resolved))
        entry = grouped.get(key)
        if entry is not None:
            roles = entry["roles"]
            assert isinstance(roles, list)
            if role not in roles:
                roles.append(role)
            continue

        digest = None
        warning = None
        status = "PASS"
        try:
            if not resolved.is_file():
                raise FileNotFoundError(f"kernel file is not available: {resolved}")
            before = resolved.stat()
            hasher = sha256()
            with resolved.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            after = resolved.stat()
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise OSError(f"kernel changed while hashing: {resolved}")
            digest = hasher.hexdigest()
        except OSError as exc:
            status = "NOT_AVAILABLE"
            warning = f"SHA-256 could not be established: {exc}"

        grouped[key] = {
            "roles": [role],
            "filename": resolved.name,
            "source_path": str(resolved),
            "sha256": digest,
            "status": status,
            "warning": warning,
        }

    return tuple(
        SpiceKernelIdentity(
            roles=tuple(entry["roles"]),
            filename=str(entry["filename"]),
            source_path=str(entry["source_path"]),
            sha256=entry["sha256"],
            status=str(entry["status"]),
            warning=entry["warning"],
        )
        for entry in grouped.values()
    )
