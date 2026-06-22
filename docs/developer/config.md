# Configuration

Preferred rule:

- non-secret settings in `config.yaml`
- secrets in `.env` or environment variables only

The loader merges values in this order:

1. defaults from `agrivision/config/settings.py`
2. non-secret values from the active YAML config
3. `.env` or exported environment variables

The default config path is `config.yaml`. Override it with `AGRIVISION_CONFIG_PATH=/path/to/config.yaml`.

Secret-like YAML fields are intentionally cleared during load and must be supplied through `.env` or the process environment. Start from `.env.example` for supported variable names.

When `APP_CONTAINER_PROJECT_ROOT` is set, loopback service URLs for Weather, Irrigation, and PDM are rewritten from `127.0.0.1` or `localhost` to `host.docker.internal`. Set `AGRIVISION_REWRITE_LOOPBACK_URLS=0` to disable that container rewrite.
