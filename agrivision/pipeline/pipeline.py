#!/usr/bin/env python3
"""
agrivision.pipeline.pipeline

Main pipeline orchestrator.

Includes Weather integration plus Irrigation integration (self-healing + ETo).
ETo settings (location_id / days_back) are read from config.yaml by the irrigation bootstrapper.
"""

import json
from pathlib import Path
from typing import Any, Dict

from agrivision.config.settings import get_project_root, load_config
from agrivision.pipeline.stages.grid import run_grid_report
from agrivision.pipeline.stages.odm import run_odm_mapir, run_odm_rgb
from agrivision.pipeline.stages.report import run_report
from agrivision.pipeline.stages.resize import run_resize
from agrivision.pipeline.stages.vegetation_index import run_ndvi
from agrivision.services.irrigation.bootstrap import (
    ensure_irrigation_auth_parcel_and_eto,
)
from agrivision.services.weather.client import collect_weather_summary

VALID_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _get_controller_settings() -> dict[str, Path | dict]:
    config = load_config()
    project_root = get_project_root()
    paths = config["paths"]

    ortho_rgb = (
        project_root / paths["odm_project_root_rgb"]
        / "project/odm_orthophoto/odm_orthophoto.tif"
    )
    ortho_mapir = (
        project_root / paths["odm_project_root_mapir"]
        / "project/odm_orthophoto/odm_orthophoto.tif"
    )
    ndvi_tif = project_root / paths["ndvi_output"] / "ndvi.tif"
    images_full_mapir = project_root / paths["images_full_mapir"]
    images_resized_mapir = project_root / paths["images_resized_mapir"]
    output_root = project_root / paths["output_root"]

    return {
        "config": config,
        "project_root": project_root,
        "ortho_rgb": ortho_rgb,
        "ortho_mapir": ortho_mapir,
        "ndvi_tif": ndvi_tif,
        "images_full_mapir": images_full_mapir,
        "images_resized_mapir": images_resized_mapir,
        "output_root": output_root,
    }


def _folder_has_images(folder: Path) -> bool:
    if not folder.exists():
        return False
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in VALID_EXTS:
            return True
    return False


def _mapir_images_available(images_full_mapir: Path, images_resized_mapir: Path) -> bool:
    return _folder_has_images(images_full_mapir) or _folder_has_images(images_resized_mapir)


def _orthophoto_exists_rgb(ortho_rgb: Path) -> bool:
    return ortho_rgb.exists()


def _orthophoto_exists_mapir(ortho_mapir: Path) -> bool:
    return ortho_mapir.exists()


