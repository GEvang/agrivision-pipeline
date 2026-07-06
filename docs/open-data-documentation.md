# Open Data Documentation

This repository is software first. It does not publish a standalone reference dataset, but it does define the generated artifact structure that operators and downstream systems consume.

## Scope

AgriVision produces run-specific data products from uploaded imagery and optional OpenAgri enrichments. These outputs are operational artifacts, not a curated public dataset release.

## Main Data Products

- uploaded image manifests under `data/uploads/<upload_id>/`
- run state under `runtime/runs/<run_id>/`
- reports and orthophotos under `output/runs/<run_id>/`
- ZIP export packages under `runtime/exports/`
- JSON-LD run metadata in `metadata/run_metadata.jsonld`

## Common Formats

- image uploads: JPEG/JPG and other accepted image formats
- rasters and orthophotos: GeoTIFF
- previews and overlays: PNG
- tabular analysis outputs: CSV
- run metadata and service outputs: JSON
- semantic export metadata: JSON-LD
- reports: HTML
- downloadable run bundles: ZIP

## Provenance

Typical provenance chain:

1. operator uploads imagery or imports an orthophoto
2. AgriVision validates the input set
3. ODM and downstream analysis stages generate artifacts
4. optional service enrichments add weather, irrigation, or PDM context
5. AgriVision writes reports, metadata, and export packages

## Export Package Contract

Run packages may contain:

- `manifest.json`
- `metadata/run_metadata.jsonld`
- `run/status.json`
- `run/params.json`
- `run/outputs.json`
- `run/run.log`
- report, raster, quality, and risk artifacts when present

Contents vary by selected steps and run success.

## Data Quality Notes

The repository validates inputs and API payloads, but it does not define universal agronomic accuracy guarantees for all generated outputs. Quality depends on:

- input imagery quality
- ODM success
- selected analysis steps
- external service availability

## Privacy and Distribution

Raw uploaded imagery may contain geolocation and sensitive field context. Public distribution, if any, should be a deliberate downstream decision. This repository does not define a public dataset publication workflow.
