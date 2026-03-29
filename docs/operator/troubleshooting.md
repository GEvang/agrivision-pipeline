# Troubleshooting

## Installation issues

- rerun `./install_agrivision.sh`
- activate `.venv` with `source .venv/bin/activate`
- validate with `python run.py --doctor`

## Secret handling

- non-secret settings belong in `config.yaml`
- secrets belong in `.env` or exported environment variables
- if a credential is missing, add it to `.env` rather than `config.yaml`

## Dashboard

Start the dashboard with:

```bash
python run.py --serve-dashboard --host 127.0.0.1 --port 8008
```
