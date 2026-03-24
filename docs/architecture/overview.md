# Architecture overview

AgriVision is split into five bounded areas:

1. `agrivision.app` — CLI and operational entrypoints.
2. `agrivision.config` — merged configuration and typed settings.
3. `agrivision.pipeline` — orthophoto, vegetation index, grid, and report orchestration.
4. `agrivision.integrations` — business-facing adapters for Weather and Irrigation services.
5. `agrivision.runtime` — deployment, environment, service bootstrap, and Docker helpers.

The existing implementation was preserved, but runtime and integration concerns are now separated structurally so the codebase maps more clearly to OpenAgri ADS expectations.
