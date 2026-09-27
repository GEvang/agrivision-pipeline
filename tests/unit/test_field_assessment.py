from agrivision.pipeline.risk.assessment import build_field_assessment


def test_field_assessment_uses_the_higher_independent_risk_signal() -> None:
    assessment = build_field_assessment(
        {
            "selected_layer_key": "grapevine_powdery_mildew",
            "layers": [{"profile_key": "grapevine_powdery_mildew", "profile_label": "Powdery Mildew", "mean_risk": 0.18, "high_or_above_cells": 2, "valid_cells": 20}],
        },
        {
            "selected_model_key": "grapevine_powdery_mildew_risk_v1",
            "risk_level": "High",
            "display_label": "Powdery Mildew",
            "recommendation": "Inspect susceptible canopy zones.",
        },
    )

    assert assessment["status"] == "High"
    assert assessment["score"] == 0.60
    assert assessment["affected_area_percent"] == 10.0
    assert assessment["confidence"] == "Partial"
    assert assessment["disease_specific_guidance"] == "Inspect susceptible canopy zones."


def test_field_assessment_marks_one_evidence_stream_as_limited() -> None:
    assessment = build_field_assessment(
        {"layers": [{"profile_key": "x", "profile_label": "X", "mean_risk": 0.22, "valid_cells": 4}]},
        {},
    )

    assert assessment["confidence"] == "Limited"
    assert "thermal anomaly" in assessment["missing_inputs"]
