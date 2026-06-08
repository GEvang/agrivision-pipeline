# Troubleshooting

## Installation issues

- rerun `./install_agrivision.sh`
- activate `.venv` with `source .venv/bin/activate`
- validate with `python run.py --doctor`
- install GDAL tools if `gdalinfo` is missing

## Secret handling

- non-secret settings belong in `config.yaml`
- secrets belong in `.env` or exported environment variables
- if a credential is missing, add it to `.env` rather than `config.yaml`

## Dashboard

Start the dashboard with:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```

If using Docker Compose, verify:

```bash
docker compose config
docker compose ps
docker compose logs --tail 100
```

ODM stages require Docker to be running. In the Compose flow, `/var/run/docker.sock` must be mounted into the application container.

## Enrichment services

- Verify Weather, Irrigation, and PDM base URLs in `config.yaml`.
- Put service credentials and tokens in `.env`.
- Use `python run.py --skip-weather`, `--skip-report`, or the dashboard step toggles to isolate setup issues.
