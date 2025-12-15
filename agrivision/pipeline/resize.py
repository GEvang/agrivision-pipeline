#!/usr/bin/env python3
"""
agrivision.pipeline.resize

Resize original images before ODM.

Resizing behavior is now controlled by:
  - The CLI flag: --run-resize  (whether the step runs at all)
  - config.yaml -> resize.max_long_edge  (how aggressively to resize)

This module now supports TWO datasets:

  - RGB images:
      data/images_full/rgb     -> data/images_resized/rgb

  - MAPIR images (multispectral):
      data/images_full/mapir   -> data/images_resized/mapir

If a given source folder is missing or empty, that dataset is skipped
with a friendly message.
"""

from pathlib import Path
from PIL import Image
import shutil

from agrivision.utils.settings import get_project_root, load_config

CONFIG = load_config()
PROJECT_ROOT = get_project_root()

# RGB paths (current pipeline uses these)
IMAGES_FULL_RGB = PROJECT_ROOT / CONFIG["paths"]["images_full"]
IMAGES_RESIZED_RGB = PROJECT_ROOT / CONFIG["paths"]["images_resized"]

# MAPIR paths (reserved for MAPIR-based NDVI; wired in future steps)
IMAGES_FULL_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_full_mapir"]
IMAGES_RESIZED_MAPIR = PROJECT_ROOT / CONFIG["paths"]["images_resized_mapir"]

MAX_LONG_EDGE = CONFIG.get("resize", {}).get("max_long_edge", 3000)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _resize_dataset(src_dir: Path, dst_dir: Path, label: str) -> int:
    """
    Resize all images in src_dir into dst_dir for a given dataset label.

    Returns the number of processed images.
    """
    if not src_dir.exists():
        print(f"[Resize] {label}: source folder does not exist, skipping: {src_dir}")
        return 0

    # Collect images
    image_files = [
        p for p in sorted(src_dir.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]

    if not image_files:
        print(f"[Resize] {label}: no images found in {src_dir}, skipping.")
        return 0

    dst_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    print(f"[Resize] {label}: processing {len(image_files)} images...")
    print(f"         Input folder : {src_dir}")
    print(f"         Output folder: {dst_dir}")
    print(f"         Max long edge: {MAX_LONG_EDGE} px")

    for img_path in image_files:
        out_path = dst_dir / img_path.name

        with Image.open(img_path) as img:
            w, h = img.size
            long_edge = max(w, h)

            if long_edge <= MAX_LONG_EDGE:
                print(f"[Resize] {label}: already small → copying {img_path.name}")
                shutil.copy2(img_path, out_path)
                processed += 1
                continue

            scale = MAX_LONG_EDGE / long_edge
            new_size = (int(w * scale), int(h * scale))

            print(f"[Resize] {label}: resizing {img_path.name} to {new_size}")
            img = img.resize(new_size, Image.LANCZOS)
            img.save(out_path, quality=95)
            processed += 1

    print(f"[Resize] {label}: completed, processed {processed} images.")
    return processed


def run_resize() -> None:
    """
    Resize images for all supported datasets (RGB, MAPIR).

    - RGB:
        data/images_full/rgb     -> data/images_resized/rgb

    - MAPIR:
        data/images_full/mapir   -> data/images_resized/mapir

    If a dataset has no images, it is skipped.
    """
    print("\n[AgriVision] Resize step")
    print(f"  Max long edge : {MAX_LONG_EDGE} px\n")

    total_processed = 0

    # 1) RGB dataset (current main pipeline)
    total_processed += _resize_dataset(
        src_dir=IMAGES_FULL_RGB,
        dst_dir=IMAGES_RESIZED_RGB,
        label="RGB",
    )

    # 2) MAPIR dataset (for real NDVI, wired in next steps)
    total_processed += _resize_dataset(
        src_dir=IMAGES_FULL_MAPIR,
        dst_dir=IMAGES_RESIZED_MAPIR,
        label="MAPIR",
    )

    if total_processed == 0:
        print("[AgriVision] WARNING: No images were processed in the resize step.")
        print("  Make sure you have placed images in at least one of:")
        print(f"    - {IMAGES_FULL_RGB}")
        print(f"    - {IMAGES_FULL_MAPIR}")
    else:
        print(f"[AgriVision] Resize step finished. Total images processed: {total_processed}")


if __name__ == "__main__":
    run_resize()
