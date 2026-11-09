import numpy as np

from agrivision.pipeline.grid.classify import (
    classify_value_absolute,
    make_grid,
    row_letter,
)


def test_row_letter_supports_single_and_double_letters() -> None:
    assert row_letter(0) == "A"
    assert row_letter(25) == "Z"
    assert row_letter(26) == "AA"



def test_classify_value_absolute_handles_none_and_thresholds() -> None:
    assert classify_value_absolute(None, 0.2, 0.5) == "no_data"
    assert classify_value_absolute(0.1, 0.2, 0.5) == "poor"
    assert classify_value_absolute(0.3, 0.2, 0.5) == "medium"
    assert classify_value_absolute(0.7, 0.2, 0.5) == "good"



def test_make_grid_returns_expected_cell_ids_and_means() -> None:
    arr = np.array([[0.1, 0.2], [0.7, 0.8]], dtype="float32")

    def classifier(value: float | None) -> str:
        return classify_value_absolute(value, 0.3, 0.6)

    cells, _, _ = make_grid(arr, classifier, grid_rows=2, grid_cols=2)
    assert [cell["cell_id"] for cell in cells] == ["A1", "A2", "B1", "B2"]
    assert cells[0]["class"] == "poor"
    assert cells[3]["class"] == "good"


def test_pseudo_index_uses_rgb_profile_thresholds() -> None:
    from agrivision.pipeline.stages.grid import _thresholds_for_index

    rgb_profile = {"poor_max": 0.0, "medium_max": 0.08}

    assert _thresholds_for_index("pseudo", rgb_profile, 0.25, 0.4) == (0.0, 0.08)
    assert _thresholds_for_index("nir_red", rgb_profile, 0.25, 0.4) == (0.25, 0.4)
    assert _thresholds_for_index("pseudo", {}, 0.25, 0.4) == (0.25, 0.4)
