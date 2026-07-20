# Data Flow

## End-To-End Sequence

1. load configuration and environment overrides
2. resolve project, input, and output paths
3. run or reuse ODM orthophoto generation
4. compute vegetation-index products
5. generate grid classifications and summaries
6. fetch or map required OpenAgri service data
7. write metadata and report assets
8. render the HTML report

## Control Flow Notes

- doctor/setup/cleanup commands exit before pipeline execution
- stage selection is controlled by dashboard settings, CLI flags, and configuration
- OpenAgri service issues are reported in service and enrichment outputs

## Artifact Boundaries

Inputs and outputs are exchanged between stages through named files and metadata helpers under `agrivision.pipeline.io`. This keeps stage interfaces inspectable and testable.
