#!/usr/bin/env python3
"""
agrivision.pipeline.odm

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
from pathlib import Path

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

# ---------------------------------------------------------------------
# Paths for RGB dataset
# ---------------------------------------------------------------------
IMAGES_FULL_RGB = PROJECT_ROOT / CONFIG["paths"]["images_full"]
IMAGES_RESIZED_RGB = PROJECT_ROOT / CONFIG["paths"]["images_resized"]
ODM_PROJECT_ROOT_RGB = PROJECT_ROOT / CONFIG["paths"]["odm_project_root_rgb"]

# ---------------------------------------------------------------------
# Paths for MAPIR dataset
# ---------------------------------------------------------------------
IMAGES_FULL_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_full_mapir"]
IMAGES_RESIZED_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_resized_mapir"]
ODM_PROJECT_ROOT_MAPIR = PROJECT_ROOT / CONFIG["paths"]["odm_project_root_mapir"]

# Common ODM settings
ODM_DOCKER_IMAGE = CONFIG["orthophoto"]["odm_docker_image"]
ORTHO_RESOLUTION_CM = CONFIG["orthophoto"]["orthophoto_resolution_cm"]

# We use the same project name ("project") inside each odm_project_* root
PROJECT_NAME = "project"

VALID_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


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


def _run_odm_docker(project_root: Path, label: str) -> None:
    """
    Execute the ODM Docker container for the project located under project_root.
    """
    uid = os.getuid()
    gid = os.getgid()

    cmd = [
        "docker",
        "run",
        "-ti",
        "--rm",
        "-u",
        f"{uid}:{gid}",
        "-v",
        f"{project_root}:/datasets",
        ODM_DOCKER_IMAGE,
        "--project-path",
        "/datasets",
        PROJECT_NAME,
        "--orthophoto-resolution",
        str(ORTHO_RESOLUTION_CM),
        "--skip-3dmodel",
        "--skip-report",
    ]

    print(f"\n[ODM-{label}] Executing ODM command:")
    print(" ", " ".join(cmd), "\n")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        raise RuntimeError(f"ODM-{label} failed with exit code {result.returncode}")

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

    input_folder = _choose_input_folder(
        label="RGB",
        full_dir=IMAGES_FULL_RGB,
        resized_dir=IMAGES_RESIZED_RGB,
    )

    project_dir = _prepare_odm_project(
        src_images_dir=input_folder,
        project_root=ODM_PROJECT_ROOT_RGB,
        label="RGB",
    )

    _run_odm_docker(project_root=ODM_PROJECT_ROOT_RGB, label="RGB")


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

    input_folder = _choose_input_folder(
        label="MAPIR",
        full_dir=IMAGES_FULL_MAPIR,
        resized_dir=IMAGES_RESIZED_MAPIR,
    )

    project_dir = _prepare_odm_project(
        src_images_dir=input_folder,
        project_root=ODM_PROJECT_ROOT_MAPIR,
        label="MAPIR",
    )

    _run_odm_docker(project_root=ODM_PROJECT_ROOT_MAPIR, label="MAPIR")


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
