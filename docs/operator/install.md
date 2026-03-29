# Install AgriVision Pipeline

Use the repository root installer as the canonical operator path.

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
./install_agrivision.sh
source .venv/bin/activate
python run.py --doctor
```

## What the installer does

- creates `.venv`
- installs Python dependencies
- creates the expected data, output, and runtime directories
- creates `.env` from `.env.example` when missing
- standardizes the local virtual environment at `.venv`

## Configuration

- keep non-secret settings in `config.yaml`
- create local secrets with `cp .env.example .env` and then fill the required values
- keep secrets in `.env` or exported environment variables
- never commit real credentials into `config.yaml` or `.env`
