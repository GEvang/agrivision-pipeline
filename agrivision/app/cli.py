#!/usr/bin/env python3
"""AgriVision Pipeline CLI."""

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
from agrivision.config.settings import get_project_root
from agrivision.runtime import irrigation as irrigation_runtime
from agrivision.runtime import pdm as pdm_runtime
from agrivision.runtime import weather as weather_runtime
from agrivision.services import path_migration, reset_service, service_control


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


def _reset(args: argparse.Namespace) -> None:
    try:
        plan = reset_service.plan_reset(args.reset, service=args.service, remove_images=args.remove_images)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print('\n'.join(plan.describe()))
    if not plan.services and not plan.delete_paths:
        return

    backup_to = args.backup
    deletes_runs = args.reset in {'outputs', 'all'}
    if deletes_runs and backup_to is None and not args.no_backup:
        if args.yes:
            raise SystemExit('Choose --backup PATH or --no-backup when resetting outputs without confirmation.')
        answer = input('Write a backup of runs, saved outputs and uploads first? [Y/n] ').strip().lower()
        if answer in {'', 'y', 'yes'}:
            backup_to = reset_service.default_backup_path(plan.project_root)
    if not args.yes and input('Type RESET to continue: ').strip() != 'RESET':
        print('Reset cancelled; nothing was changed.')
        return
    try:
        for line in reset_service.execute_reset(plan, backup_to=backup_to):
            print(line)
    except reset_service.ResetRefused as exc:
        raise SystemExit(str(exc)) from exc


def _migrate_paths(*, dry_run: bool) -> None:
    root = get_project_root()
    result = path_migration.migrate_recorded_paths(root, dry_run=dry_run)
    verb = 'Would rewrite' if dry_run else 'Rewrote'
    print(f'Scanned {result.files_scanned} JSON files under runtime/, data/ and output/.')
    print(f'{verb} {result.paths_converted} paths in {len(result.files_changed)} files.')
    if result.backup:
        print(f'Originals backed up to {result.backup.relative_to(root)}')
    if result.paths_left:
        print(f'Left {len(result.paths_left)} absolute paths that point outside this project unchanged.')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='AgriVision Pipeline entry point.')
    parser.add_argument('--skip-odm', action='store_true', help='Skip the ODM orthophoto generation step.')
    parser.add_argument(
        '--skip-vegetation-index',
        dest='skip_vegetation_index',
        action='store_true',
        help='Skip Vegetation Index computation and reuse existing Vegetation Index outputs.',
    )
    parser.add_argument('--doctor', action='store_true', help='Print runtime diagnostics and exit.')
    parser.add_argument('--setup-services', action='store_true', help='Prepare sibling OpenAgri services and exit.')
    parser.add_argument('--service-control', action='store_true', help='Run a single companion service management action and exit.')
    parser.add_argument('--service-key', choices=['weather', 'irrigation', 'pdm'], help='Service key for --service-control.')
    parser.add_argument('--service-action', choices=['prepare', 'ensure', 'stop', 'restart'], help='Action for --service-control.')
    parser.add_argument('--cleanup', action='store_true', help='Remove generated outputs and exit.')
    parser.add_argument(
        '--reset',
        choices=reset_service.RESET_LEVELS,
        help='Reset outputs, the OpenAgri services, or everything (asks for confirmation).',
    )
    parser.add_argument('--service', choices=list(reset_service.SERVICE_DIRS), help='With --reset services: reset only this service.')
    parser.add_argument('--backup', type=Path, help='With --reset: zip runs, saved outputs and uploads here first.')
    parser.add_argument('--no-backup', action='store_true', help='With --reset outputs/all: skip the backup.')
    parser.add_argument('--remove-images', action='store_true', help='With --reset services/all: also remove the service Docker images.')
    parser.add_argument('--yes', action='store_true', help='With --reset: do not ask for confirmation.')
    parser.add_argument(
        '--migrate-paths',
        action='store_true',
        help='Rewrite absolute paths in existing run records to project-relative ones (backs up first).',
    )
    parser.add_argument('--dry-run', action='store_true', help='With --migrate-paths: only report what would change.')
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
    if args.service_control:
        if not args.service_key or not args.service_action:
            raise SystemExit('--service-control requires --service-key and --service-action.')
        if args.service_action == 'prepare':
            sync = _prepare_service(args.service_key)
            print(json.dumps({'changed': sync.changed, 'changed_keys': list(sync.changed_keys)}, indent=2))
            return
        if args.service_action == 'ensure':
            service_control.ensure_service(args.service_key, timeout_seconds=120)
            print(json.dumps({'status': 'ok', 'service': args.service_key, 'action': 'ensure'}, indent=2))
            return
        if args.service_action == 'stop':
            service_control.stop_service(args.service_key)
            print(json.dumps({'status': 'ok', 'service': args.service_key, 'action': 'stop'}, indent=2))
            return
        if args.service_action == 'restart':
            service_control.restart_service(args.service_key, timeout_seconds=120)
            print(json.dumps({'status': 'ok', 'service': args.service_key, 'action': 'restart'}, indent=2))
            return
    if args.reset:
        _reset(args)
        return
    if args.migrate_paths:
        _migrate_paths(dry_run=args.dry_run)
        return
    if args.cleanup:
        removed = cleanup_outputs()
        print(json.dumps({'removed': removed}, indent=2))
        return
    if args.serve_dashboard:
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'uvicorn',
                'agrivision.app.api:app',
                '--host',
                args.host,
                '--port',
                str(args.port),
            ],
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        return

    run_full_pipeline(
        skip_odm=args.skip_odm,
        skip_vegetation_index=args.skip_vegetation_index,
        skip_weather=args.skip_weather,
        skip_report=args.skip_report,
    )


def _prepare_service(service_key: str):
    if service_key == 'weather':
        return weather_runtime.prepare_weather_repo_and_env()
    if service_key == 'irrigation':
        return irrigation_runtime.prepare_repo_and_env()
    if service_key == 'pdm':
        return pdm_runtime.prepare_repo_and_env()
    raise ValueError(f'Unknown service key: {service_key}')


if __name__ == '__main__':
    main()