def _ndvi_exists(ndvi_tif: Path) -> bool:
    return ndvi_tif.exists()


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_weather_artifacts(weather_summary: Dict[str, Any], output_root: Path) -> Dict[str, Any]:
    weather_dir = output_root / "weather"
    weather_dir.mkdir(parents=True, exist_ok=True)

    weather_summary["current_weather_artifact"] = _write_json(
        weather_dir / "current_weather.json",
        weather_summary.get("current_weather", {}),
    )
    weather_summary["forecast_json_artifact"] = _write_json(
        weather_dir / "forecast5.json",
        weather_summary.get("forecast5_points", []),
    )
    weather_summary["forecast_jsonld_artifact"] = _write_json(
        weather_dir / "forecast5.jsonld",
        weather_summary.get("forecast5_jsonld", {}),
    )
    weather_summary["thi_artifact"] = _write_json(
        weather_dir / "thi.json",
        weather_summary.get("thi", {}),
    )
    weather_summary["thi_jsonld_artifact"] = _write_json(
        weather_dir / "thi.jsonld",
        weather_summary.get("thi_jsonld", {}),
    )
    weather_summary["uav_artifact"] = _write_json(
        weather_dir / "uav_flight_forecast.json",
        weather_summary.get("uav_flight_forecast", {}),
    )
    weather_summary["spray_artifact"] = _write_json(
        weather_dir / "spray_forecast.json",
        weather_summary.get("spray_forecast", {}),
    )
    weather_summary["spray_jsonld_artifact"] = _write_json(
        weather_dir / "spray_forecast.jsonld",
        weather_summary.get("spray_forecast_jsonld", {}),
    )
    weather_summary["historical_daily_artifact"] = _write_json(
        weather_dir / "historical_daily.json",
        weather_summary.get("historical_daily", {}),
    )
    weather_summary["historical_hourly_artifact"] = _write_json(
        weather_dir / "historical_hourly.json",
        weather_summary.get("historical_hourly", {}),
    )
    return weather_summary


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

    resolved = _get_controller_settings()
    config = resolved["config"]
    ortho_rgb = resolved["ortho_rgb"]
    ortho_mapir = resolved["ortho_mapir"]
    ndvi_tif = resolved["ndvi_tif"]
    images_full_mapir = resolved["images_full_mapir"]
    images_resized_mapir = resolved["images_resized_mapir"]
    output_root = resolved["output_root"]

    if run_resize_step:
        print("Step 1/5: Resizing images...")
        run_resize()
    else:
        print("Step 1/5: Skipping resize (no --run-resize flag).")
        print("          ODM will auto-select full vs resized images.")

    if skip_odm:
        skip_odm_rgb = True
        skip_odm_mapir = True
        print("\nStep 2/5: Skipping ODM (--skip-odm).")

    if skip_odm_rgb:
        print("\n[ODM-RGB] Skipping RGB ODM step.")
        if not _orthophoto_exists_rgb(ortho_rgb):
            raise RuntimeError(
                f"\n[ERROR] RGB ODM skipped but no RGB orthophoto exists:\n  {ortho_rgb}\n"
            )
    else:
        print("\n[ODM-RGB] Running RGB ODM...")
        run_odm_rgb()

    if skip_odm_mapir:
        print("\n[ODM-MAPIR] Skipping MAPIR ODM (skip flag active).")
    else:
        if _mapir_images_available(images_full_mapir, images_resized_mapir):
            print("\n[ODM-MAPIR] MAPIR images detected – running MAPIR ODM...")
            run_odm_mapir()
        else:
            print("\n[ODM-MAPIR] No MAPIR images found. Skipping MAPIR ODM.")

    if skip_ndvi:
        print("\nStep 3/5: Skipping NDVI (--skip-ndvi).")
        if not _ndvi_exists(ndvi_tif):
            raise RuntimeError(
                f"\n[ERROR] NDVI skipped but NDVI output missing:\n  {ndvi_tif}\n"
            )
    else:
        print("\nStep 3/5: Computing NDVI...")
        if not _orthophoto_exists_rgb(ortho_rgb) and not _orthophoto_exists_mapir(ortho_mapir):
            raise RuntimeError("\n[ERROR] No orthophoto available for NDVI.\n")
        run_ndvi()

    print("\nStep 4/5: Generating NDVI grid...")
    run_grid_report()

    weather_summary = {
        "enabled": True,
        "location_name": config.get("location", {}).get("name", "Unknown location"),
        "current_weather": {},
        "forecast5_points": [],
        "forecast5_jsonld": {},
        "thi": {},
        "thi_jsonld": {},
        "uav_flight_forecast": {},
        "spray_forecast": {},
        "spray_forecast_jsonld": {},
        "historical_daily": {},
        "historical_hourly": {},
        "notes": ["Weather integration not executed."],
        "uav_model": "dji_phantom4",
    }

    try:
        print("\n[AgriVision] Running Weather integration ...")
        weather_summary = collect_weather_summary(uav_model="dji_phantom4")
        weather_summary = _write_weather_artifacts(weather_summary, output_root)
        print("[AgriVision] ✅ Weather integration completed")
    except Exception as exc:
        print("[AgriVision] ⚠️ Weather integration failed (continuing pipeline).")
        print(f"[AgriVision] Reason: {exc}")
        weather_summary = {
            "enabled": False,
            "location_name": config.get("location", {}).get("name", "Unknown location"),
            "current_weather": {},
            "forecast5_points": [],
            "forecast5_jsonld": {},
            "thi": {},
            "thi_jsonld": {},
            "uav_flight_forecast": {},
            "spray_forecast": {},
            "spray_forecast_jsonld": {},
            "historical_daily": {},
            "historical_hourly": {},
            "notes": [f"Weather integration failed: {exc}"],
            "uav_model": "dji_phantom4",
        }

    irrigation_summary = {
        "enabled": True,
        "authenticated": False,
        "base_url": config.get("irrigation", {}).get("base_url", ""),
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
    except Exception as exc:
        print("[AgriVision] ⚠️ Irrigation integration failed (continuing pipeline).")
        print(f"[AgriVision] Reason: {exc}")
        irrigation_summary = {
            "enabled": True,
            "authenticated": False,
            "base_url": config.get("irrigation", {}).get("base_url", ""),
            "email": "",
            "parcel_count": 0,
            "created_default_parcel": False,
            "eto": {"ok": False, "http_status": None, "method": "get_calculations"},
            "notes": [f"Irrigation integration failed: {exc}"],
        }

    print("\nStep 5/5: Creating report...")
    run_report(irrigation_summary=irrigation_summary, weather_summary=weather_summary)

    print("\n================== Pipeline Complete ==================\n")


if __name__ == "__main__":
    run_full_pipeline()
