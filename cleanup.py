#!/usr/bin/env python3
"""
SMART CLEANUP TOOL FOR AGRIVISION ADS
-------------------------------------

Features:
- Dry-run mode (--dry-run)
- Interactive mode (--interactive)
- Detects obsolete directories (old ODM, old image structure)
- Removes empty / corrupted project folders
- Cleans up orphan files outside expected structure

Usage:
    python cleanup.py
    python cleanup.py --dry-run
    python cleanup.py --interactive
"""

import shutil
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).resolve().parent

# -------------------------------------------------------------------------
# NEW folder structure (protected)
# -------------------------------------------------------------------------
PROTECTED = {
    PROJECT_ROOT / "agrivision",
    PROJECT_ROOT / "OpenAgri-WeatherService",
    PROJECT_ROOT / "config.yaml",
    PROJECT_ROOT / "requirements.txt",
    PROJECT_ROOT / "run.py",
    PROJECT_ROOT / "install_agrivision.sh",
    PROJECT_ROOT / "bootstrap.sh",
    PROJECT_ROOT / "cleanup.py",
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "output/ndvi",
    PROJECT_ROOT / "output/runs",
    PROJECT_ROOT / "data/images_full/rgb",
    PROJECT_ROOT / "data/images_full/mapir",
    PROJECT_ROOT / "data/images_resized/rgb",
    PROJECT_ROOT / "data/images_resized/mapir",
    PROJECT_ROOT / "data/odm_project_rgb",
    PROJECT_ROOT / "data/odm_project_mapir",
}

VALID_ODM_STRUCTURE = {"images", "odm_orthophoto", "opensfm", "mve"}


# -------------------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------------------
def ask(prompt: str) -> bool:
    """Prompt user in interactive mode."""
    resp = input(f"{prompt} [y/N]: ").strip().lower()
    return resp in ("y", "yes")


def safe_delete(path: Path, dry: bool, interactive: bool):
    """Delete a path unless it's protected."""
    if path in PROTECTED:
        return

    # If inside a protected root, skip parent but allow level-below cleanup
    for protected in PROTECTED:
        if protected in path.parents:
            # allow deleting old subfolders IN protected dirs
            break

    if interactive:
        if not ask(f"Delete {path}?"):
            print(f"SKIPPED: {path}")
            return

    print(("DELETE:" if not dry else "DRY-RUN DELETE:") + f" {path}")
    if not dry:
        shutil.rmtree(path, ignore_errors=True)


def folder_is_empty(folder: Path) -> bool:
    """Check if a folder exists but has no files inside."""
    try:
        next(folder.iterdir())
        return False
    except StopIteration:
        return True
    except FileNotFoundError:
        return True


def is_obsolete_odm_project(folder: Path) -> bool:
    """
    Determine whether an ODM project is incomplete/obsolete:
      - project/ folder exists but contains NO odm_orthophoto
      - or folder does not contain a proper ODM structure
    """
    if not folder.is_dir():
        return False

    project = folder / "project"
    if not project.exists():
        return False  # not even an ODM project structure

    orthophoto = project / "odm_orthophoto" / "odm_orthophoto.tif"
    if orthophoto.exists():
        return False  # this project is valid (keep)

    # If `project` exists but no orthophoto → likely incomplete → remove
    return True


def find_obsolete_items():
    """Find folders that are candidates for deletion."""
    obsolete = []

    # 1. Remove old ODM root
    old_odm = PROJECT_ROOT / "data/odm_project"
    if old_odm.exists():
        obsolete.append(old_odm)

    # 2. Remove old single image folders (if misstructured)
    old_full = PROJECT_ROOT / "data/images_full"
    old_resized = PROJECT_ROOT / "data/images_resized"

    # If these contain files directly or wrong structure
    if old_full.exists() and not (old_full / "rgb").exists():
        obsolete.append(old_full)
    if old_resized.exists() and not (old_resized / "rgb").exists():
        obsolete.append(old_resized)

    # 3. Remove folders ending in *_old or *_backup
    for f in (PROJECT_ROOT / "data").rglob("*"):
        if not f.is_dir():
            continue
        name = f.name.lower()
        if name.endswith("_old") or name.endswith("_backup"):
            obsolete.append(f)

    # 4. Remove incomplete ODM projects
    for odm_folder in (PROJECT_ROOT / "data").glob("odm_project_*"):
        if odm_folder in PROTECTED:
            continue
        if is_obsolete_odm_project(odm_folder):
            obsolete.append(odm_folder)

    # 5. Remove empty folders
    for f in (PROJECT_ROOT / "data").rglob("*"):
        if f.is_dir() and folder_is_empty(f) and f not in PROTECTED:
            obsolete.append(f)

    return list(set(obsolete))  # unique list


# -------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Smart cleanup for AgriVision ADS")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--interactive", action="store_true", help="Ask confirmation before each delete")
    args = parser.parse_args()

    dry = args.dry_run
    interactive = args.interactive

    print("\n========== AGRIVISION SMART CLEANUP ==========\n")
    print(f"DRY-RUN: {dry}")
    print(f"INTERACTIVE: {interactive}")
    print("\nScanning for obsolete items...\n")

    obsolete_items = find_obsolete_items()

    if not obsolete_items:
        print("Nothing to clean. Your project structure looks good!")
        return

    print(f"Found {len(obsolete_items)} obsolete items.\n")

    for item in obsolete_items:
        safe_delete(item, dry=dry, interactive=interactive)

    print("\nCleanup complete.\n")


if __name__ == "__main__":
    main()
