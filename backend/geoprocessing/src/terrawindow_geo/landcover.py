"""Land-cover screening with ESA WorldCover classes."""

from __future__ import annotations

import numpy as np

from .models import LandCoverClass, LandCoverRule, LandCoverSummary

WORLDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


def summarize(classes: np.ndarray, rule: LandCoverRule | None = None, dataset: str = "ESA WorldCover 10 m 2021 v200") -> LandCoverSummary:
    """Class fractions of a class-code array (NaN or 0 = no data), plus the screening verdict."""
    codes = classes[np.isfinite(classes)].astype(np.int32)
    codes = codes[codes > 0]
    total = classes.size
    if codes.size == 0:
        return LandCoverSummary(
            dataset=dataset, valid_fraction=0.0, classes=[], dominant_class=None, reason="No land-cover data over this patch."
        )
    values, counts = np.unique(codes, return_counts=True)
    fractions = counts / codes.size
    order = np.argsort(-fractions)
    listed = [
        LandCoverClass(code=int(values[i]), label=WORLDCOVER_CLASSES.get(int(values[i]), "Unknown"), fraction=round(float(fractions[i]), 4))
        for i in order
    ]
    summary = LandCoverSummary(
        dataset=dataset,
        valid_fraction=round(codes.size / total, 4),
        classes=listed,
        dominant_class=listed[0].code,
    )
    if rule is not None:
        excluded = float(sum(c.fraction for c in listed if c.code in rule.excluded_classes))
        summary.excluded_fraction = round(excluded, 4)
        if excluded > rule.max_excluded_fraction:
            worst = max((c for c in listed if c.code in rule.excluded_classes), key=lambda c: c.fraction)
            summary.screen = "fail"
            summary.reason = (
                f"{excluded:.0%} of the patch is in excluded classes (limit {rule.max_excluded_fraction:.0%}); "
                f"mostly {worst.label.lower()}."
            )
        else:
            summary.screen = "pass"
    return summary
