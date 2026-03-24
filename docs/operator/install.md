# Install AgriVision Pipeline

## Canonical operator install path

From a clean checkout:

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
./install_agrivision.sh
source .venv/bin/activate
python run.py --doctor
```

This is the primary operator installation path.

## Secrets and configuration

- Keep non-secret settings in `config.yaml`.
- Keep secrets in `.env` or exported environment variables.
- Start from `.env.example` when you need Weather or Irrigation credentials.

```bash
cp .env.example .env
```

Examples of secrets managed through `.env`:

- `WEATHER_USERNAME`
- `WEATHER_PASSWORD`
- `OPENWEATHER_API_KEY`
- `IRRIGATION_EMAIL`
- `IRRIGATION_PASSWORD`
- `IRRIGATION_TOKEN`

## Data and output locations

- uploaded datasets: `data/uploads/`
- run state and logs: `runtime/runs/`
- reports and processing outputs: `output/`
