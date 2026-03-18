#!/usr/bin/env python3
"""
agrivision.pipeline.controller

Main pipeline orchestrator.

Includes Irrigation integration (self-healing + ETo).
ETo settings (location_id / days_back) are read from config.yaml by the irrigation bootstrapper.
"""

from pathlib import Path

from agrivision.irrigation.bootstrap import ensure_irrigation_auth_parcel_and_eto
from agrivision.pipeline.grid import run_grid_report
from agrivision.pipeline.ndvi import run_ndvi
from agrivision.pipeline.odm import run_odm_mapir, run_odm_rgb
from agrivision.pipeline.report import run_report
from agrivision.pipeline.resize import run_resize
from agrivision.utils.settings import get_project_root, load_config

CONFIG = load_config()
PROJECT_ROOT = get_project_root()

ORTHO_RGB = (
    PROJECT_ROOT / CONFIG["paths"]["odm_project_root_rgb"]
    / "project/odm_orthophoto/odm_orthophoto.tif"
)

ORTHO_MAPIR = (
    PROJECT_ROOT / CONFIG["paths"]["odm_project_root_mapir"]
    / "project/odm_orthophoto/odm_orthophoto.tif"
)

NDVI_TIF = PROJECT_ROOT / CONFIG["paths"]["ndvi_output"] / "ndvi.tif"

IMAGES_FULL_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_full_mapir"]
IMAGES_RESIZED_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_resized_mapir"]

VALID_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _folder_has_images(folder: Path) -> bool:
    if not folder.exists():
        return False
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in VALID_EXTS:
            return True
    return False


def _mapir_images_available() -> bool:
    return _folder_has_images(IMAGES_FULL_MAPIR) or _folder_has_images(IMAGES_RESIZED_MAPIR)


def _orthophoto_exists_rgb() -> bool:
    return ORTHO_RGB.exists()


def _orthophoto_exists_mapir() -> bool:
    return ORTHO_MAPIR.exists()


def _ndvi_exists() -> bool:
    return NDVI_TIF.exists()


def run_full_pipeline(
    run_resize_step: bool = False,
    skip_odm: bool = False,
    skip_odm_rgb: bool = False,
    skip_odm_mapir: bool = False,
    skip_ndvi: bool = False,
) -> None:

    print("\n================== AgriVision Pipeline Start ==================\n")
    print("Configuration:")
    print(f"  run_resize_step = {run_resize_step}")
    print(f"  skip_odm        = {skip_odm}")
    print(f"  skip_odm_rgb    = {skip_odm_rgb}")
    print(f"  skip_odm_mapir  = {skip_odm_mapir}")
    print(f"  skip_ndvi       = {skip_ndvi}")
    print()

    # Step 1 — Resize
    if run_resize_step:
        print("Step 1/5: Resizing images...")
        run_resize()
    else:
        print("Step 1/5: Skipping resize (no --run-resize flag).")
        print("          ODM will auto-select full vs resized images.")

    # Step 2 — ODM
    if skip_odm:
        skip_odm_rgb = True
        skip_odm_mapir = True
        print("\nStep 2/5: Skipping ODM (--skip-odm).")

    if skip_odm_rgb:
        print("\n[ODM-RGB] Skipping RGB ODM step.")
        if not _orthophoto_exists_rgb():
            raise RuntimeError(
                f"\n[ERROR] RGB ODM skipped but no RGB orthophoto exists:\n  {ORTHO_RGB}\n"
            )
    else:
        print("\n[ODM-RGB] Running RGB ODM...")
        run_odm_rgb()

    if skip_odm_mapir:
        print("\n[ODM-MAPIR] Skipping MAPIR ODM (skip flag active).")
    else:
        if _mapir_images_available():
            print("\n[ODM-MAPIR] MAPIR images detected – running MAPIR ODM...")
            run_odm_mapir()
        else:
            print("\n[ODM-MAPIR] No MAPIR images found. Skipping MAPIR ODM.")

    # Step 3 — NDVI
    if skip_ndvi:
        print("\nStep 3/5: Skipping NDVI (--skip-ndvi).")
        if not _ndvi_exists():
            raise RuntimeError(
                f"\n[ERROR] NDVI skipped but NDVI output missing:\n  {NDVI_TIF}\n"
            )
    else:
        print("\nStep 3/5: Computing NDVI...")
        if not _orthophoto_exists_rgb() and not _orthophoto_exists_mapir():
            raise RuntimeError("\n[ERROR] No orthophoto available for NDVI.\n")
        run_ndvi()

    # Step 4 — Grid
    print("\nStep 4/5: Generating NDVI grid...")
    run_grid_report()

    # Irrigation integration (self-healing + config-driven ETo)
    irrigation_summary = {
        "enabled": True,
        "authenticated": False,
        "base_url": CONFIG.get("irrigation", {}).get("base_url", ""),
        "email": "",
        "parcel_count": 0,
        "created_default_parcel": False,
        "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
        "notes": ["Irrigation integration not executed."],
    }

    try:
        print("\n[AgriVision] Running Irrigation integration (config-driven ETo) ...")
        irrigation_summary = ensure_irrigation_auth_parcel_and_eto(
            write_artifacts=True,
            verbose=True,
        )
        print("[AgriVision] ✅ Irrigation integration completed")
    except Exception as e:
        print("[AgriVision] ⚠️ Irrigation integration failed (continuing pipeline).")
        print(f"[AgriVision] Reason: {e}")
        irrigation_summary = {
            "enabled": True,
            "authenticated": False,
            "base_url": CONFIG.get("irrigation", {}).get("base_url", ""),
            "email": "",
            "parcel_count": 0,
            "created_default_parcel": False,
            "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
            "notes": [f"Irrigation integration failed: {e}"],
        }

    # Step 5 — Report
    print("\nStep 5/5: Creating report...")
    run_report(irrigation_summary=irrigation_summary)

    print("\n================== Pipeline Complete ==================\n")


if __name__ == "__main__":
    run_full_pipeline()
