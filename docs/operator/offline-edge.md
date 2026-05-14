# Offline and edge operation

Use `config/config.edge.yaml` as the starting point for constrained or intermittently connected environments.

Recommended practices:

- pre-stage imagery and dependencies locally;
- inject credentials through environment variables when network access is available;
- validate the environment with `python run.py --doctor` before field execution; and
- preserve generated metadata files alongside copied artifacts.

## Current support level

AgriVision currently supports an offline-capable local workflow for imagery already present on the machine. Orthophoto generation and vegetation analysis can run without network access once Docker images and Python dependencies are available locally.

External OpenAgri services have different offline characteristics:

- Weather data depends on the configured Weather Service and its cache state.
- Irrigation and Pest & Disease services should be started and authenticated before field operation if they are required during the run.
- If service enrichment is not required, disable those steps in the dashboard or use the corresponding CLI skip flags.

## Low-resource recommendations

- Use the dashboard Orthophoto Creation quality presets, starting with `Preview` or `Balanced`.
- Use reduced images for first-pass field validation.
- Keep Docker Desktop memory high enough for ODM on Windows; large image sets can be killed by the container runtime.
- Export run packages after successful analysis so `manifest.json`, `metadata/run_metadata.jsonld`, rasters, and report files can move together.

## Validation status

The current release is validated on Windows Docker Desktop and local Python development flows. ARM/Raspberry Pi deployment is a target profile, but it should be treated as not yet validated until a release is tested on the specific edge hardware and Docker image architecture.
