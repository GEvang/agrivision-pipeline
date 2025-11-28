#!/usr/bin/env python3
"""
compute_ndvi.py

Standalone script to compute NDVI from an orthophoto GeoTIFF using rasterio.

Usage (from ~/odm_test):

    python3 compute_ndvi.py \
        --input odm_project/odm_orthophoto/odm_orthophoto.tif \
        --output ndvi.tif \
        --camera sample_mapir_unknown
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio

# Camera band configuration.
# You can add more profiles here later.
CAMERA_CONFIG = {
    # From our analysis of your purple orthomosaic:
    # Band 1 = RED, Band 4 = NIR
    "sample_mapir_unknown": {
        "red_band": 1,
        "nir_band": 4,
    },
    # Example for a generic 4-band multispectral [B, G, R, NIR]
    "multispectral_4band": {
        "red_band": 3,
        "nir_band": 4,
    },
}


def compute_ndvi(input_path: Path, output_path: Path, camera: str) -> None:
    """Compute NDVI from an orthophoto and save it as a GeoTIFF."""

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

        # Read the bands as float32 for safe math
        red = src.read(red_idx).astype("float32")
        nir = src.read(nir_idx).astype("float32")

        # NDVI = (NIR - RED) / (NIR + RED)
        print("Computing NDVI...")
        num = nir - red
        den = nir + red

        ndvi = np.zeros_like(num, dtype="float32")
        np.divide(num, den, out=ndvi, where=(den != 0))

        # Optional: clip to [-1, 1] to clean up numerical noise
        ndvi = np.clip(ndvi, -1.0, 1.0)

        # Prepare single-band output profile
        profile.update(
            dtype="float32",
            count=1,
            nodata=0,
        )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Writing NDVI GeoTIFF to: {output_path}")
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(ndvi, 1)

    print("NDVI computation completed.")


def main():
    parser = argparse.ArgumentParser(
        description="Compute NDVI from an orthophoto GeoTIFF."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="odm_project/odm_orthophoto/odm_orthophoto.tif",
        help="Path to input orthophoto GeoTIFF",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="ndvi.tif",
        help="Path to output NDVI GeoTIFF",
    )
    parser.add_argument(
        "--camera",
        "-c",
        default="sample_mapir_unknown",
        help="Camera profile to use (e.g. sample_mapir_unknown, multispectral_4band)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    compute_ndvi(input_path, output_path, args.camera)


if __name__ == "__main__":
    main()

