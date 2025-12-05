#!/usr/bin/env python3
"""
agrivision.pipeline.resize

Optionally resize original images before ODM.
Resizing can be disabled entirely using config.yaml:

resize:
  enabled: true
  max_long_edge: 3000
"""

from pathlib import Path
from PIL import Image

from agrivision.utils.settings import get_project_root, load_config

CONFIG = load_config()
PROJECT_ROOT = get_project_root()

IMAGES_FULL_DIR = PROJECT_ROOT / CONFIG["paths"]["images_full"]
IMAGES_RESIZED_DIR = PROJECT_ROOT / CONFIG["paths"]["images_resized"]

RESIZE_ENABLED = CONFIG.get("resize", {}).get("enabled", True)
MAX_LONG_EDGE = CONFIG.get("resize", {}).get("max_long_edge", 3000)


def run_resize() -> None:
    """
    If enabled, resize images so their longest side <= MAX_LONG_EDGE.
    If disabled, simply copy original images into the resized folder.
    """

    print("\n[AgriVision] Resize step")
    print(f"  Enabled: {RESIZE_ENABLED}")
    print(f"  Max long edge: {MAX_LONG_EDGE} px")
    print(f"  Input folder: {IMAGES_FULL_DIR}")
    print(f"  Output folder: {IMAGES_RESIZED_DIR}")

    if not IMAGES_FULL_DIR.exists():
        raise FileNotFoundError(f"Source folder missing: {IMAGES_FULL_DIR}")

    IMAGES_RESIZED_DIR.mkdir(parents=True, exist_ok=True)

    image_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    for img_path in sorted(IMAGES_FULL_DIR.iterdir()):
        if img_path.suffix.lower() not in image_exts:
            continue

        out_path = IMAGES_RESIZED_DIR / img_path.name

        # If resizing disabled → just copy file
        if not RESIZE_ENABLED:
            print(f"[Resize] Skipping resize, copying {img_path.name}")
            out_path.write_bytes(img_path.read_bytes())
            continue

        # Resize enabled
        with Image.open(img_path) as img:
            w, h = img.size
            long_edge = max(w, h)

            if long_edge <= MAX_LONG_EDGE:
                print(f"[Resize] Already small enough → copying {img_path.name}")
                out_path.write_bytes(img_path.read_bytes())
                continue

            scale = MAX_LONG_EDGE / long_edge
            new_size = (int(w * scale), int(h * scale))

            print(f"[Resize] Resizing {img_path.name} to {new_size}")
            img = img.resize(new_size, Image.LANCZOS)
            img.save(out_path, quality=95)

    print("[AgriVision] Resize step completed.")

