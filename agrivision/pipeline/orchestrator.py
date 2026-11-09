"""Run the AgriVision pipeline stages in order for one workspace.

Each stage is a small function that reads and updates a shared
:class:`PipelineRun`. Integration stages (weather, irrigation, pest & disease,
disease risk) degrade instead of failing the run; orthophoto and vegetation
index problems stop it.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from agrivision.config.settings import parse_bool
from agrivision.integrations.common.geometry import openagri_point_wkt
from agrivision.pipeline.io.geolocation import resolve_orthophoto_location
from agrivision.pipeline.io.paths import resolve_pipeline_paths
from agrivision.pipeline.stages.disease_risk import run_disease_risk
from agrivision.pipeline.stages.grid import run_grid_report
from agrivision.pipeline.stages.irrigation_enrichment import run_irrigation_enrichment
from agrivision.pipeline.stages.odm import run_odm_mapir, run_odm_rgb, run_odm_thermal
from agrivision.pipeline.stages.pdm_enrichment import run_pdm_enrichment
from agrivision.pipeline.stages.pixel_alignment import run_pixel_alignment_fallback
from agrivision.pipeline.stages.report import run_report
from agrivision.pipeline.stages.vegetation_index import run_vegetation_index
from agrivision.pipeline.stages.weather_enrichment import run_weather_enrichment
from agrivision.pipeline.state import folder_has_images

ProgressCallback = Callable[[str, str, str], None]


class _CurrentStdoutHandler(logging.StreamHandler):
    """Write to whatever ``sys.stdout`` is at emit time.

    Dashboard runs route each pipeline thread's stdout to its own run log, so
    resolving the stream per record keeps log lines in the right file; the CLI
    simply gets the console.
    """

    @property  # type: ignore[override]
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, value) -> None:
        pass


logger = logging.getLogger(__name__)
if not any(isinstance(handler, _CurrentStdoutHandler) for handler in logger.handlers):
    _handler = _CurrentStdoutHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@dataclass(frozen=True)
class _Camera:
    key: str
    label: str
    images_key: str
    ortho_key: str


_CAMERAS = (
    _Camera("rgb", "RGB", "images_full_rgb", "ortho_rgb"),
    _Camera("mapir", "MAPIR", "images_full_mapir", "ortho_mapir"),
    _Camera("thermal", "Thermal", "images_full_thermal", "ortho_thermal"),
)


def _odm_runner(camera: _Camera) -> Callable[..., None]:
    # Looked up at call time so tests can monkeypatch the module attributes.
    return {"rgb": run_odm_rgb, "mapir": run_odm_mapir, "thermal": run_odm_thermal}[camera.key]


@dataclass
class PipelineRun:
    """Settings and intermediate results shared by the stages of one run."""

    paths: dict[str, Any]
    config: dict[str, Any]
    skip: dict[str, bool]
    orthophoto_resolution_cm: int | None
    pdm_crop: str
    pdm_model_key: str
    flight_date: date | None
    run_id: str | None
    workspace_root: Path | None
    progress_callback: ProgressCallback | None
    pixel_fallback_used: bool = False
    odm_failures: list[str] = field(default_factory=list)
    location_context: dict[str, Any] | None = None
    weather_summary: dict[str, Any] = field(default_factory=dict)
    irrigation_summary: dict[str, Any] = field(default_factory=dict)
    pdm_summary: dict[str, Any] = field(default_factory=dict)
    disease_risk_summary: dict[str, Any] = field(default_factory=dict)

    def progress(self, stage_key: str, message: str, state: str = "running") -> None:
        if self.progress_callback:
            self.progress_callback(stage_key, message, state)

    def path(self, key: str) -> Path | None:
        value = self.paths.get(key)
        return value if isinstance(value, Path) else None

    def has_images(self, camera: _Camera) -> bool:
        folder = self.path(camera.images_key)
        return folder is not None and folder_has_images(folder)

    def has_demo_inputs(self) -> bool:
        return any(self.has_images(camera) for camera in _CAMERAS)

    def has_analysis_orthophoto(self) -> bool:
        """RGB or MAPIR orthophoto present; thermal alone cannot feed the index."""
        return any(path is not None and path.exists() for path in (self.path("ortho_rgb"), self.path("ortho_mapir")))

    @property
    def location_name(self) -> str:
        return str(
            (self.location_context or {}).get("label")
            or self.config.get("location", {}).get("name", "Unknown location")
        )

    @property
    def parcel_wkt(self) -> str | None:
        if not self.location_context:
            return None
        return openagri_point_wkt(self.location_context["latitude"], self.location_context["longitude"])


def _run_pixel_fallback(run: PipelineRun, reason: str) -> None:
    if run.pixel_fallback_used:
        return
    if not run.has_demo_inputs():
        raise RuntimeError(reason)
    run.progress("run_odm_rgb", "Falling back to pixel-space demo alignment")
    logger.info("\n[Demo Alignment] %s", reason)
    run_pixel_alignment_fallback(workspace_root=run.workspace_root, config=run.config)
    run.pixel_fallback_used = True
    for camera in _CAMERAS:
        run.progress(f"run_odm_{camera.key}", f"{camera.label} fallback analysis image ready", "completed")


def _orthophoto_stage(run: PipelineRun) -> None:
    logger.info("Step 1/5: ODM will use full-resolution images.")
    if run.skip["odm"]:
        logger.info("\nStep 2/5: Skipping ODM (--skip-odm).")

    for camera in _CAMERAS:
        tag = f"[ODM-{camera.label.upper()}]"
        orthophoto = run.path(camera.ortho_key)
        if run.skip["odm"] or run.skip[f"odm_{camera.key}"]:
            logger.info("\n%s Skipping %s ODM (skip flag active).", tag, camera.label)
            if orthophoto is not None and orthophoto.exists():
                logger.info("%s Reusing existing %s orthophoto: %s", tag, camera.label, orthophoto)
            continue
        if run.pixel_fallback_used:
            logger.info("\n%s Demo fallback already created the %s analysis image.", tag, camera.label)
            continue
        if not run.has_images(camera):
            logger.info("\n%s No %s images found. Skipping %s ODM.", tag, camera.label, camera.label)
            run.progress(f"run_odm_{camera.key}", f"No {camera.label} images found", "completed")
            continue

        run.progress(f"run_odm_{camera.key}", f"Running ODM for {camera.label} images")
        logger.info("\n%s Running %s ODM...", tag, camera.label)
        try:
            _odm_runner(camera)(
                ortho_resolution_cm=run.orthophoto_resolution_cm,
                workspace_root=run.workspace_root,
                config=run.config,
                run_id=run.run_id,
            )
            run.progress(f"run_odm_{camera.key}", f"{camera.label} orthophoto complete", "completed")
        except Exception as exc:
            message = f"{camera.label} ODM failed ({exc}); using pixel-space demo fallback instead."
            run.odm_failures.append(message)
            _run_pixel_fallback(run, message)

    if not run.has_analysis_orthophoto() and run.has_demo_inputs():
        _run_pixel_fallback(run, "No orthophoto outputs were generated; using pixel-space demo fallback.")
    elif run.odm_failures and not run.pixel_fallback_used:
        raise RuntimeError(run.odm_failures[0])


def _location_stage(run: PipelineRun) -> None:
    orthophotos = [path for path in (run.path(c.ortho_key) for c in _CAMERAS) if path is not None]
    run.location_context = resolve_orthophoto_location(
        orthophotos,
        reverse_geocode=parse_bool(run.config.get("location", {}).get("reverse_geocode"), True),
    )
    if run.location_context:
        logger.info(
            "[AgriVision] Run location resolved from orthophoto: %s (%.5f, %.5f)",
            run.location_context["label"],
            run.location_context["latitude"],
            run.location_context["longitude"],
        )
    else:
        logger.info("[AgriVision] No georeferenced orthophoto found; using configured location fallback.")


def _vegetation_index_stage(run: PipelineRun) -> None:
    vegetation_index_tif = run.paths["vegetation_index_output"] / "vegetation_index.tif"
    if run.skip["vegetation_index"]:
        logger.info("\nStep 3/5: Skipping Vegetation Index (--skip-vegetation-index).")
        if not run.skip["grid"] and not vegetation_index_tif.exists():
            raise RuntimeError(
                f"\n[ERROR] Vegetation Index skipped but Vegetation Index output missing:\n  {vegetation_index_tif}\n"
            )
        return
    run.progress("compute_vegetation_index", "Computing Vegetation Index")
    logger.info("\nStep 3/5: Computing Vegetation Index...")
    if not run.has_analysis_orthophoto():
        raise RuntimeError("\n[ERROR] No orthophoto available for Vegetation Index.\n")
    run_vegetation_index(workspace_root=run.workspace_root, config=run.config)
    run.progress("compute_vegetation_index", "Vegetation Index complete", "completed")


def _grid_stage(run: PipelineRun) -> None:
    if run.skip["grid"]:
        logger.info("\nStep 4/5: Skipping Vegetation Index grid (--skip-grid).")
        return
    run.progress("generate_grid", "Generating Vegetation Index grid")
    logger.info("\nStep 4/5: Generating Vegetation Index grid...")
    run_grid_report(workspace_root=run.workspace_root, config=run.config)
    run.progress("generate_grid", "Vegetation Index grid complete", "completed")


def _first_note(summary: dict[str, Any]) -> str:
    notes = summary.get("notes") or [""]
    return str(summary.get("error_message") or notes[0])


def _weather_stage(run: PipelineRun) -> None:
    if run.skip["weather"]:
        logger.info("\n[AgriVision] Skipping Weather integration (--skip-weather).")
        run.weather_summary = {"enabled": False, "notes": ["Skipped by configuration."]}
        return
    run.progress("fetch_weather", "Fetching weather data")
    logger.info("\n[AgriVision] Running Weather integration ...")
    run.weather_summary = run_weather_enrichment(
        run.paths["output_root"],
        run.location_name,
        location=run.location_context,
        flight_date=run.flight_date,
    )
    if run.weather_summary.get("enabled"):
        logger.info("[AgriVision] Weather integration completed")
    else:
        logger.info("[AgriVision] Weather integration failed (continuing pipeline).")
        logger.info("[AgriVision] Reason: %s", _first_note(run.weather_summary))
    run.progress("fetch_weather", "Weather enrichment complete", "completed")


def _irrigation_stage(run: PipelineRun) -> None:
    if run.skip["irrigation"]:
        logger.info("\n[AgriVision] Skipping Irrigation integration (--skip-irrigation).")
        run.irrigation_summary = {"enabled": False, "notes": ["Skipped by configuration."]}
        return
    run.progress("irrigation_enrichment", "Running irrigation enrichment")
    logger.info("\n[AgriVision] Running Irrigation integration (config-driven ETo) ...")
    run.irrigation_summary = run_irrigation_enrichment(
        run.config.get("irrigation", {}).get("base_url", ""),
        output_dir=run.paths["output_root"] / "irrigation",
    )
    if run.irrigation_summary.get("authenticated") or run.irrigation_summary.get("enabled"):
        logger.info("[AgriVision] Irrigation integration completed")
    else:
        logger.info("[AgriVision] Irrigation integration failed (continuing pipeline).")
        logger.info("[AgriVision] Reason: %s", _first_note(run.irrigation_summary))
    run.progress("irrigation_enrichment", "Irrigation enrichment complete", "completed")


def _pdm_stage(run: PipelineRun) -> None:
    if run.skip["pdm"]:
        logger.info("\n[AgriVision] Skipping PDM integration (--skip-pdm).")
        run.pdm_summary = {"enabled": False, "status": "disabled", "notes": ["Skipped by configuration."]}
        return
    run.progress("pdm_enrichment", "Running pest & disease enrichment")
    logger.info("\n[AgriVision] Running Pest & Disease integration ...")
    pdm_cfg = run.config.get("pdm", {}) if isinstance(run.config.get("pdm"), dict) else {}
    parcel_wkt = run.parcel_wkt
    run.pdm_summary = run_pdm_enrichment(
        base_url=pdm_cfg.get("base_url", ""),
        weather_summary=run.weather_summary,
        enabled=True,
        crop=run.pdm_crop,
        model_key=run.pdm_model_key,
        artifact_dir=run.paths["output_root"] / "pdm",
        parcel_wkt=parcel_wkt,
        parcel_source="orthophoto centroid" if parcel_wkt else "irrigation.default_parcel_wkt",
        location=run.location_context,
    )
    if run.pdm_summary.get("status") == "success":
        logger.info("[AgriVision] Pest & Disease integration completed")
    else:
        logger.info("[AgriVision] Pest & Disease integration failed or degraded (continuing pipeline).")
        logger.info("[AgriVision] Reason: %s", _first_note(run.pdm_summary))
    run.progress("pdm_enrichment", "Pest & disease enrichment complete", "completed")


def _disease_risk_stage(run: PipelineRun) -> None:
    run.disease_risk_summary = {"enabled": False, "notes": ["Disease risk scoring skipped."]}
    if run.skip["grid"]:
        return
    run.progress("disease_risk", "Scoring disease risk layers")
    try:
        run.disease_risk_summary = run_disease_risk(
            crop=run.pdm_crop,
            weather_summary=run.weather_summary,
            irrigation_summary=run.irrigation_summary,
            pdm_summary=run.pdm_summary,
            workspace_root=run.workspace_root,
            config=run.config,
            flight_date=run.flight_date,
        )
    except Exception as exc:
        run.disease_risk_summary = {
            "enabled": False,
            "status": "failed",
            "error_message": str(exc),
            "notes": ["Disease risk scoring failed; report will use the standard grid overlay."],
        }
        logger.info("[AgriVision] Disease risk scoring failed (continuing pipeline): %s", exc)
    run.progress("disease_risk", "Disease risk scoring complete", "completed")


def _report_stage(run: PipelineRun) -> None:
    if run.skip["report"]:
        logger.info("\nStep 5/5: Skipping report generation (--skip-report).")
        return
    run.progress("generate_report", "Generating report")
    logger.info("\nStep 5/5: Creating report...")
    run_report(
        irrigation_summary=run.irrigation_summary,
        weather_summary=run.weather_summary,
        pdm_summary=run.pdm_summary,
        workspace_root=run.workspace_root,
        config=run.config,
        disease_risk_summary=run.disease_risk_summary,
    )
    run.progress("generate_report", "Report generated", "completed")


_STAGES = (
    _orthophoto_stage,
    _location_stage,
    _vegetation_index_stage,
    _grid_stage,
    _weather_stage,
    _irrigation_stage,
    _pdm_stage,
    _disease_risk_stage,
    _report_stage,
)


def run_full_pipeline(
    skip_odm: bool = False,
    skip_odm_rgb: bool = False,
    skip_odm_mapir: bool = False,
    skip_odm_thermal: bool = False,
    skip_vegetation_index: bool = False,
    skip_grid: bool = False,
    skip_weather: bool = False,
    skip_irrigation: bool = False,
    skip_pdm: bool = False,
    skip_report: bool = False,
    orthophoto_resolution_cm: int | None = None,
    pdm_crop: str | None = None,
    pdm_model_key: str | None = None,
    flight_date: date | None = None,
    progress_callback: ProgressCallback | None = None,
    run_id: str | None = None,
    workspace_root: Path | None = None,
    config: dict | None = None,
) -> None:
    skip = {
        "odm": skip_odm,
        "odm_rgb": skip_odm_rgb,
        "odm_mapir": skip_odm_mapir,
        "odm_thermal": skip_odm_thermal,
        "vegetation_index": skip_vegetation_index,
        "grid": skip_grid,
        "weather": skip_weather,
        "irrigation": skip_irrigation,
        "pdm": skip_pdm,
        "report": skip_report,
    }
    logger.info("\n================== AgriVision Pipeline Start ==================\n")
    logger.info("Configuration:")
    for name, value in skip.items():
        logger.info("  skip_%-18s= %s", name, value)
    logger.info("")

    paths = resolve_pipeline_paths(workspace_root=workspace_root, config=config)
    resolved_config = paths["config"]
    pdm_cfg = resolved_config.get("pdm", {}) if isinstance(resolved_config.get("pdm"), dict) else {}
    run = PipelineRun(
        paths=paths,
        config=resolved_config,
        skip=skip,
        orthophoto_resolution_cm=orthophoto_resolution_cm,
        pdm_crop=pdm_crop or pdm_cfg.get("default_crop") or "grapevine",
        pdm_model_key=pdm_model_key or pdm_cfg.get("default_model_key") or "grapevine_powdery_mildew_risk_v1",
        flight_date=flight_date,
        run_id=run_id,
        workspace_root=workspace_root,
        progress_callback=progress_callback,
    )
    for stage in _STAGES:
        stage(run)
    logger.info("\n================== Pipeline Complete ==================\n")
