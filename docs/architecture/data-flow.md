# Data flow

```text
Drone images
  -> Resize (optional)
  -> ODM orthophoto generation
  -> Vegetation index generation
  -> Grid classification and overlay rendering
  -> Weather enrichment
  -> Irrigation enrichment
  -> HTML report
```

## Stage inputs and outputs

- **Resize** reads raw RGB and MAPIR folders and writes normalized image folders.
- **ODM** reads prepared image folders and writes orthophoto artifacts under `data/odm_project_*`.
- **Vegetation index** reads orthophotos and writes raster plus metadata under `output/ndvi/`.
- **Grid** reads NDVI artifacts and writes overlays, tabular summaries, and intermediate metadata.
- **Weather/Irrigation enrichment** read grid and config context, then write service artifacts under `output/weather/` and `output/irrigation/`.
- **Report** gathers artifacts from earlier stages and writes `output/report_latest.html`.
