# Troubleshooting

## Installation issues

- make sure Docker or Docker Desktop is installed
- make sure Docker is running
- rerun `docker compose up --build -d`
- if needed, use the OS launcher from the repository root

## Secret handling

- non-secret dashboard settings are stored in `runtime/settings.json`
- advanced configuration can still use `config.yaml`
- secrets belong in `.env` or exported environment variables
- missing secrets do not block dashboard startup unless you enable a service that requires them

## Dashboard

Start the dashboard with:

```bash
docker compose up --build -d
```

Then open `http://127.0.0.1:8008`.
