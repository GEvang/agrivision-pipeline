#!/usr/bin/env python3
"""
agrivision.pipeline.stages.odm

Run OpenDroneMap (ODM) via Docker to generate orthophotos from drone
images.

This module now supports TWO datasets:

  - RGB   : visual orthophoto (for reports, context)
  - MAPIR : multispectral orthophoto (for real NDVI)

Current pipeline:
-----------------
- The main controller still calls run_odm(), which internally runs
  run_odm_rgb() only. MAPIR ODM support is implemented here but not yet
  wired into the main pipeline (that will come in a later step).

Image selection logic:
----------------------
For each dataset (RGB or MAPIR), ODM selects its input images as:

  1. If images_resized/<dataset>/ has images:
         -> use that

  2. Else if images_full/<dataset>/ has images:
         -> use that

  3. Else:
         -> fail with a clear error.

Selected images are copied into an ODM project directory:

    data/odm_project_rgb/project/images
    data/odm_project_mapir/project/images

ODM is then executed in Docker with:

    -v data/odm_project_xxx:/datasets
    --project-path /datasets
    project_name

"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from agrivision.config.settings import get_project_root, load_config

# We use the same project name ("project") inside each odm_project_* root
PROJECT_NAME = "project"

VALID_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _require_docker_cli() -> None:
    if shutil.which("docker") is not None:
        return
    raise RuntimeError(
        "Docker CLI is required for ODM but was not found in PATH. "
        "Install Docker on the host for local runs, or mount /var/run/docker.sock "
        "and include the docker CLI in the AgriVision app container for container runs."
    )


def _host_project_root() -> Path | None:
    host_root = os.getenv("HOST_PROJECT_ROOT", "").strip()
    if not host_root:
        return None
    return Path(host_root).expanduser().resolve()


def _container_project_root() -> Path | None:
    container_root = os.getenv("APP_CONTAINER_PROJECT_ROOT", "").strip()
    if not container_root:
        return None
    return Path(container_root).resolve()


def _app_container_name() -> str | None:
    return (
        os.getenv("AGRIVISION_APP_CONTAINER_NAME", "").strip()
        or os.getenv("HOSTNAME", "").strip()
        or None
    )


def _resolve_odm_bind_source(project_root: Path) -> Path:
    host_root = _host_project_root()
    container_root = _container_project_root()
    resolved_project_root = project_root.resolve()

    if host_root and container_root:
        try:
            relative = resolved_project_root.relative_to(container_root)
        except ValueError:
            pass
        else:
            return (host_root / relative).resolve()

    return resolved_project_root


def _docker_run_prefix() -> list[str]:
    _require_docker_cli()
    return ["docker", "run", "--rm"]


def _docker_user_args() -> list[str]:
    if not hasattr(os, "getuid") or not hasattr(os, "getgid"):
        return []
    return ["-u", f"{os.getuid()}:{os.getgid()}"]


def _odm_container_name(label: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-")
    return f"agrivision-odm-{normalized or 'run'}"


def _odm_dataset_mount_args(project_root: Path) -> tuple[list[str], str]:
    container_root = _container_project_root()
    app_container = _app_container_name()
    if container_root and app_container:
        try:
            project_root.resolve().relative_to(container_root)
        except ValueError:
            pass
        else:
            return ["--volumes-from", app_container], str(project_root)

    bind_source = _resolve_odm_bind_source(project_root)
    return ["-v", f"{bind_source}:/datasets"], "/datasets"


def _get_odm_settings() -> dict[str, object]:
    """Resolve ODM config and path settings at runtime."""
    config = load_config()
    project_root = get_project_root()
    paths = config["paths"]
    orthophoto = config["orthophoto"]

    return {
        "project_root": project_root,
        "images_full_rgb": project_root / paths["images_full"],
        "images_resized_rgb": project_root / paths["images_resized"],
        "odm_project_root_rgb": project_root / paths["odm_project_root_rgb"],
        "images_full_mapir": project_root / paths["images_full_mapir"],
        "images_resized_mapir": project_root / paths["images_resized_mapir"],
        "odm_project_root_mapir": project_root / paths["odm_project_root_mapir"],
        "odm_docker_image": orthophoto["odm_docker_image"],
        "ortho_resolution_cm": orthophoto["orthophoto_resolution_cm"],
    }


def _folder_has_images(folder: Path) -> bool:
    """Return True if folder contains at least one valid image file."""
    if not folder.exists():
        return False

    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in VALID_EXTS:
            return True
    return False


def _choose_input_folder(label: str, full_dir: Path, resized_dir: Path) -> Path:
    """
    Decide which folder to use for a dataset (RGB or MAPIR):

        1) resized_dir (if it has images)
        2) full_dir    (fallback)

    Raises RuntimeError if neither has images.
    """
    resized_has = _folder_has_images(resized_dir)
    full_has = _folder_has_images(full_dir)

    if resized_has:
        print(f"[ODM-{label}] Using resized images: {resized_dir}")
        return resized_dir

    if full_has:
        print(
            f"[ODM-{label}] No resized images detected. "
            f"Falling back to full-resolution images:\n"
            f"            {full_dir}"
        )
        return full_dir

    raise RuntimeError(
        f"\n[ERROR] ODM-{label} cannot run because no images were found in either:\n"
        f"  - {resized_dir}\n"
        f"  - {full_dir}\n\n"
        "Make sure you have placed images in at least one of these folders,\n"
        "or run the resize step with --run-resize.\n"
    )


def _prepare_odm_project(src_images_dir: Path, project_root: Path, label: str) -> Path:
    """
    Create a clean ODM project folder for the given dataset (RGB or MAPIR)
    and copy images from src_images_dir into:

        <project_root>/project/images

    Returns the path to the project directory.
    """
    project_dir = project_root / PROJECT_NAME
    images_dir = project_dir / "images"

    if project_dir.exists():
        print(f"[ODM-{label}] Removing existing ODM project directory: {project_dir}")
        shutil.rmtree(project_dir)

    images_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0
    for src in sorted(src_images_dir.iterdir()):
        if not src.is_file():
            continue
        if src.suffix.lower() not in VALID_EXTS:
            continue

        dst = images_dir / src.name
        shutil.copy2(src, dst)
        print(f"[ODM-{label}] COPY {src} -> {dst}")
        image_count += 1

    if image_count == 0:
        raise RuntimeError(
            f"[ODM-{label}] No images found in chosen source folder: {src_images_dir}"
        )

    print(f"[ODM-{label}] Copied {image_count} images into ODM project at {project_dir}.")
    return project_dir


def _run_odm_docker(
    project_root: Path, label: str, odm_docker_image: str, ortho_resolution_cm: int
) -> None:
    """
    Execute the ODM Docker container for the project located under project_root.
    """
    mount_args, project_path = _odm_dataset_mount_args(project_root)

    cmd = [
        *_docker_run_prefix(),
        *_docker_user_args(),
        "--name",
        _odm_container_name(label),
        *mount_args,
        odm_docker_image,
        "--project-path",
        project_path,
        PROJECT_NAME,
        "--orthophoto-resolution",
        str(ortho_resolution_cm),
        "--skip-3dmodel",
        "--skip-report",
    ]

    print(f"\n[ODM-{label}] Executing ODM command:")
    print(" ", " ".join(cmd), "\n")

    result = subprocess.run(cmd, cwd=project_root.parent, stdout=sys.stdout, stderr=sys.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"ODM-{label} failed with exit code {result.returncode}. "
            f"Docker mount args were {' '.join(mount_args)}."
        )

    print(f"[ODM-{label}] ODM processing finished.")
    print(
        f"[ODM-{label}] Orthophoto should be here:\n"
        f"  {project_root}/project/odm_orthophoto/odm_orthophoto.tif"
    )


# ---------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------
def run_odm_rgb() -> None:
    """
    Run ODM for the RGB dataset.

    Uses:
      - images_resized/rgb  (preferred, if not empty)
      - images_full/rgb     (fallback)

    Writes project into:
      - data/odm_project_rgb/project
    """
    print("\n[ODM-RGB] Starting ODM photogrammetry for RGB dataset...")
    settings = _get_odm_settings()

    images_full_rgb = settings["images_full_rgb"]
    images_resized_rgb = settings["images_resized_rgb"]
    odm_project_root_rgb = settings["odm_project_root_rgb"]
    odm_docker_image = settings["odm_docker_image"]
    ortho_resolution_cm = settings["ortho_resolution_cm"]

    input_folder = _choose_input_folder(
        label="RGB",
        full_dir=images_full_rgb,
        resized_dir=images_resized_rgb,
    )

    _prepare_odm_project(
        src_images_dir=input_folder,
        project_root=odm_project_root_rgb,
        label="RGB",
    )

    _run_odm_docker(
        project_root=odm_project_root_rgb,
        label="RGB",
        odm_docker_image=odm_docker_image,
        ortho_resolution_cm=ortho_resolution_cm,
    )


def run_odm_mapir() -> None:
    """
    Run ODM for the MAPIR dataset.

    Uses:
      - images_resized/mapir  (preferred, if not empty)
      - images_full/mapir     (fallback)

    Writes project into:
      - data/odm_project_mapir/project

    NOTE:
      This function is implemented and ready to use, but the main
      pipeline controller does not call it yet. In upcoming steps,
      we will wire this into the pipeline so that MAPIR orthophotos
      are produced alongside RGB orthophotos.
    """
    print("\n[ODM-MAPIR] Starting ODM photogrammetry for MAPIR dataset...")
    settings = _get_odm_settings()

    images_full_mapir = settings["images_full_mapir"]
    images_resized_mapir = settings["images_resized_mapir"]
    odm_project_root_mapir = settings["odm_project_root_mapir"]
    odm_docker_image = settings["odm_docker_image"]
    ortho_resolution_cm = settings["ortho_resolution_cm"]

    input_folder = _choose_input_folder(
        label="MAPIR",
        full_dir=images_full_mapir,
        resized_dir=images_resized_mapir,
    )

    _prepare_odm_project(
        src_images_dir=input_folder,
        project_root=odm_project_root_mapir,
        label="MAPIR",
    )

    _run_odm_docker(
        project_root=odm_project_root_mapir,
        label="MAPIR",
        odm_docker_image=odm_docker_image,
        ortho_resolution_cm=ortho_resolution_cm,
    )


def run_odm() -> None:
    """
    Backwards-compatible entrypoint used by the controller.

    For now, this simply runs ODM for the RGB dataset only.
    MAPIR ODM support is available via run_odm_mapir(), which
    will be wired into the main pipeline in a later step.
    """
    run_odm_rgb()


if __name__ == "__main__":
    run_odm()
