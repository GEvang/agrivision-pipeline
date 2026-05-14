# Interoperability notes

AgriVision participates in an OpenAgri-style ecosystem primarily through file-based and configuration-based contracts.

## Stable exchange surfaces

- CLI flags and exit behavior
- YAML and environment-based configuration
- stage output folders and metadata files
- normalized enrichment payloads derived from weather and irrigation providers

## Recommendations for downstream consumers

- pin the repository version used in production;
- consume artifacts through documented paths rather than log parsing;
- preserve geospatial metadata when moving outputs to other systems;
- map provider-native enrichment to normalized internal fields before reuse; and
- document any additional schema introduced by downstream processing.

## Semantic exports

Run export packages include `metadata/run_metadata.jsonld`. This file provides stable run, dataset, processing-step, parameter, and artifact identifiers for OpenAgri-style interchange. It is intentionally additive: the pipeline still writes simple JSON, CSV, GeoTIFF, PNG, and HTML artifacts for local operators, while the JSON-LD metadata gives downstream systems a semantic entry point.

The current JSON-LD context uses Schema.org terms plus OpenAgri/OCSM-oriented identifiers. Future hardening should replace provisional OpenAgri terms with the canonical OCSM vocabulary once the target classes/properties are fixed for this ADS.

## Reporting service boundary

AgriVision currently renders local HTML reports inside the ADS because reports combine drone-derived rasters, grid overlays, OpenAgri Weather summaries, Irrigation outputs, and Pest & Disease results. This keeps field operation independent from a remote reporting dependency.

For stricter reuse of the OpenAgri Reporting Service, add an optional adapter that sends a package manifest or JSON-LD payload to the Reporting Service and stores the returned PDF/report artifact next to the local HTML report. That adapter should be optional so offline/edge runs can continue using local reporting.
