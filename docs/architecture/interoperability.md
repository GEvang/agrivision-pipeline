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
