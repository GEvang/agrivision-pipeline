#!/usr/bin/env python3
"""
clean_generated_data.py

Manually clean all *generated* data from the AgriVision pipeline,
while keeping:

  - Original images in data/images_full/
  - All scripts, venv, configs, etc.

It removes:

  - data/images_resized/*
  - data/odm_project/*
  - output/ndvi/*
  - output/orthos/*
  - output/runs/*
  - output/report_latest.html

Usage (from project root):

    python3 scripts/clean_generated_data.py

Optional:

    python3 scripts/clean_generated_data.py --yes     # no confirmation
    python3 scripts/clean_generated_data.py --dry-run # show what would be cleaned
"""

import argparse
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

PATHS_DIRS = [
    BASE_DIR / "data" / "images_resized",
    BASE_DIR / "data" / "odm_project",
    BASE_DIR / "output" / "ndvi",
    BASE_DIR / "output" / "orthos",
    BASE_DIR / "output" / "runs",
]

PATHS_FILES = [
    BASE_DIR / "output" / "report_latest.html",
]


def describe_targets():
    print("[AgriVision] The following directories will be cleaned (contents removed):")
    for d in PATHS_DIRS:
        print(f"  DIR:  {d}")

    print("\n[AgriVision] The following files will be removed if they exist:")
    for f in PATHS_FILES:
        print(f"  FILE: {f}")
    print()


def clean_generated_data(dry_run: bool = False):
    # Directories
    for d in PATHS_DIRS:
        if d.exists():
            if dry_run:
                print(f"[DRY RUN] Would clean directory: {d}")
            else:
                print(f"[CLEAN] Cleaning directory: {d}")
                # Remove contents but keep directory
                for child in d.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
        else:
            print(f"[INFO] Directory does not exist, skipping: {d}")

    # Files
    for f in PATHS_FILES:
        if f.exists():
            if dry_run:
                print(f"[DRY RUN] Would remove file: {f}")
            else:
                print(f"[CLEAN] Removing file: {f}")
                f.unlink()
        else:
            print(f"[INFO] File does not exist, skipping: {f}")


def main():
    parser = argparse.ArgumentParser(description="Clean generated AgriVision data.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask for confirmation, just clean.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed, but do not delete anything.",
    )
    args = parser.parse_args()

    print(f"[AgriVision] Project root: {BASE_DIR}")
    describe_targets()

    if args.dry_run:
        print("[AgriVision] DRY RUN mode: nothing will actually be deleted.\n")
        clean_generated_data(dry_run=True)
        return

    if not args.yes:
        answer = input("Proceed with cleaning? This only removes generated data. [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("[AgriVision] Cleaning aborted by user.")
            return

    clean_generated_data(dry_run=False)
    print("\n[AgriVision] Cleaning completed.")


if __name__ == "__main__":
    main()

