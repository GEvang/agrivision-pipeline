#!/usr/bin/env python3
"""Reset the repository to an install-ready state for debugging."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

RESET_TARGETS = [
    PROJECT_ROOT / "venv",
    PROJECT_ROOT / "build",
    PROJECT_ROOT / "dist",
    PROJECT_ROOT / "agrivision_pipeline.egg-info",
    PROJECT_ROOT / ".pytest_cache",
    PROJECT_ROOT / ".coverage",
    PROJECT_ROOT / ".ruff_cache",
    PROJECT_ROOT / "OpenAgri-WeatherService",
    PROJECT_ROOT / "OpenAgri-IrrigationManagement",
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "data/odm_project_rgb",
    PROJECT_ROOT / "data/odm_project_mapir",
    PROJECT_ROOT / "data/images_resized",
]

REMOVE_GLOBS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
]

RECREATE_DIRS = [
    PROJECT_ROOT / "data/images_full/rgb",
    PROJECT_ROOT / "data/images_full/mapir",
    PROJECT_ROOT / "data/images_resized/rgb",
    PROJECT_ROOT / "data/images_resized/mapir",
    PROJECT_ROOT / "data/odm_project_rgb",
    PROJECT_ROOT / "data/odm_project_mapir",
    PROJECT_ROOT / "output/ndvi",
    PROJECT_ROOT / "output/runs",
    PROJECT_ROOT / "output/irrigation",
    PROJECT_ROOT / "output/weather",
]


def _delete_path(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    print(f"{'DRY-RUN ' if dry_run else ''}DELETE {path}")
    if dry_run:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def reset_install_state(dry_run: bool) -> None:
    for target in RESET_TARGETS:
        _delete_path(target, dry_run)
    for pattern in REMOVE_GLOBS:
        for path in PROJECT_ROOT.glob(pattern):
            _delete_path(path, dry_run)
    if dry_run:
        return
    for path in RECREATE_DIRS:
        path.mkdir(parents=True, exist_ok=True)


def run_installer() -> None:
    subprocess.run(["bash", "install_agrivision.sh"], cwd=str(PROJECT_ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset AgriVision to an install-ready state.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted.")
    parser.add_argument(
        "--reset-install",
        action="store_true",
        help="Delete generated files, cloned service repos, caches, outputs, and local build artifacts.",
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="Run install_agrivision.sh after the reset completes.",
    )
    args = parser.parse_args()

    if not args.reset_install and not args.reinstall:
        parser.error("Use --reset-install, optionally with --reinstall.")

    if args.reset_install:
        reset_install_state(args.dry_run)

    if args.reinstall:
        if args.dry_run:
            print("DRY-RUN would run: bash install_agrivision.sh")
        else:
            run_installer()
            print("[Done] Reinstall finished. Re-activate the virtual environment with: source venv/bin/activate")


if __name__ == "__main__":
    main()
