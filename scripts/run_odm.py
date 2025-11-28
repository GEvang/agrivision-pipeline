#!/usr/bin/env python3
"""
run_odm.py

Run OpenDroneMap (ODM) in Docker on the resized images.

- Input images:  data/images_resized/
- ODM project:   data/odm_project/project/
- Output ortho:  data/odm_project/project/odm_orthophoto/odm_orthophoto.tif

Run from project root:
    python3 scripts/run_odm.py
"""

import os
import shutil
import subprocess
from pathlib import Path

# ----- CONFIGURATION -----

ODM_DOCKER_IMAGE = "opendronemap/odm"

# We'll keep a single ODM project called "project"
PROJECT_NAME = "project"

# Base project directory (folder that contains scripts/, data/, output/, etc.)
BASE_DIR = Path(__file__).resolve().parent.parent

IMAGES_RESIZED_DIR = BASE_DIR / "data" / "images_resized"
ODM_PROJECT_ROOT = BASE_DIR / "data" / "odm_project"
ODM_PROJECT_DIR = ODM_PROJECT_ROOT / PROJECT_NAME
ODM_IMAGES_DIR = ODM_PROJECT_DIR / "images"


def ensure_images_for_odm():
    """
    Prepare the ODM project folder and copy resized images into it.

    Input:  data/images_resized/
    Output: data/odm_project/project/images/
    """

    if not IMAGES_RESIZED_DIR.exists():
        raise FileNotFoundError(
            f"Resized images folder not found: {IMAGES_RESIZED_DIR}\n"
            "Run scripts/resize_images.py first."
        )

    # Clean any previous ODM project to avoid stale/broken files
    if ODM_PROJECT_DIR.exists():
        print(f"Cleaning existing ODM project folder: {ODM_PROJECT_DIR}")
        shutil.rmtree(ODM_PROJECT_DIR)

    # Recreate the images folder
    ODM_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Copying images from {IMAGES_RESIZED_DIR} -> {ODM_IMAGES_DIR}")
    count = 0
    for src in IMAGES_RESIZED_DIR.iterdir():
        if not src.is_file():
            continue
        if src.suffix.lower() not in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
            continue

        dst = ODM_IMAGES_DIR / src.name
        shutil.copy2(src, dst)
        count += 1

    print(f"Image copy complete. {count} files copied.")




def run_odm():
    """
    Run the ODM Docker container.

    We mount:
      - data/odm_project -> /datasets  (ODM's project path)

    ODM will expect images in:
      /datasets/project/images
    which we ensured in ensure_images_for_odm().
    """

    ensure_images_for_odm()

    print(f"Running ODM in Docker using image: {ODM_DOCKER_IMAGE}")
    print(f"ODM project root (host): {ODM_PROJECT_ROOT}")

    cmd = [
        "docker", "run",
        "-ti",
        "--rm",
        "-v", f"{ODM_PROJECT_ROOT}:/datasets",
        ODM_DOCKER_IMAGE,
        "--project-path", "/datasets",
        PROJECT_NAME,
        "--fast-orthophoto",
        "--skip-3dmodel",
        "--skip-report",
    ]



    print("\nExecuting command:")
    print(" ".join(cmd))
    print()

    # Run the process and stream output
    subprocess.run(cmd, check=True)

    ortho_path = ODM_PROJECT_DIR / "odm_orthophoto" / "odm_orthophoto.tif"
    print("\nODM processing finished.")
    print(f"Orthophoto should be here:\n  {ortho_path}")
    if not ortho_path.exists():
        print("[WARNING] Orthophoto not found where expected. Check ODM output folders.")


def main():
    print(f"Base directory: {BASE_DIR}")
    print(f"Resized images: {IMAGES_RESIZED_DIR}")
    print(f"ODM project dir: {ODM_PROJECT_DIR}")

    run_odm()


if __name__ == "__main__":
    main()

