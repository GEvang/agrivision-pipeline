# Configuration

`config.yaml` remains the active runtime config.

Additional variants under `config/` are templates for different operating profiles:

- `config.example.yaml` — baseline example values
- `config.dev.yaml` — local development profile
- `config.edge.yaml` — edge/offline-friendly profile

## Precedence

1. Explicit environment variables
2. `config.yaml`
3. Template defaults used when copying from `config/`

Secrets such as Weather and Irrigation credentials should live in `.env` or exported environment variables rather than being committed into YAML.
