# Interoperability Notes

AgriVision participates in an OpenAgri-style ecosystem primarily through file-based and configuration-based contracts.

## Stable Exchange Surfaces

- CLI flags and exit behavior
- YAML and environment-based configuration
- stage output folders and metadata files
- normalized enrichment payloads derived from OpenAgri providers

## Recommendations For Downstream Consumers

- pin the repository version used in production
- consume artifacts through documented paths rather than log parsing
- preserve geospatial metadata when moving outputs to other systems
- map provider-native enrichment to normalized internal fields before reuse
- document any additional schema introduced by downstream processing

## Semantic Exports

Run export packages include `metadata/run_metadata.jsonld`. This file provides stable run, dataset, processing-step, parameter, and artifact identifiers for OpenAgri-style interchange. It is intentionally additive: the pipeline still writes simple JSON, CSV, GeoTIFF, PNG, and HTML artifacts for local operators, while the JSON-LD metadata gives downstream systems a semantic entry point.

The JSON-LD context uses Schema.org terms plus OpenAgri/OCSM-oriented identifiers. When the canonical OCSM vocabulary is fixed for this ADS, align the export identifiers with those target classes and properties.

## Reporting Service Boundary

AgriVision currently renders local HTML reports inside the ADS because reports combine drone-derived rasters, grid overlays, OpenAgri Weather summaries, Irrigation outputs, and Pest & Disease results. This keeps field operation independent from a remote reporting dependency.

For stricter reuse of the OpenAgri Reporting Service, add a reporting adapter that sends a package manifest or JSON-LD payload to the Reporting Service and stores the returned PDF/report artifact next to the local HTML report. Offline and edge runs can continue using the local HTML report renderer when the remote reporting service is not part of the deployment.
