# Deployment and operation view

Supported operational profiles:

- `standalone`: AgriVision pipeline only.
- `docker-local`: AgriVision container with Docker socket access for ODM.
- `docker-with-openagri-services`: AgriVision plus sibling Weather/Irrigation services.
- `edge-offline`: offline-friendly execution with previously provisioned services.

Deployment-oriented helpers live under `agrivision.runtime` and scripts live under `deployment/`.
