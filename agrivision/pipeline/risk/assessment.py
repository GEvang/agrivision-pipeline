"""Turn technical PDM and spatial-risk results into one field-level decision."""

from __future__ import annotations

from typing import Any

_PDM_SCORES = {"very low": 0.0, "low": 0.22, "moderate": 0.40, "medium": 0.40, "high": 0.60, "very high": 0.78, "critical": 0.93}


def risk_category(score: float | None) -> str:
    if score is None:
        return "Unavailable"
    if score < 0.15:
        return "Very Low"
    if score < 0.30:
        return "Low"
    if score < 0.50:
        return "Medium"
    if score < 0.70:
        return "High"
    if score < 0.85:
        return "Very High"
    return "Critical"


def _pdm_score(summary: dict[str, Any] | None) -> float | None:
    level = str((summary or {}).get("risk_level") or "").strip().casefold()
    return _PDM_SCORES.get(level)


def _selected_layer(risk_summary: dict[str, Any], pdm_summary: dict[str, Any] | None) -> dict[str, Any] | None:
    layers = [layer for layer in risk_summary.get("layers", []) if isinstance(layer, dict)]
    model_key = str((pdm_summary or {}).get("selected_model_key") or "")
    profile_key = model_key.removesuffix("_risk_v1")
    for layer in layers:
        if layer.get("profile_key") == profile_key:
            return layer
    selected_key = risk_summary.get("selected_layer_key")
    return next((layer for layer in layers if layer.get("profile_key") == selected_key), layers[0] if layers else None)


def build_field_assessment(
    risk_summary: dict[str, Any] | None, pdm_summary: dict[str, Any] | None
) -> dict[str, Any]:
    """Create an auditable, conservative field conclusion.

    The PDM and UAV spatial outputs remain independent evidence streams. The
    field status takes the higher available concern, rather than averaging away
    a high warning from either source.
    """
    risk_summary = risk_summary or {}
    layer = _selected_layer(risk_summary, pdm_summary)
    spatial_score = layer.get("mean_risk") if layer else None
    try:
        spatial_score = float(spatial_score) if spatial_score is not None else None
    except (TypeError, ValueError):
        spatial_score = None
    pdm_score = _pdm_score(pdm_summary)
    score = max(value for value in (spatial_score, pdm_score) if value is not None) if any(
        value is not None for value in (spatial_score, pdm_score)
    ) else None
    status = risk_category(score)
    label = str((layer or {}).get("profile_label") or (pdm_summary or {}).get("display_label") or "Selected crop risk")
    high_cells = int((layer or {}).get("high_or_above_cells") or 0)
    valid_cells = int((layer or {}).get("valid_cells") or 0)
    affected_percent = round((100 * high_cells / valid_cells), 1) if valid_cells else None

    if status in {"High", "Very High", "Critical"}:
        action, timeframe = "Prioritise field scouting in the mapped priority zones and ask an agronomist to review confirmed symptoms.", "within 24–48 hours"
    elif status == "Medium":
        action, timeframe = "Inspect mapped priority zones and nearby plants before deciding whether intervention is needed.", "within 2–3 days"
    elif status in {"Low", "Very Low"}:
        action, timeframe = "Continue routine monitoring; inspect any isolated mapped anomalies during the next field visit.", "during the next routine visit"
    else:
        action, timeframe = "No field conclusion is available until weather and risk-layer processing complete.", "not available"

    evidence = []
    if spatial_score is not None:
        evidence.append("UAV spatial risk layer")
    if pdm_score is not None:
        evidence.append("PDM weather-driven risk")
    missing = ["phenology", "historical pressure", "soil/irrigation context", "thermal anomaly"]
    confidence = "Partial" if len(evidence) >= 2 else "Limited" if evidence else "Unavailable"
    pdm_guidance = str((pdm_summary or {}).get("recommendation") or "").strip()
    return {
        "status": status,
        "score": score,
        "target": label,
        "spatial_score": spatial_score,
        "pdm_score": pdm_score,
        "evidence": evidence,
        "confidence": confidence,
        "high_risk_cells": high_cells,
        "valid_cells": valid_cells,
        "affected_area_percent": affected_percent,
        "recommended_action": action,
        "recommended_timeframe": timeframe,
        "disease_specific_guidance": pdm_guidance,
        "missing_inputs": missing,
        "method": "Higher of the available PDM and UAV spatial risk signals; the sources are retained separately for review.",
    }
