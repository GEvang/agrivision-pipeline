# Configuration

Preferred rule:

- non-secret settings in `config.yaml`
- secrets in `.env` or environment variables only

Backward compatibility remains for older YAML-based secret values, but operator-facing workflows should migrate them into `.env`.
