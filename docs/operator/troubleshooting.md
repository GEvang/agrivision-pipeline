# Troubleshooting

## Doctor output

Run:

```bash
python run.py --doctor
```

Check that paths, config resolution, and environment variables match the expected runtime.

## Common issues

### Missing outputs

Run `python run.py --cleanup` and repeat the pipeline with the expected stage flags.

### Container path mismatches

Verify `HOST_PROJECT_ROOT` and `APP_CONTAINER_PROJECT_ROOT` in the compose configuration.

### Configuration secrets warning

Move credential values from `config.yaml` into `.env` or exported environment variables.
