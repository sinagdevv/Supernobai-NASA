"""Lazy dispatcher for strictly single-body temporal rehearsal evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping

from .temporal import (
    RehearsalCriteria,
    RehearsalEvaluation,
)


@dataclass(frozen=True)
class TemporalEvaluationRequest:
    """One selected body's temporal request; no fields exist for other bodies."""

    body: str
    terrain: object
    start_utc: datetime
    end_utc: datetime
    step: timedelta
    kernels: object
    criteria: RehearsalCriteria = field(default_factory=RehearsalCriteria)
    body_options: Mapping[str, object] = field(default_factory=dict)


def dispatch_temporal_evaluation(
    request: TemporalEvaluationRequest,
) -> RehearsalEvaluation:
    """Run only the engine selected by ``request.body`` using lazy imports."""
    if not isinstance(request, TemporalEvaluationRequest):
        raise TypeError("request must be a TemporalEvaluationRequest")
    if request.body not in ("earth", "moon", "mars"):
        raise ValueError("body must be exactly 'earth', 'moon', or 'mars'")
    if not isinstance(request.criteria, RehearsalCriteria):
        raise TypeError("criteria must be a RehearsalCriteria")

    arguments = dict(request.body_options)
    reserved = {"terrain", "start_utc", "end_utc", "step", "kernels", "criteria"}
    overlap = reserved.intersection(arguments)
    if overlap:
        raise ValueError(
            "body_options may not override request fields: "
            + ", ".join(sorted(overlap))
        )
    arguments.update(
        {
            "terrain": request.terrain,
            "start_utc": request.start_utc,
            "end_utc": request.end_utc,
            "step": request.step,
            "kernels": request.kernels,
            "criteria": request.criteria,
        }
    )

    if request.body == "earth":
        from ..earth.temporal import evaluate_earth_rehearsal_windows

        evaluator = evaluate_earth_rehearsal_windows
    elif request.body == "moon":
        from ..lunar.temporal import evaluate_lunar_rehearsal_windows

        evaluator = evaluate_lunar_rehearsal_windows
    else:
        from ..mars.temporal import evaluate_mars_rehearsal_windows

        evaluator = evaluate_mars_rehearsal_windows
    return evaluator(**arguments)


def evaluate_selected_body(
    body: str,
    terrain: object,
    start_utc: datetime,
    end_utc: datetime,
    step: timedelta,
    *,
    kernels: object,
    criteria: RehearsalCriteria | None = None,
    body_options: Mapping[str, object] | None = None,
) -> RehearsalEvaluation:
    """Convenience entry point that accepts only selected-body inputs."""
    return dispatch_temporal_evaluation(
        TemporalEvaluationRequest(
            body=body,
            terrain=terrain,
            start_utc=start_utc,
            end_utc=end_utc,
            step=step,
            kernels=kernels,
            criteria=criteria or RehearsalCriteria(),
            body_options={} if body_options is None else dict(body_options),
        )
    )
