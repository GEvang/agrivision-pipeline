#!/usr/bin/env python3
"""
run_odm.py

Prepare an ODM project using data/images_resized/ and run OpenDroneMap
in Docker to generate a normal (non-fast) orthophoto.

Outputs (inside odm_project):

    data/odm_project/project/odm_orthophoto/odm_orthophoto.tif

Usage (from project root):

    source venv/bin/activate
    python3 scripts/run_odm.py
"""

import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RESIZED_IMAGES_DIR = BASE_DIR / "data" / "images_resized"
ODM_PROJECT_ROOT = BASE_DIR / "data" / "odm_project"
PROJECT_NAME = "project"
ODM_DOCKER_IMAGE = "opendronemap/odm:latest"


def prepare_odm_project():
    """
    Create a clean ODM project folder and copy resized images into it.

    Note: we COPY rather than symlink because Docker only sees the mounted
    /datasets path. Absolute symlinks pointing outside the mount will be broken
    inside the container.
    """
    project_dir = ODM_PROJECT_ROOT / PROJECT_NAME
    images_dir = project_dir / "images"

    if project_dir.exists():
        print(f"[INFO] Removing existing ODM project directory: {project_dir}")
        shutil.rmtree(project_dir)

    images_dir.mkdir(parents=True, exist_ok=True)

    if not RESIZED_IMAGES_DIR.exists():
        raise FileNotFoundError(f"Resized images folder does not exist: {RESIZED_IMAGES_DIR}")

    image_count = 0
    for src in sorted(RESIZED_IMAGES_DIR.iterdir()):
        if not src.is_file():
            continue
        if src.suffix.lower() not in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
            continue

        dst = images_dir / src.name
        shutil.copy2(src, dst)
        print(f"[COPY] {src} -> {dst}")
        image_count += 1

    if image_count == 0:
        raise RuntimeError(f"No images found in {RESIZED_IMAGES_DIR}")

    print(f"[INFO] Copied {image_count} images into ODM project.")



def run_odm():
    """
    Run ODM in Docker to create a normal orthophoto.
    """
    prepare_odm_project()

    odm_project_root = ODM_PROJECT_ROOT
    print(f"[INFO] ODM project root (host): {odm_project_root}")

    cmd = [
        "docker", "run",
        "-ti",
        "--rm",
        "-v", f"{odm_project_root}:/datasets",
        ODM_DOCKER_IMAGE,
        "--project-path", "/datasets",
        PROJECT_NAME,
        "--orthophoto-resolution", "2",  # 2 cm/pixel; 1 is sharper but slower
        "--skip-3dmodel",
        "--skip-report",
    ]

    print("\n[INFO] Executing ODM command:")
    print(" ", " ".join(cmd), "\n")

    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        raise RuntimeError(f"ODM failed with exit code {result.returncode}")

    print("[INFO] ODM processing finished.")
    print("Orthophoto should be here:")
    print("  data/odm_project/project/odm_orthophoto/odm_orthophoto.tif")


def main():
    print(f"[AgriVision] Base directory: {BASE_DIR}")
    print("[AgriVision] Running ODM for orthophoto...")
    run_odm()


if __name__ == "__main__":
    main()

