# AgriVision Pipeline

AgriVision is an OpenAgri-oriented drone imagery pipeline that produces orthophotos, vegetation index artifacts, grid-based field summaries, service enrichments, and an HTML report.

## Repository layout

- `agrivision/app` — CLI and operational commands
- `agrivision/config` — config loading and typed settings
- `agrivision/domain` — stage contracts and run models
- `agrivision/pipeline` — core processing flow and stage logic
- `agrivision/integrations` — Weather and Irrigation adapters
- `agrivision/runtime` — deployment/bootstrap helpers
- `deployment/` — Docker and operational scripts
- `docs/` — architecture, operator, and developer documentation

## Quick start

```bash
python run.py --doctor
python run.py --run-resize
```

## Documentation

- Architecture: `docs/architecture/`
- Operator docs: `docs/operator/`
- Developer docs: `docs/developer/`
- Deployment assets: `deployment/`
