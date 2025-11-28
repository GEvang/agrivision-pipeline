#!/usr/bin/env python3
"""
ndvi_pipeline.py

1. Compute NDVI from an orthophoto GeoTIFF using rasterio.
2. Save NDVI as a GeoTIFF.
3. Create a colorized PNG from the NDVI.

Usage (from ~/odm_test):

    python3 ndvi_pipeline.py \
        --input odm_project/odm_orthophoto/odm_orthophoto.tif \
        --ndvi ndvi.tif \
        --png ndvi_color.png \
        --camera sample_mapir_unknown
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image  # pillow


# Camera band configuration.
# You can add more profiles here later if needed.
CAMERA_CONFIG = {
    # From your sample TIFF analysis:
    # Band 1 = RED, Band 4 = NIR
    "sample_mapir_unknown": {
        "red_band": 1,
        "nir_band": 4,
    },
    # Example for generic 4-band multispectral [B, G, R, NIR]
    "multispectral_4band": {
        "red_band": 3,
        "nir_band": 4,
    },
}


def compute_ndvi_array(input_path: Path, camera: str) -> tuple[np.ndarray, dict]:
    """Load the orthophoto and return (ndvi_array, profile)."""

    if camera not in CAMERA_CONFIG:
        raise ValueError(
            f"Unknown camera profile '{camera}'. "
            f"Known cameras: {', '.join(CAMERA_CONFIG.keys())}"
        )

    cfg = CAMERA_CONFIG[camera]

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    print(f"Opening orthophoto: {input_path}")

    with rasterio.open(input_path) as src:
        profile = src.profile.copy()

        red_idx = cfg["red_band"]
        nir_idx = cfg["nir_band"]

        print(f"Using bands -> RED: {red_idx}, NIR: {nir_idx}")

        red = src.read(red_idx).astype("float32")
        nir = src.read(nir_idx).astype("float32")

        print("Computing NDVI...")
        num = nir - red
        den = nir + red

        ndvi = np.zeros_like(num, dtype="float32")
        np.divide(num, den, out=ndvi, where=(den != 0))

        ndvi = np.clip(ndvi, -1.0, 1.0)

    return ndvi, profile


def save_ndvi_geotiff(ndvi: np.ndarray, profile: dict, output_path: Path) -> None:
    """Save NDVI array as GeoTIFF."""
    profile = profile.copy()
    profile.update(
        dtype="float32",
        count=1,
        nodata=0,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing NDVI GeoTIFF to: {output_path}")
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(ndvi, 1)


def ndvi_to_rgb(ndvi: np.ndarray) -> np.ndarray:
    """
    Map NDVI values in [-1, 1] to an RGB image using a simple colormap.
    Feel free to adjust these colors later to your taste.
    """

    ndvi = np.clip(ndvi, -1.0, 1.0)
    norm = (ndvi + 1.0) / 2.0  # -1..1 -> 0..1

    h, w = ndvi.shape
    r = np.zeros((h, w), dtype="float32")
    g = np.zeros((h, w), dtype="float32")
    b = np.zeros((h, w), dtype="float32")

    # Low NDVI: 0.0 .. 0.33
    low = norm <= 0.33
    r[low] = 0.3
    g[low] = 0.0
    b[low] = 0.7 + 0.3 * (norm[low] / 0.33)

    # Medium NDVI: 0.33 .. 0.66
    med = (norm > 0.33) & (norm <= 0.66)
    t = (norm[med] - 0.33) / (0.66 - 0.33)
    r[med] = 0.5 + 0.5 * t
    g[med] = 0.0
    b[med] = 1.0 - 0.7 * t

    # High NDVI: 0.66 .. 1.0
    high = norm > 0.66
    t2 = (norm[high] - 0.66) / (1.0 - 0.66)
    r[high] = 1.0
    g[high] = 0.5 + 0.5 * t2
    b[high] = 0.0

    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(rgb * 255.0, 0, 255).astype("uint8")
    return rgb


def save_ndvi_png(ndvi: np.ndarray, output_path: Path) -> None:
    """Save NDVI as a colorized PNG."""
    print("Converting NDVI to color PNG...")
    rgb = ndvi_to_rgb(ndvi)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(rgb, mode="RGB")
    img.save(output_path)
    print(f"Color PNG written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Compute NDVI from an orthophoto and create a colorized PNG."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="odm_project/odm_orthophoto/odm_orthophoto.tif",
        help="Input orthophoto GeoTIFF",
    )
    parser.add_argument(
        "--ndvi",
        "-n",
        default="ndvi.tif",
        help="Output NDVI GeoTIFF filename",
    )
    parser.add_argument(
        "--png",
        "-p",
        default="ndvi_color.png",
        help="Output color PNG filename",
    )
    parser.add_argument(
        "--camera",
        "-c",
        default="sample_mapir_unknown",
        help="Camera profile (e.g. sample_mapir_unknown, multispectral_4band)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    ndvi_path = Path(args.ndvi)
    png_path = Path(args.png)

    # 1. Compute NDVI array + profile
    ndvi, profile = compute_ndvi_array(input_path, args.camera)

    # 2. Save NDVI GeoTIFF
    save_ndvi_geotiff(ndvi, profile, ndvi_path)

    # 3. Save colorized PNG
    save_ndvi_png(ndvi, png_path)

    print("NDVI pipeline completed successfully.")


if __name__ == "__main__":
    main()

