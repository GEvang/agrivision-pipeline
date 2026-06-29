# Install AgriVision Pipeline

The recommended operator install path is dashboard-first with Docker.

## Windows

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Double-click `Start AgriVision Windows.bat`.
4. Open `http://127.0.0.1:8008`.

## Linux

1. Install Docker.
2. Clone AgriVision.
3. Run:

```bash
chmod +x "Start AgriVision Linux.sh"
./"Start AgriVision Linux.sh"
```

4. Open `http://127.0.0.1:8008`.

## macOS

1. Install Docker Desktop.
2. Clone or download AgriVision.
3. Run once:

```bash
chmod +x "Start AgriVision macOS.command"
```

4. Double-click `Start AgriVision macOS.command`.
5. Open `http://127.0.0.1:8008`.

## Universal command

```bash
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline
docker compose up --build -d
```

## Notes

- `.env` is optional for dashboard startup
- `runtime/settings.json` is created automatically on first launch
- optional OpenAgri services can be configured later from the Settings page
- Python virtualenv setup remains available for development and advanced local runs, but it is not required for dashboard-only use

## Advanced references

- `docs/developer/local-dev.md`
- `docs/developer/config.md`
- `docs/operator/windows-self-hosting.md`
