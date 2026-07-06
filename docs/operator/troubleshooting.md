# Troubleshooting

## The Dashboard Does Not Open

Check the container first:

```bash
docker compose ps
docker compose logs --tail 100
```

Common causes:

- Docker is not running
- port `8008` is already in use
- the image build failed

## `docker compose up` Fails Immediately

Run:

```bash
docker compose config
docker compose build
```

If that fails, fix the Docker error before looking at application behavior.

## The Dashboard Starts But ODM Work Fails

Check:

- Docker has enough RAM and disk space
- `/var/run/docker.sock` is available to the container
- the host has enough free space for ODM intermediates

Windows operators should review `docs/operator/windows-self-hosting.md` for Docker Desktop resource guidance.

## Weather, Irrigation, or PDM Looks Broken

Expected behavior:

- missing services do not block dashboard startup
- missing credentials do not matter until you enable that integration

Check:

- service base URLs
- credentials in `.env`
- service status on the Settings page
- service docs or health endpoints if the companion service is running

## Settings or Credentials Are Not Persisting

Non-secret settings are stored in `runtime/settings.json`.

Secrets belong in `.env` or exported environment variables, not in `config.yaml`.

If changes disappear:

- confirm `runtime/` is writable
- confirm you are editing the same checkout that Docker is mounting

## A Run Is Stuck Or Fails Midway

Check the run detail page and the run log under:

```text
runtime/runs/<run_id>/run.log
```

Useful artifacts:

- `runtime/runs/<run_id>/status.json`
- `runtime/runs/<run_id>/outputs.json`
- `runtime/runs/<run_id>/previews/`

## Last Resort Diagnostics

```bash
python run.py --doctor
docker compose logs --tail 200
```
