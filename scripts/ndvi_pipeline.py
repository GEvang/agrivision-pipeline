#!/usr/bin/env python3
"""
ndvi_pipeline.py

High-level controller for the AgriVision pipeline.

Steps:
  1. Resize original images           -> scripts/resize_images.py
  2. Run ODM to generate orthophoto   -> scripts/run_odm.py
  3. Compute NDVI + color PNG         -> scripts/compute_ndvi.py

Default directories (relative to project root):
  data/images_full/
  data/images_resized/
  data/odm_project/
  output/ndvi/

Usage (from project root):

    # Run full pipeline:
    python3 scripts/ndvi_pipeline.py

    # Skip ODM (for example, if you already have an orthophoto):
    python3 scripts/ndvi_pipeline.py --skip-odm

    # Skip resizing and ODM (only recompute NDVI from existing orthophoto):
    python3 scripts/ndvi_pipeline.py --skip-resize --skip-odm

    # Just test wiring without doing any work:
    python3 scripts/ndvi_pipeline.py --skip-resize --skip-odm --skip-ndvi
"""

import argparse
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def run_step(description: str, cmd: list[str], skip: bool = False) -> None:
    """
    Helper to run a subprocess step with logging and optional skipping.
    """
    if skip:
        print(f"[SKIP] {description}")
        return

    print(f"\n[STEP] {description}")
    print("Command:", " ".join(cmd))
    print()

    # Run the command from the project root
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        raise RuntimeError(
            f"Step failed: {description} (exit code {result.returncode})"
        )

    print(f"[OK] {description} completed.")


def main():
    parser = argparse.ArgumentParser(description="AgriVision NDVI pipeline controller.")

    parser.add_argument(
        "--skip-resize",
        action="store_true",
        help="Skip image resizing step.",
    )
    parser.add_argument(
        "--skip-odm",
        action="store_true",
        help="Skip ODM processing step.",
    )
    parser.add_argument(
        "--skip-ndvi",
        action="store_true",
        help="Skip NDVI computation step.",
    )
    parser.add_argument(
        "--camera",
        type=str,
        default="sample_mapir_unknown",
        help="Camera profile to pass to compute_ndvi.py.",
    )

    args = parser.parse_args()

    print(f"Base directory: {BASE_DIR}")

    # 1. Resize images
    run_step(
        "Resizing images (scripts/resize_images.py)",
        ["python3", "scripts/resize_images.py"],
        skip=args.skip_resize,
    )

    # 2. Run ODM
    run_step(
        "Running ODM (scripts/run_odm.py)",
        ["python3", "scripts/run_odm.py"],
        skip=args.skip_odm,
    )

    # 3. Compute NDVI
    run_step(
        "Computing NDVI (scripts/compute_ndvi.py)",
        ["python3", "scripts/compute_ndvi.py", "--camera", args.camera],
        skip=args.skip_ndvi,
    )

    print("\n[PIPELINE] AgriVision NDVI pipeline completed.")


if __name__ == "__main__":
    main()

