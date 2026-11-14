"""Markdown and PDF dossiers rendered from a stored run. No measurements are computed here."""

from __future__ import annotations

from datetime import datetime, timezone

from fpdf import FPDF

from . import TEMPLATE_VERSION
from .canonical import canonical_json, sha256_bytes
from .shapes import ReportError

DISCLAIMER = (
    "TERRAWINDOW research record. This dossier reproduces a stored analysis run. "
    "It is not an official NASA qualification and it certifies no site."
)

RECOMMENDATIONS = [
    "Ground-truth the elevation model across the candidate area before treating the grid as the surface a rover would drive.",
    "Count rocks and measure soil strength in the field. Terrain metrics do not establish either one.",
    "Survey the real horizon from the planned start point. This record does not calculate terrain shadows.",
    "Confirm access, weather, and a fallback date before a rehearsal.",
]


def _utc(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pretty(value) -> str:
    return canonical_json(value)


def report_title(run: dict) -> str:
    names = [item["dataset_id"] for item in run.get("datasets") or []]
    kind = run.get("kind") or "run"
    if names:
        return f"{kind} · " + " · ".join(names)
    return f"{kind} · {run.get('run_id')}"


def _criteria_lines(result: dict) -> list[str]:
    criteria = result.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return []
    lines = ["## Criteria", "", "| Metric | Scale (m) | Reference | Candidate | Difference | Status |", "|---|---:|---:|---:|---:|---|"]
    for item in criteria:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {metric} | {scale} | {reference} | {candidate} | {difference} | {status} |".format(
                metric=item.get("metric") or "",
                scale="" if item.get("scale_m") is None else item.get("scale_m"),
                reference="" if item.get("reference") is None else item.get("reference"),
                candidate="" if item.get("candidate") is None else item.get("candidate"),
                difference="" if item.get("difference") is None else item.get("difference"),
                status=item.get("status") or "",
            )
        )
    counts = result.get("counts")
    if isinstance(counts, dict):
        lines.extend(["", "Criterion counts: " + ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))])
    return lines


def _scale_lines(result: dict) -> list[str]:
    scales = result.get("scales")
    if not isinstance(scales, list) or not scales:
        return []
    lines = ["## Scales", "", "| Scale (m) | Status | Coverage | Slope mean (deg) | RMS height median (m) |", "|---:|---|---:|---:|---:|"]
    for item in scales:
        if not isinstance(item, dict):
            continue
        slope = ((item.get("slope") or {}).get("stats") or {}).get("mean")
        rough = (((item.get("roughness") or {}).get("rms_height_m") or {}).get("median"))
        lines.append(
            f"| {item.get('scale_m')} | {item.get('status')} | {item.get('coverage_fraction')} | {slope if slope is not None else ''} | {rough if rough is not None else ''} |"
        )
    return lines


def _screen_lines(result: dict) -> list[str]:
    if result.get("type") != "FeatureCollection":
        return []
    summary = result.get("summary") or {}
    lines = ["## Candidate shortlist", ""]
    if summary:
        lines.append(
            "Cells {cells}. Candidate {candidate}. Rejected {rejected}. Insufficient data {insufficient}.".format(
                cells=summary.get("cells"),
                candidate=summary.get("candidate"),
                rejected=summary.get("rejected"),
                insufficient=summary.get("insufficient_data"),
            )
        )
        lines.append(f"Scale {summary.get('scale_m')} m. Patch {summary.get('patch_size_m')} m.")
        lines.append("")
    lines.extend(["| Patch | Status | Latitude | Longitude | Slope mean (deg) |", "|---|---|---:|---:|---:|"])
    shown = 0
    for feature in result.get("features") or []:
        props = (feature or {}).get("properties") or {}
        if props.get("status") != "candidate":
            continue
        metrics = props.get("metrics") or {}
        lines.append(
            f"| {props.get('id')} | candidate | {props.get('center_lat')} | {props.get('center_lon')} | {metrics.get('slope_mean_deg')} |"
        )
        shown += 1
    if shown == 0:
        lines.append("| — | — | — | — | — |")
    lines.extend(["", "Rejected patches stay in the candidate table and are omitted from this shortlist."])
    return lines


