# Offline And Edge Operation

Use `config/config.edge.yaml` as the starting point for constrained or intermittently connected environments.

Recommended practices:

- pre-stage imagery and Docker images locally
- add credentials through environment variables when network access is available
- validate the environment with `python run.py --doctor` before field execution
- preserve generated metadata files alongside copied artifacts

## Field Use

AgriVision supports field workflows where imagery is already present on the machine. Orthophoto generation and vegetation analysis can run without live internet access once Docker images and dependencies are available locally.

OpenAgri services remain part of the system:

- Weather data depends on the configured Weather Service and available cached data.
- Irrigation and Pest & Disease services should be started and authenticated before field operation.
- If a field run is completed while disconnected, review OpenAgri service status before using the final report.

## Low-Resource Recommendations

- Use the dashboard Orthophoto Creation quality presets, starting with `Preview` or `Balanced`.
- Keep Docker Desktop memory high enough for ODM on Windows; large image sets can be killed by the container runtime.
- Export run packages after successful analysis so `manifest.json`, `metadata/run_metadata.jsonld`, rasters, and report files can move together.

## Hardware Notes

The standard operator paths are Windows Docker Desktop and Linux Docker. ARM or Raspberry Pi deployments require project-specific validation for the device, operating system, and Docker image architecture before field use.
