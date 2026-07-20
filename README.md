# AgriVision

AgriVision helps farm teams turn drone imagery into orthophotos, vegetation analysis, disease-risk outputs, reports, and export packages. It is designed to run with the required OpenAgri Weather, Irrigation, and Pest & Disease services.

## Installation

Use one of the provided start files:

- Windows: `Start AgriVision Windows.bat`
- Linux: `Start AgriVision Linux.sh`
- macOS: `Start AgriVision macOS.command`

Or start with Docker:

```bash
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:8008
```

Before field analysis, confirm the required OpenAgri Weather, Irrigation, and Pest & Disease services are configured and reachable from the Settings page.

## Usage

1. Open the dashboard.
2. Upload drone imagery or import an existing orthophoto.
3. Create a run and select the required analysis steps.
4. Review the run status.
5. Download the report or export package.

## Configuration

- Non-secret settings are stored in `config.yaml` and `runtime/settings.json`.
- Secrets belong in `.env` or host environment variables.
- Start from `.env.example` for supported environment variable names.
- The dashboard listens on port `8008`.
- Persistent operator data is stored under `data/`, `output/`, and `runtime/`.

## Documentation

- Deployment: `DEPLOYMENT.md`
- API reference: `docs/api/README.md`
- Architecture: `docs/architecture/overview.md`
- Testing: `docs/developer/testing.md`
- Open-source summary: `docs/open-source-software-documentation.md`
- Contribution and support: `CONTRIBUTING.md`

## API Docs

When the dashboard is running:

- OpenAPI JSON: `http://127.0.0.1:8008/openapi.json`
- Swagger UI: `http://127.0.0.1:8008/docs`
- ReDoc: `http://127.0.0.1:8008/redoc`

## License

This repository is licensed under the European Union Public Licence (EUPL) v1.2. See `LICENSE`.
