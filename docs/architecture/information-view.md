# Information view

Primary artifacts:

- RGB orthophoto: `data/odm_project_rgb/project/odm_orthophoto/odm_orthophoto.tif`
- MAPIR orthophoto: `data/odm_project_mapir/project/odm_orthophoto/odm_orthophoto.tif`
- Vegetation index raster: `output/ndvi/ndvi.tif`
- Vegetation index metadata: `output/ndvi/metadata.json`
- Grid overlay/table artifacts: `output/ndvi/*`
- Weather artifacts: `output/weather/*`
- Irrigation artifacts: `output/irrigation/*`
- Final report: `output/report_latest.html`

Stage contracts are represented by `agrivision.domain.models` so downstream consumers can reason about outputs without discovering fields ad hoc.
