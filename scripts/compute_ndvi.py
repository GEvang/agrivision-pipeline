#!/usr/bin/env python3
"""
compute_ndvi.py

Compute NDVI from the ODM orthophoto and optionally save a colorized PNG.

Default paths (relative to project root):

  Input orthophoto (from ODM):
      data/odm_project/project/odm_orthophoto/odm_orthophoto.tif

  Output NDVI GeoTIFF:
      output/ndvi/ndvi.tif

  Output NDVI color PNG:
      output/ndvi/ndvi_color.png

Run from project root:
    python3 scripts/compute_ndvi.py

You can override paths and camera with CLI options:
    python3 scripts/compute_ndvi.py \
        --input-ortho data/odm_project/project/odm_orthophoto/odm_orthophoto.tif \
        --output-ndvi output/ndvi/ndvi.tif \
        --output-color output/ndvi/ndvi_color.png \
        --camera sample_mapir_unknown
"""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
import matplotlib.pyplot as plt


# ------------ CONFIGURATION ------------

# Base project directory = folder that contains "scripts", "data", "output", etc.
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_ORTHO = BASE_DIR / "data" / "odm_project" / "project" / "odm_orthophoto" / "odm_orthophoto.tif"
DEFAULT_NDVI_TIF = BASE_DIR / "output" / "ndvi" / "ndvi.tif"
DEFAULT_NDVI_COLOR = BASE_DIR / "output" / "ndvi" / "ndvi_color.png"

# Camera band configuration: which band index is RED / NIR in the orthophoto.
# NOTE: rasterio bands are 1-based.
CAMERA_CONFIG = {
    # This matches the band layout we inferred from your sample Mapir-style data
    "sample_mapir_unknown": {
        "red_band": 1,
        "nir_band": 4,
    },
    # Example for a generic 4-band multispectral (B,G,R,NIR)
    "multispectral_4band": {
        "red_band": 3,
        "nir_band": 4,
    },
}


# ------------ CORE NDVI LOGIC ------------

def compute_ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Compute NDVI = (NIR - RED) / (NIR + RED) with safety for division by zero.

    Parameters
    ----------
    red : np.ndarray
        Red band values.
    nir : np.ndarray
        Near-infrared band values.

    Returns
    -------
    np.ndarray
        NDVI array in float32, values approx in [-1, 1].
    """
    red = red.astype("float32")
    nir = nir.astype("float32")

    # Avoid division by zero
    denom = nir + red
    denom[denom == 0] = 1e-6

    ndvi = (nir - red) / denom

    # Clip to reasonable range
    ndvi = np.clip(ndvi, -1.0, 1.0)
    return ndvi.astype("float32")


def save_ndvi_geotiff(ndvi: np.ndarray, ref_src: rasterio.io.DatasetReader, out_path: Path) -> None:
    """
    Save NDVI as a single-band GeoTIFF using reference metadata from the ortho.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta = ref_src.meta.copy()
    meta.update(
        {
            "count": 1,          # single band
            "dtype": "float32",  # NDVI is continuous
        }
    )

    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(ndvi, 1)

    print(f"[OK] NDVI GeoTIFF written to: {out_path}")


def save_ndvi_color_png(ndvi: np.ndarray, out_path: Path) -> None:
    """
    Save a colorized NDVI PNG using a matplotlib colormap.

    Values in [-1, 1] are mapped to [0, 1] for display.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize NDVI to [0, 1] for visualization
    ndvi_norm = (ndvi + 1.0) / 2.0
    ndvi_norm = np.clip(ndvi_norm, 0.0, 1.0)

    plt.figure(figsize=(8, 8))
    plt.imshow(ndvi_norm, cmap="RdYlGn")  # red = low, green = high
    plt.axis("off")
    plt.tight_layout(pad=0)

    plt.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()

    print(f"[OK] NDVI color PNG written to: {out_path}")


def run_compute_ndvi(
    input_ortho: Path,
    output_ndvi_tif: Path,
    output_ndvi_color: Path | None,
    camera: str,
) -> None:
    """
    High-level NDVI computation function.
    """

    if camera not in CAMERA_CONFIG:
        raise ValueError(
            f"Unknown camera profile '{camera}'. "
            f"Available: {', '.join(CAMERA_CONFIG.keys())}"
        )

    red_band_index = CAMERA_CONFIG[camera]["red_band"]
    nir_band_index = CAMERA_CONFIG[camera]["nir_band"]

    print(f"Base directory: {BASE_DIR}")
    print(f"Input orthophoto: {input_ortho}")
    print(f"Output NDVI (tif): {output_ndvi_tif}")
    if output_ndvi_color:
        print(f"Output NDVI (color png): {output_ndvi_color}")
    print(f"Camera profile: {camera} (RED={red_band_index}, NIR={nir_band_index})")

    if not input_ortho.exists():
        raise FileNotFoundError(f"Input orthophoto not found: {input_ortho}")

    with rasterio.open(input_ortho) as src:
        if src.count < max(red_band_index, nir_band_index):
            raise ValueError(
                f"Input ortho has only {src.count} bands; "
                f"camera config expects at least {max(red_band_index, nir_band_index)}."
            )

        red = src.read(red_band_index, resampling=Resampling.nearest)
        nir = src.read(nir_band_index, resampling=Resampling.nearest)

        print("[INFO] Computing NDVI array...")
        ndvi = compute_ndvi_array(red, nir)

        print("[INFO] Saving NDVI GeoTIFF...")
        save_ndvi_geotiff(ndvi, src, output_ndvi_tif)

        if output_ndvi_color is not None:
            print("[INFO] Saving NDVI color PNG...")
            save_ndvi_color_png(ndvi, output_ndvi_color)


# ------------ CLI ENTRYPOINT ------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute NDVI from ODM orthophoto.")

    parser.add_argument(
        "--input-ortho",
        type=str,
        default=str(DEFAULT_ORTHO),
        help="Path to input orthophoto GeoTIFF (default: ODM output).",
    )
    parser.add_argument(
        "--output-ndvi",
        type=str,
        default=str(DEFAULT_NDVI_TIF),
        help="Path to output NDVI GeoTIFF.",
    )
    parser.add_argument(
        "--output-color",
        type=str,
        default=str(DEFAULT_NDVI_COLOR),
        help="Path to output NDVI color PNG. "
             "Use --output-color '' to skip PNG generation.",
    )
    parser.add_argument(
        "--camera",
        type=str,
        default="sample_mapir_unknown",
        help=f"Camera profile name ({', '.join(CAMERA_CONFIG.keys())}).",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    input_ortho = Path(args.input_ortho)
    output_ndvi_tif = Path(args.output_ndvi)
    output_ndvi_color = Path(args.output_color) if args.output_color else None

    run_compute_ndvi(
        input_ortho=input_ortho,
        output_ndvi_tif=output_ndvi_tif,
        output_ndvi_color=output_ndvi_color,
        camera=args.camera,
    )


if __name__ == "__main__":
    main()

