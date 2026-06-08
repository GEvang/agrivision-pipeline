# Data flow

## End-to-end sequence

1. load configuration and environment overrides;
2. resolve project, input, and output paths;
3. run or reuse ODM orthophoto generation;
4. compute vegetation-index products;
5. generate grid classifications and summaries;
6. fetch or map weather and irrigation enrichment data;
7. write metadata and report assets;
8. render the HTML report.

## Control flow notes

- doctor/setup/cleanup commands exit before pipeline execution;
- stage skipping is controlled by CLI flags and configuration;
- external-service failures should remain isolated to enrichment paths where possible.

## Artifact boundaries

Inputs and outputs are exchanged between stages through named files and metadata helpers under `agrivision.pipeline.io`. This keeps stage interfaces inspectable and testable.
