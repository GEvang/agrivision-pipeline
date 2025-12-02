#!/usr/bin/env python3
"""
resize_images.py

Resize original images from data/images_full/ into data/images_resized/
to speed up ODM, while keeping enough resolution for good orthophotos.

- Only resizes if the longest edge > MAX_LONG_EDGE
- Otherwise just copies the file

Usage (from project root):

    source venv/bin/activate
    python3 scripts/resize_images.py
"""

from pathlib import Path
from PIL import Image

# -------- CONFIG --------
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "data" / "images_full"
OUTPUT_DIR = BASE_DIR / "data" / "images_resized"

# Max size of the LONGEST side, in pixels.
# 3000 is a good compromise: smaller than original, but still detailed.
MAX_LONG_EDGE = 3000

# JPEG quality (if input is JPG)
JPEG_QUALITY = 85
# ------------------------


def resize_image(src: Path, dst: Path) -> None:
    with Image.open(src) as im:
        im = im.convert("RGB")

        width, height = im.size
        long_edge = max(width, height)

        if long_edge <= MAX_LONG_EDGE:
            # No need to resize, just save a copy
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst, quality=JPEG_QUALITY)
            print(f"[COPY] {src.name} -> {dst.name} (no resize)")
            return

        scale = MAX_LONG_EDGE / float(long_edge)
        new_size = (int(width * scale), int(height * scale))

        im = im.resize(new_size, Image.LANCZOS)

        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, quality=JPEG_QUALITY)
        print(f"[RESIZE] {src.name}: {width}x{height} -> {new_size[0]}x{new_size[1]}")


def main():
    print(f"Input directory:  {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_DIR.exists():
        print(f"[ERROR] Input directory does not exist: {INPUT_DIR}")
        return

    count = 0
    for src in sorted(INPUT_DIR.iterdir()):
        if not src.is_file():
            continue
        if src.suffix.lower() not in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]:
            continue

        dst = OUTPUT_DIR / src.name
        resize_image(src, dst)
        count += 1

    print(f"\nDone. Processed {count} images.")


if __name__ == "__main__":
    main()

