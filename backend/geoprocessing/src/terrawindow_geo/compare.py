"""Compare a candidate patch against a reference patch, one criterion at a time.

There is deliberately no overall similarity score. Each criterion keeps its own values, its own
tolerance and its own status, and a criterion that cannot be evaluated is `not_assessed`, which is
different from failing.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import wasserstein_distance

from ._util import fnum
from .models import ComparisonResult, CriterionResult, ScaleMetrics, TerrainProfile, Tolerances


def _criterion(metric, scale_m, unit, ref, cand, tol, kind, missing_reason=None) -> CriterionResult:
    if ref is None or cand is None:
        return CriterionResult(
            metric=metric, scale_m=scale_m, unit=unit, reference=ref, candidate=cand, difference=None,
            tolerance=tol, tolerance_kind=kind, normalized_difference=None, status="not_assessed",
            reason=missing_reason or "Value missing on one side.",
        )
    diff = cand - ref
    allowed = tol if kind == "absolute" else tol * abs(ref)
    if allowed <= 0:
        norm = 0.0 if diff == 0 else None
        status = "within_tolerance" if diff == 0 else "not_assessed"
        reason = None if diff == 0 else "Reference value is zero, so a relative tolerance is undefined."
    else:
        norm = abs(diff) / allowed
        status = "within_tolerance" if norm <= 1 else "outside_tolerance"
        reason = None
    return CriterionResult(
        metric=metric, scale_m=scale_m, unit=unit, reference=fnum(ref), candidate=fnum(cand), difference=fnum(diff),
        tolerance=tol, tolerance_kind=kind, normalized_difference=fnum(norm, 3), status=status, reason=reason,
    )


def _slope_distance(a: ScaleMetrics, b: ScaleMetrics) -> float | None:
    """Earth mover's distance between the two slope histograms, in degrees."""
    ha, hb = a.slope.histogram, b.slope.histogram
    if ha.bin_edges_deg != hb.bin_edges_deg or sum(ha.fractions) == 0 or sum(hb.fractions) == 0:
        return None
    edges = np.asarray(ha.bin_edges_deg)
    centres = (edges[:-1] + edges[1:]) / 2
    return float(wasserstein_distance(centres, centres, ha.fractions, hb.fractions))


def _match(scales: list[ScaleMetrics], scale_m: float) -> ScaleMetrics | None:
    for s in scales:
        if abs(s.scale_m - scale_m) <= 0.01 * scale_m:
            return s
    return None


def compare_profiles(reference: TerrainProfile, candidate: TerrainProfile, tolerances: Tolerances | None = None) -> ComparisonResult:
    tol = tolerances or Tolerances()
    criteria: list[CriterionResult] = []
    notes: list[str] = []

    ref_scales = {s.scale_m for s in reference.scales}
    cand_scales = {s.scale_m for s in candidate.scales}
    common = sorted(s for s in ref_scales if _match(candidate.scales, s) is not None)
    only_ref = sorted(ref_scales - set(common))
    only_cand = sorted(s for s in cand_scales if _match(reference.scales, s) is None)
    if only_ref:
        notes.append(f"Scales only in the reference (not compared): {', '.join(f'{s:g} m' for s in only_ref)}.")
    if only_cand:
        notes.append(f"Scales only in the candidate (not compared): {', '.join(f'{s:g} m' for s in only_cand)}.")
    if not common:
        notes.append("The two profiles share no analysis scale, so no terrain criterion could be compared.")

    for scale in common:
        r, c = _match(reference.scales, scale), _match(candidate.scales, scale)
        if r.status != "assessed" or c.status != "assessed":
            who = "reference" if r.status != "assessed" else "candidate"
            reason = f"Insufficient elevation coverage in the {who} patch at this scale."
            for metric, unit in (("slope_mean", "degrees"), ("slope_p90", "degrees"), ("roughness_rms_height_median", "metres")):
                criteria.append(_criterion(metric, scale, unit, None, None, None, "absolute", reason))
            continue
        rs, cs = r.slope, c.slope
        criteria.append(_criterion("slope_mean", scale, "degrees", rs.stats.mean, cs.stats.mean, tol.slope_mean_deg, "absolute"))
        criteria.append(_criterion("slope_median", scale, "degrees", rs.stats.median, cs.stats.median, tol.slope_median_deg, "absolute"))
        criteria.append(_criterion("slope_p90", scale, "degrees", rs.stats.p90, cs.stats.p90, tol.slope_p90_deg, "absolute"))
        criteria.append(_criterion("rms_slope", scale, "degrees", rs.rms_slope_deg, cs.rms_slope_deg, tol.rms_slope_deg, "absolute"))
        for key in sorted(set(rs.fraction_steeper_than) & set(cs.fraction_steeper_than), key=float):
            criteria.append(
                _criterion(
                    f"fraction_steeper_than_{key}deg", scale, "fraction",
                    rs.fraction_steeper_than[key], cs.fraction_steeper_than[key], tol.slope_fraction_abs, "absolute",
                )
            )
        dist = _slope_distance(r, c)
        criteria.append(
            CriterionResult(
                metric="slope_distribution_distance", scale_m=scale, unit="degrees", reference=None, candidate=None,
                difference=fnum(dist, 3), tolerance=tol.slope_distribution_deg, tolerance_kind="absolute",
                normalized_difference=fnum(dist / tol.slope_distribution_deg, 3) if dist is not None else None,
                status="not_assessed" if dist is None else ("within_tolerance" if dist <= tol.slope_distribution_deg else "outside_tolerance"),
                reason="Wasserstein (earth mover's) distance between the two slope histograms." if dist is not None else "Histograms are not comparable.",
            )
        )
        criteria.append(
            _criterion(
                "roughness_rms_height_median", scale, "metres",
                r.roughness.rms_height_m.median, c.roughness.rms_height_m.median, tol.roughness_rel, "relative",
            )
        )

    # Relief is only comparable when both the window and the grid it was measured on match.
    for rr in reference.relief:
        match = next(
            (cr for cr in candidate.relief if abs(cr.window_m - rr.window_m) <= 0.05 * rr.window_m and abs(cr.grid_m - rr.grid_m) <= 0.05 * rr.grid_m),
            None,
        )
        metric = f"relief_median_{rr.window_m:g}m_window"
        if match is None:
            criteria.append(
                _criterion(metric, rr.grid_m, "metres", rr.stats.median, None, tol.relief_rel, "relative",
                           "Candidate has no relief measurement with the same window and grid spacing.")
            )
        else:
            criteria.append(_criterion(metric, rr.grid_m, "metres", rr.stats.median, match.stats.median, tol.relief_rel, "relative"))

    counts = {"within_tolerance": 0, "outside_tolerance": 0, "not_assessed": 0}
    for c in criteria:
        counts[c.status] += 1
    notes.append("Counts are a tally of criteria, not a similarity score. Read each criterion with its scale and tolerance.")
    notes.append("Tolerances are screening assumptions chosen by the user, not validated mission thresholds.")

    return ComparisonResult(
        common_scales_m=common,
        criteria=criteria,
        counts=counts,
        notes=notes,
        tolerances=tol,
        reference_profile=reference,
        candidate_profile=candidate,
    )
