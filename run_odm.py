#!/usr/bin/env python3
import subprocess
from pathlib import Path
import argparse
import shutil
import os

def run_odm(images_dir, project_dir):
    images_path = Path(images_dir).resolve()
    project_path = Path(project_dir).resolve()

    # SAFETY: make sure images exist
    if not images_path.exists():
        print(f"ERROR: Images directory does not exist: {images_path}")
        return

    # MANUAL DELETION — keep things clean
    if project_path.exists():
        print(f"Deleting old ODM project: {project_path}")
        shutil.rmtree(project_path)

    # Recreate project/images folder
    print("Creating new ODM project folder...")
    images_target = project_path / "images"
    images_target.mkdir(parents=True, exist_ok=True)

    # Copy resized images into odm_project/images
    exts = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    files = [f for f in images_path.iterdir() if f.suffix in exts]

    print(f"Copying {len(files)} images into odm_project/images ...")
    for f in files:
        shutil.copy2(f, images_target / f.name)

    # Build the correct ODM docker call
    cmd = [
        "docker", "run", "--rm", "-ti",
        "-v", f"{project_path.parent}:/datasets",
        "opendronemap/odm",
        "--project-path", "/datasets",
        "--orthophoto-resolution", "2",
        "--ignore-gsd",
        "--fast-orthophoto",
        "--feature-quality", "low",
        "--pc-quality", "low",
        project_path.name,   # dataset name (MUST be last)
    ]

    print("\nRunning ODM with command:")
    print(" ".join(cmd))
    print("\nProcessing...\n")

    subprocess.run(cmd)

    print("ODM finished.")
    print(f"Orthophoto should be at:")
    print(project_path / "odm_orthophoto" / "odm_orthophoto.tif")


def main():
    parser = argparse.ArgumentParser(
        description="Run ODM via Docker on resized images."
    )

    parser.add_argument(
        "--images", "-i",
        default="images_resized",
        help="Folder containing resized images",
    )
    parser.add_argument(
        "--project", "-p",
        default="odm_project",
        help="ODM project folder name",
    )

    args = parser.parse_args()
    run_odm(args.images, args.project)

if __name__ == "__main__":
    main()

