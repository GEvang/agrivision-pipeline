#!/usr/bin/env python3
"""AgriVision ADS CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from agrivision.app.commands.cleanup import cleanup_outputs
from agrivision.app.commands.doctor import doctor
from agrivision.app.commands.run_pipeline import run_full_pipeline
from agrivision.app.commands.setup_services import setup_services


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / '.env'
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='AgriVision ADS pipeline entry point.')
    parser.add_argument('--run-resize', action='store_true', help='Run the image resizing step before ODM.')
    parser.add_argument('--skip-odm', action='store_true', help='Skip the ODM orthophoto generation step.')
    parser.add_argument('--skip-ndvi', action='store_true', help='Skip NDVI computation and reuse existing NDVI outputs.')
    parser.add_argument('--doctor', action='store_true', help='Print runtime diagnostics and exit.')
    parser.add_argument('--setup-services', action='store_true', help='Prepare sibling OpenAgri services and exit.')
    parser.add_argument('--cleanup', action='store_true', help='Remove generated outputs and exit.')
    parser.add_argument('--skip-weather', action='store_true', help='Skip weather enrichment during the run.')
    parser.add_argument('--skip-report', action='store_true', help='Skip report generation during the run.')
    parser.add_argument('--serve-dashboard', action='store_true', help='Start the FastAPI operator dashboard.')
    parser.add_argument('--host', default='127.0.0.1', help='Dashboard bind host.')
    parser.add_argument('--port', type=int, default=8008, help='Dashboard bind port.')
    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def main() -> None:
    load_local_env()
    args = parse_args()

    if args.doctor:
        print(json.dumps(doctor(), indent=2))
        return
    if args.setup_services:
        setup_services()
        print('Services prepared.')
        return
    if args.cleanup:
        removed = cleanup_outputs()
        print(json.dumps({'removed': removed}, indent=2))
        return
    if args.serve_dashboard:
        subprocess.run([sys.executable, '-m', 'uvicorn', 'agrivision.app.api:app', '--host', args.host, '--port', str(args.port)], check=False)
        return

    run_full_pipeline(
        run_resize_step=args.run_resize,
        skip_odm=args.skip_odm,
        skip_ndvi=args.skip_ndvi,
        skip_weather=args.skip_weather,
        skip_report=args.skip_report,
    )


if __name__ == '__main__':
    main()
