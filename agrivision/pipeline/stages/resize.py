#!/usr/bin/env python3
"""
agrivision.pipeline.stages.resize

Resize original images before ODM.

Resizing behavior is now controlled by:
  - The CLI flag: --run-resize  (whether the step runs at all)
  - config.yaml -> resize.max_long_edge  (how aggressively to resize)

This module now supports three datasets:

  - RGB images:
      data/images_full/rgb     -> data/images_resized/rgb

  - MAPIR images (multispectral):
      data/images_full/mapir   -> data/images_resized/mapir

  - Thermal images:
      data/images_full/thermal -> data/images_resized/thermal

If a given source folder is missing or empty, that dataset is skipped
with a friendly message.
"""

import shutil
from pathlib import Path

from PIL import Image

from agrivision.config.settings import get_project_root, load_config

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _get_resize_settings() -> dict:
    """
    Resolve resize-related config at call time instead of import time.
    """
    config = load_config()
    project_root = get_project_root()

    paths_cfg = config.get("paths", {})
    resize_cfg = config.get("resize", {})

    return {
        "project_root": project_root,
        "images_full_rgb": project_root / paths_cfg["images_full"],
        "images_resized_rgb": project_root / paths_cfg["images_resized"],
        "images_full_mapir": project_root / paths_cfg["images_full_mapir"],
        "images_resized_mapir": project_root / paths_cfg["images_resized_mapir"],
        "images_full_thermal": project_root / paths_cfg["images_full_thermal"],
        "images_resized_thermal": project_root / paths_cfg["images_resized_thermal"],
        "max_long_edge": resize_cfg.get("max_long_edge", 3000),
    }

def _resize_dataset(src_dir: Path, dst_dir: Path, label: str, max_long_edge: int) -> int:
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
    print(f"         Max long edge: {max_long_edge} px")

    for img_path in image_files:
        out_path = dst_dir / img_path.name

        with Image.open(img_path) as img:
            w, h = img.size
            long_edge = max(w, h)

            if long_edge <= max_long_edge:
                print(f"[Resize] {label}: already small → copying {img_path.name}")
                shutil.copy2(img_path, out_path)
                processed += 1
                continue

            scale = max_long_edge / long_edge
            new_size = (int(w * scale), int(h * scale))

            print(f"[Resize] {label}: resizing {img_path.name} to {new_size}")
            img = img.resize(new_size, Image.LANCZOS)
            img.save(out_path, quality=95)
            processed += 1

    print(f"[Resize] {label}: completed, processed {processed} images.")
    return processed


def run_resize() -> None:
    """
    Resize images for all supported datasets (RGB, MAPIR, thermal).

    - RGB:
        data/images_full/rgb     -> data/images_resized/rgb

    - MAPIR:
        data/images_full/mapir   -> data/images_resized/mapir

    If a dataset has no images, it is skipped.
    """
    settings = _get_resize_settings()
    max_long_edge = settings["max_long_edge"]
    images_full_rgb = settings["images_full_rgb"]
    images_resized_rgb = settings["images_resized_rgb"]
    images_full_mapir = settings["images_full_mapir"]
    images_resized_mapir = settings["images_resized_mapir"]
    images_full_thermal = settings["images_full_thermal"]
    images_resized_thermal = settings["images_resized_thermal"]

    print("\n[AgriVision] Resize step")
    print(f"  Max long edge : {max_long_edge} px\n")

    total_processed = 0

    # 1) RGB dataset (current main pipeline)
    total_processed += _resize_dataset(
        src_dir=images_full_rgb,
        dst_dir=images_resized_rgb,
        label="RGB",
        max_long_edge=max_long_edge,
    )

    # 2) MAPIR dataset
    total_processed += _resize_dataset(
        src_dir=images_full_mapir,
        dst_dir=images_resized_mapir,
        label="MAPIR",
        max_long_edge=max_long_edge,
    )

    # 3) Thermal dataset
    total_processed += _resize_dataset(
        src_dir=images_full_thermal,
        dst_dir=images_resized_thermal,
        label="Thermal",
        max_long_edge=max_long_edge,
    )

    if total_processed == 0:
        print("[AgriVision] WARNING: No images were processed in the resize step.")
        print("  Make sure you have placed images in at least one of:")
        print(f"    - {images_full_rgb}")
        print(f"    - {images_full_mapir}")
        print(f"    - {images_full_thermal}")
    else:
        print(f"[AgriVision] Resize step finished. Total images processed: {total_processed}")


if __name__ == "__main__":
    run_resize()
