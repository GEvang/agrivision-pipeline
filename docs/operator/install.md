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

The installer expects `python3`. It warns when `gdalinfo` is missing because GDAL is required for raster and orthophoto workflows.

On Windows PowerShell, use the manual setup from the README or run the Docker Compose flow.

## Configuration

- keep non-secret settings in `config.yaml`
- create local secrets with `cp .env.example .env` and then fill the required values
- keep secrets in `.env` or exported environment variables
- never commit real credentials into `config.yaml` or `.env`

## Windows self-hosting

For a Windows workstation that serves the dashboard through Cloudflare Tunnel, follow `docs/operator/windows-self-hosting.md` after the local dashboard runs successfully.
