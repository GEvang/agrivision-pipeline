# Data flow

## End-to-end sequence

1. load configuration and environment overrides;
2. resolve project, input, and output paths;
3. optionally resize source imagery;
4. run or reuse ODM orthophoto generation;
5. compute vegetation-index products;
6. generate grid classifications and summaries;
7. fetch or map weather and irrigation enrichment data;
8. write metadata and report assets;
9. render the HTML report.

## Control flow notes

- doctor/setup/cleanup commands exit before pipeline execution;
- stage skipping is controlled by CLI flags and configuration;
- external-service failures should remain isolated to enrichment paths where possible.

## Artifact boundaries

Inputs and outputs are exchanged between stages through named files and metadata helpers under `agrivision.pipeline.io`. This keeps stage interfaces inspectable and testable.
