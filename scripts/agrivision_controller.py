#!/usr/bin/env python3
"""
agrivision_controller.py

High-level controller for the AgriVision pipeline.

Steps:
  1. Resize original images           -> scripts/resize_images.py
  2. Run ODM to generate orthophoto   -> scripts/run_odm.py
  3. Compute NDVI + color PNG         -> scripts/compute_ndvi.py
  4. Generate NDVI grid + CSVs        -> scripts/ndvi_grid_report.py
  5. Generate static HTML report      -> scripts/generate_report.py
  6. Snapshot outputs into a per-run folder under output/runs/<run_id>/

Usage (from project root):

    # Full pipeline, auto-generated run ID (timestamp)
    python3 scripts/agrivision_controller.py

    # Provide your own run ID (e.g. field name)
    python3 scripts/agrivision_controller.py --run-id vineyard_north

    # Skip heavy steps if needed:
    python3 scripts/agrivision_controller.py --skip-odm --skip-resize
"""

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ORTHO_SRC = BASE_DIR / "data" / "odm_project" / "project" / "odm_orthophoto" / "odm_orthophoto.tif"
NDVI_TIF_SRC = BASE_DIR / "output" / "ndvi" / "ndvi.tif"
NDVI_PNG_SRC = BASE_DIR / "output" / "ndvi" / "ndvi_color.png"
REPORT_SRC = BASE_DIR / "output" / "report_latest.html"

GRID_OVERLAY_SRC = BASE_DIR / "output" / "ndvi" / "ndvi_grid_overlay.png"
GRID_CELLS_SRC = BASE_DIR / "output" / "ndvi" / "ndvi_grid_cells.csv"
GRID_CATEGORIES_SRC = BASE_DIR / "output" / "ndvi" / "ndvi_grid_categories.csv"


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

    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        raise RuntimeError(
            f"Step failed: {description} (exit code {result.returncode})"
        )

    print(f"[OK] {description} completed.")


def snapshot_run_outputs(run_id: str):
    """
    Copy key outputs of the current run into output/runs/<run_id>/

    This is just for archiving / comparing different runs.
    """
    runs_root = BASE_DIR / "output" / "runs"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    def copy_if_exists(src: Path, dst_name: str, label: str):
        if src.exists():
            dst = run_dir / dst_name
            shutil.copy2(src, dst)
            print(f"[OK] Copied {label} -> {dst}")
        else:
            print(f"[WARN] {label} not found at {src}, skipping copy.")

    # (1) Orthophoto
    copy_if_exists(ORTHO_SRC, "odm_orthophoto.tif", "Orthophoto")

    # (2) NDVI GeoTIFF
    copy_if_exists(NDVI_TIF_SRC, "ndvi.tif", "NDVI GeoTIFF")

    # (3) NDVI color PNG
    copy_if_exists(NDVI_PNG_SRC, "ndvi_color.png", "NDVI PNG")

    # (4) NDVI grid overlay
    copy_if_exists(GRID_OVERLAY_SRC, "ndvi_grid_overlay.png", "NDVI grid overlay")

    # (5) NDVI grid cells CSV
    copy_if_exists(GRID_CELLS_SRC, "ndvi_grid_cells.csv", "NDVI grid cells CSV")

    # (6) NDVI grid categories CSV
    copy_if_exists(
        GRID_CATEGORIES_SRC,
        "ndvi_grid_categories.csv",
        "NDVI grid categories CSV",
    )

    # (7) HTML report
    copy_if_exists(REPORT_SRC, "report.html", "HTML report")


def main():
    parser = argparse.ArgumentParser(
        description="AgriVision master controller (per-run snapshots)."
    )

    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run identifier (e.g. 'field1_morning'). "
        "If not provided, a timestamp-based ID will be used.",
    )
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
        "--skip-report",
        action="store_true",
        help="Skip HTML report generation.",
    )
    parser.add_argument(
        "--camera",
        type=str,
        default="sample_mapir_unknown",
        help="Camera profile name passed to compute_ndvi.py.",
    )
    parser.add_argument(
        "--skip-grid",
        action="store_true",
        help="Skip NDVI grid overlay + CSV generation.",
    )

    args = parser.parse_args()

    if args.run_id:
        run_id = args.run_id
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"[AgriVision] Base directory: {BASE_DIR}")
    print(f"[AgriVision] Run ID: {run_id}")

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

    # 3b. Generate NDVI grid overlay + CSVs
    skip_grid = args.skip_grid or args.skip_ndvi
    run_step(
        "Generating NDVI grid report (scripts/ndvi_grid_report.py)",
        ["python3", "scripts/ndvi_grid_report.py"],
        skip=skip_grid,
    )

    # 4. Generate HTML report
    run_step(
        "Generating HTML report (scripts/generate_report.py)",
        ["python3", "scripts/generate_report.py"],
        skip=args.skip_report,
    )

    # 5. Snapshot outputs for this run
    snapshot_run_outputs(run_id)

    print("[PIPELINE] AgriVision controller completed successfully.")


if __name__ == "__main__":
    main()