def _limitation_lines(result: dict) -> list[str]:
    found: list[str] = []
    if isinstance(result.get("limitations"), list):
        found.extend(str(item) for item in result["limitations"])
    for side in ("reference_profile", "candidate_profile"):
        profile = result.get(side) or {}
        if isinstance(profile.get("limitations"), list):
            found.extend(str(item) for item in profile["limitations"])
    if not found:
        return []
    unique = list(dict.fromkeys(found))
    return ["## Limitations stored with the result", "", *[f"- {item}" for item in unique]]


def build_markdown(run: dict, generated_at: datetime) -> str:
    if run.get("status") != "completed":
        raise ReportError("run_not_completed", "A dossier is generated only for a completed run.", 409)
    result = run.get("result") or {}
    lines = [
        f"# TERRAWINDOW research dossier",
        "",
        f"_{report_title(run)}_",
        "",
        f"> {DISCLAIMER}",
        "",
        "## Record",
        "",
        f"- Template version: {TEMPLATE_VERSION}",
        f"- Generated: {_utc(generated_at)}",
        f"- Run: {run.get('run_id')}",
        f"- Status: {run.get('status')}",
        f"- Engine version: {run.get('engine_version')}",
        f"- Request hash: {run.get('request_hash')}",
        f"- Result hash: {run.get('result_hash')}",
        "",
        "## Analysis configuration",
        "",
        "```json",
        _pretty(run.get("request")),
        "```",
        "",
        "## Input datasets",
        "",
        "| Role | Dataset | Checksum recorded for this run |",
        "|---|---|---|",
    ]
    for item in run.get("datasets") or []:
        lines.append(f"| {item.get('role')} | {item.get('dataset_id')} | {item.get('sha256')} |")
    if not run.get("datasets"):
        lines.append("| — | — | — |")
    lines.append("")
    for block in (_criteria_lines(result), _scale_lines(result), _screen_lines(result), _limitation_lines(result)):
        if block:
            lines.extend(block)
            lines.append("")
    notes = result.get("notes")
    if isinstance(notes, list) and notes:
        lines.extend(["## Notes stored with the result", "", *[f"- {note}" for note in notes], ""])
    lines.extend(
        [
            "## Reproducibility",
            "",
            "The run stores the engine version, the canonical request, the result document, and the dataset checksum at recording time.",
            "A later change to the dataset registry does not rewrite this run.",
            "Verification recomputes the result hash, compares each recorded checksum with the registry and with the GeoTIFF when the file is on disk, and recomputes the PDF checksum.",
            "",
            "## Recommendations",
            "",
            "These are checks this record does not perform.",
            "",
            *[f"{index}. {step}" for index, step in enumerate(RECOMMENDATIONS, start=1)],
            "",
        ]
    )
    return "\n".join(lines)


def _pdf_text(text: str) -> str:
    replaced = (
        text.replace("\u00b0", " deg")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u00a0", " ")
    )
    folded = []
    for token in replaced.split(" "):
        if len(token) <= 90:
            folded.append(token)
        else:
            folded.extend(token[index : index + 90] for index in range(0, len(token), 90))
    return " ".join(folded).encode("latin-1", "replace").decode("latin-1")


def build_pdf(markdown: str) -> bytes:
    pdf = FPDF()
    # Fixed metadata so the PDF checksum depends on the dossier text, not the clock.
    pdf.set_creation_date(datetime(2026, 1, 1))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for paragraph in markdown.split("\n"):
        pdf.multi_cell(0, 5, _pdf_text(paragraph if paragraph else " "), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def render_report(run: dict, generated_at: datetime | None = None) -> dict:
    when = generated_at or datetime.now(timezone.utc)
    markdown = build_markdown(run, when)
    pdf = build_pdf(markdown)
    return {
        "title": report_title(run),
        "template_version": TEMPLATE_VERSION,
        "generated_at": when,
        "markdown": markdown,
        "pdf": pdf,
        "pdf_sha256": sha256_bytes(pdf),
    }
