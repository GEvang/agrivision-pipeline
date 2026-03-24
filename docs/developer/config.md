# Configuration

`config.yaml` remains the active runtime config for non-secret settings.

Additional variants under `config/` are templates for different operating profiles:

- `config.example.yaml` — baseline example values
- `config.dev.yaml` — local development profile
- `config.edge.yaml` — edge/offline-friendly profile

## Precedence

1. Explicit environment variables
2. `.env`
3. `config.yaml`
4. built-in defaults

## Secret handling

Store credentials in `.env` or exported environment variables, not in YAML.

Preferred secret keys:

- `WEATHER_USERNAME`
- `WEATHER_PASSWORD`
- `OPENWEATHER_API_KEY`
- `IRRIGATION_EMAIL`
- `IRRIGATION_PASSWORD`
- `IRRIGATION_TOKEN`

Legacy YAML secret values are still accepted for backward compatibility, but they should be migrated out of `config.yaml`.
