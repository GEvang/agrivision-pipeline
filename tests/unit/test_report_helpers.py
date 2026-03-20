from agrivision.pipeline.report.assets import get_index_title
from agrivision.pipeline.report.tables import render_grid_table


def test_get_index_title_prefers_metadata_index_name() -> None:
    ndvi_meta = {"index": {"index_name": "GNDVI-like"}}
    grid_meta = {"index_name": "Vegetation Index"}
    assert get_index_title(ndvi_meta, grid_meta) == "GNDVI-like"



def test_render_grid_table_uses_mean_index_and_class() -> None:
    html = render_grid_table(
        "Vegetation Index",
        [{
            "cell_id": "A1",
            "row_label": "A",
            "col_label": "1",
            "mean_index": "0.4321",
            "class": "good",
        }],
    )
    assert "A1" in html
    assert "0.4321" in html
    assert "class-good" in html
