#!/usr/bin/env python3
"""
agrivision.pipeline.odm

Prepare an ODM project using resized images and run OpenDroneMap
in Docker to generate an orthophoto.

"""

import os
import shutil
import subprocess
from pathlib import Path

from agrivision.utils.settings import get_project_root, load_config


CONFIG = load_config()
PROJECT_ROOT = get_project_root()

RESIZED_IMAGES_DIR = PROJECT_ROOT / CONFIG["paths"]["images_resized"]
ODM_PROJECT_ROOT = PROJECT_ROOT / CONFIG["paths"]["odm_project_root"]

PROJECT_NAME = "project"
ODM_DOCKER_IMAGE = CONFIG["orthophoto"]["odm_docker_image"]
ORTHO_RESOLUTION_CM = CONFIG["orthophoto"]["orthophoto_resolution_cm"]


def prepare_odm_project() -> Path:
    """
    Create a clean ODM project folder and copy resized images into it.

    Returns the path to the project directory.
    """
    project_dir = ODM_PROJECT_ROOT / PROJECT_NAME
    images_dir = project_dir / "images"

    if project_dir.exists():
        print(f"[ODM] Removing existing ODM project directory: {project_dir}")
        # Remove entire tree (we assume it is owned by current user after we
        # started running docker with -u UID:GID).
        shutil.rmtree(project_dir)

    images_dir.mkdir(parents=True, exist_ok=True)

    if not RESIZED_IMAGES_DIR.exists():
        raise FileNotFoundError(
            f"Resized images folder does not exist: {RESIZED_IMAGES_DIR}"
        )

    image_count = 0
    for src in sorted(RESIZED_IMAGES_DIR.iterdir()):
        if not src.is_file():
            continue
        if src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            continue

        dst = images_dir / src.name
        shutil.copy2(src, dst)
        print(f"[ODM] COPY {src} -> {dst}")
        image_count += 1

    if image_count == 0:
        raise RuntimeError(f"No images found in {RESIZED_IMAGES_DIR}")

    print(f"[ODM] Copied {image_count} images into ODM project.")
    return project_dir


def run_odm() -> None:
    """
    Run ODM in Docker to create an orthophoto.
    """
    odm_project_root = ODM_PROJECT_ROOT
    print(f"[ODM] ODM project root (host): {odm_project_root}")

    uid = os.getuid()
    gid = os.getgid()

    cmd = [
        "docker",
        "run",
        "-ti",
        "--rm",
        "-u",
        f"{uid}:{gid}",          # run container as current user
        "-v",
        f"{odm_project_root}:/datasets",
        ODM_DOCKER_IMAGE,
        "--project-path",
        "/datasets",
        PROJECT_NAME,
        "--orthophoto-resolution",
        str(ORTHO_RESOLUTION_CM),
        "--skip-3dmodel",
        "--skip-report",
    ]

    print("\n[ODM] Executing ODM command:")
    print(" ", " ".join(cmd), "\n")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        raise RuntimeError(f"ODM failed with exit code {result.returncode}")

    print("[ODM] ODM processing finished.")
    print(
        "Orthophoto should be here:\n"
        "  data/odm_project/project/odm_orthophoto/odm_orthophoto.tif"
    )


if __name__ == "__main__":
    run_odm()

