"""Shapes shared by the CLI and the HTTP service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .canonical import sanitize

Kind = Literal["profile", "compare", "screen"]
Role = Literal["reference", "candidate", "input"]
ROLES = ("reference", "candidate", "input")


class ReportError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.run_id: str | None = None


class DatasetLink(BaseModel):
    dataset_id: str
    role: Role
    sha256: str | None = None


class RunIn(BaseModel):
    kind: Kind
    request: dict | None = None
    result: dict
    engine_version: str | None = None
    datasets: list[DatasetLink] | None = None


class ReportIn(BaseModel):
    run_id: str


def detect_kind(result: dict) -> Kind:
    if result.get("type") == "FeatureCollection":
        return "screen"
    if "reference_profile" in result and "candidate_profile" in result:
        return "compare"
    if "patch" in result and "scales" in result:
        return "profile"
    raise ReportError("unknown_result", "The result is not a profile, comparison, or screen document.")


def engine_version_of(result: dict) -> str | None:
    provenance = result.get("provenance")
    if isinstance(provenance, dict) and provenance.get("engine_version"):
        return str(provenance["engine_version"])
    for side in ("reference_profile", "candidate_profile"):
        side_prov = (result.get(side) or {}).get("provenance") or {}
        if isinstance(side_prov, dict) and side_prov.get("engine_version"):
            return str(side_prov["engine_version"])
    return None


def _dataset_id(result: dict, *path: str) -> str:
    node: Any = result
    for part in path:
        if not isinstance(node, dict) or part not in node:
            raise ReportError("missing_dataset", "The result does not name an input dataset.")
        node = node[part]
    if not isinstance(node, str) or not node:
        raise ReportError("missing_dataset", "The result does not name an input dataset.")
    return node


def dataset_refs(kind: Kind, result: dict) -> list[tuple[Role, str]]:
    if kind == "compare":
        return [
            ("reference", _dataset_id(result, "reference_profile", "provenance", "dataset_id")),
            ("candidate", _dataset_id(result, "candidate_profile", "provenance", "dataset_id")),
        ]
    if kind == "screen":
        return [("input", _dataset_id(result, "provenance", "dataset_id"))]
    if kind == "profile":
        return [("input", _dataset_id(result, "provenance", "dataset_id"))]
    raise ReportError("unknown_result", f"Unknown result kind '{kind}'.")


def derive_request(kind: Kind, result: dict) -> dict:
    """A request recorded from a result file when the original request body was not kept."""
    result = sanitize(result)
    if kind == "compare":
        return {
            "derived_from_result": True,
            "reference_dataset_id": dataset_refs(kind, result)[0][1],
            "candidate_dataset_id": dataset_refs(kind, result)[1][1],
            "common_scales_m": result.get("common_scales_m"),
            "tolerances": result.get("tolerances"),
        }
    if kind == "screen":
        return {
            "derived_from_result": True,
            "dataset_id": dataset_refs(kind, result)[0][1],
            "summary": result.get("summary"),
            "criteria": result.get("criteria"),
        }
    return {
        "derived_from_result": True,
        "dataset_id": dataset_refs(kind, result)[0][1],
        "patch": (result.get("patch") or {}),
        "scales_m": [item.get("scale_m") for item in result.get("scales") or [] if isinstance(item, dict)],
    }


def closed_ring(ring: list) -> list:
    if ring and ring[0] != ring[-1]:
        return [*ring, ring[0]]
    return ring


def candidate_features(result: dict) -> list[dict]:
    features = result.get("features")
    if not isinstance(features, list):
        raise ReportError("invalid_screen", "A screen result needs a features list.")
    rows = []
    for feature in features:
        if not isinstance(feature, dict):
            raise ReportError("invalid_screen", "A screen feature is not an object.")
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Polygon":
            raise ReportError("invalid_screen", "Each screen feature must be a Polygon.")
        coordinates = geometry.get("coordinates") or []
        if not coordinates or not isinstance(coordinates[0], list):
            raise ReportError("invalid_screen", "A screen polygon has no ring.")
        patch_id = str(props.get("id") or feature.get("id") or "")
        if not patch_id:
            raise ReportError("invalid_screen", "A screen feature has no id.")
        center = None
        if props.get("center_lon") is not None and props.get("center_lat") is not None:
            center = (float(props["center_lon"]), float(props["center_lat"]))
        rows.append(
            {
                "patch_id": patch_id,
                "status": str(props.get("status") or "unknown"),
                "geometry": {"type": "Polygon", "coordinates": [closed_ring(coordinates[0])]},
                "center": center,
                "metrics": props.get("metrics") or {},
                "criteria": props.get("criteria") or [],
            }
        )
    return rows
