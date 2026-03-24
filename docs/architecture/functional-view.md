# Functional view

Main flow:

1. Optional resize of RGB and MAPIR images.
2. ODM execution for RGB and, when available, MAPIR imagery.
3. Vegetation index generation.
4. Grid classification and overlay rendering.
5. Weather enrichment.
6. Irrigation enrichment.
7. HTML report creation.

The canonical orchestrator is `agrivision.pipeline.orchestrator.run_full_pipeline`.
