# Deployment

The root-level operational assets are the only supported deployment surface:

- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `Start AgriVision Windows.bat`
- `Start AgriVision Linux.sh`
- `Start AgriVision macOS.command`
- `.env.example`

## Root Docker flow

```bash
docker compose up --build -d
```

Then open `http://127.0.0.1:8008`.

Base dashboard startup does not require `.env` and does not require optional OpenAgri services to be installed in advance.

Python virtualenv setup remains available for development and advanced local runs, but it is no longer the primary operator deployment path.
