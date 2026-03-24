# Information view

AgriVision exchanges information through a small number of stable object families.

## Primary information objects

### Run configuration

Configuration is the control-plane input to the system. It determines project roots, stage toggles, service endpoints, credentials, and output locations.

### Input imagery

Raw or resized drone imagery acts as the primary data-plane input.

### Derived geospatial artifacts

The pipeline derives:

- orthophotos
- vegetation-index rasters
- grid summaries
- auxiliary metadata

### Enrichment data

Weather and irrigation services provide contextual data that can augment reports and downstream decision support.

### Reporting outputs

HTML output and associated assets are the final user-facing information products.

## Information ownership by module

- `config` owns validated settings.
- `pipeline.io` owns artifact path and metadata conventions.
- `integrations` owns payload translation boundaries.
- `services` owns provider-native payload handling.
- `report` owns rendered presentation artifacts.

## Interoperability principles

To keep outputs reusable across OpenAgri-style systems:

- preserve metadata near artifacts;
- avoid embedding credentials in persisted outputs;
- keep units and timestamps explicit;
- prefer normalized enrichment structures over provider-native ad hoc payloads; and
- document folder and file conventions as part of the contract.
