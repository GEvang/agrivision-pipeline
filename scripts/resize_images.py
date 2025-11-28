#!/usr/bin/env python3
"""
resize_images.py

Resize original drone images into a smaller size to speed up ODM.

Input:  data/images_full/
Output: data/images_resized/

Run from project root:
    python3 scripts/resize_images.py
"""

import os
from pathlib import Path

from PIL import Image


# Base project directory = folder that contains "scripts", "data", etc.
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "data" / "images_full"
OUTPUT_DIR = BASE_DIR / "data" / "images_resized"

# Maximum width/height for resized images (in pixels)
MAX_SIZE = 2000  # adjust later if needed


def resize_image(src_path: Path, dst_path: Path) -> None:
    """Resize a single image and save it to dst_path."""
    with Image.open(src_path) as img:
        img.thumbnail((MAX_SIZE, MAX_SIZE))

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(dst_path, format=img.format, quality=90)


def main():
    print(f"Base directory: {BASE_DIR}")
    print(f"Input images:  {INPUT_DIR}")
    print(f"Output images: {OUTPUT_DIR}")

    if not INPUT_DIR.exists():
        print(f"[ERROR] Input folder does not exist: {INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    for filename in os.listdir(INPUT_DIR):
        src = INPUT_DIR / filename

        if not src.is_file():
            continue

        # Only process common image formats
        if src.suffix.lower() not in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
            continue

        dst = OUTPUT_DIR / filename
        print(f"Resizing: {src.name} -> {dst.relative_to(BASE_DIR)}")
        resize_image(src, dst)
        count += 1

    print(f"\nDone. Resized {count} images.")


if __name__ == "__main__":
    main()

