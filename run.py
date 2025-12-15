#!/usr/bin/env python3
"""
AgriVision ADS entry point.

Run the full pipeline with:

    python run.py

or:

    python3 run.py

Control which steps run using CLI flags:

    python run.py --run-resize
    python run.py --skip-odm
    python run.py --skip-ndvi
    python run.py --run-resize --skip-odm --skip-ndvi
"""

import argparse

from agrivision.pipeline.controller import run_full_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AgriVision ADS pipeline entry point."
    )

    parser.add_argument(
        "--run-resize",
        action="store_true",
        help=(
            "Run the image resizing step before ODM. "
            "By default, resizing is skipped and the pipeline expects "
            "resized images to already exist in the configured folder."
        ),
    )

    parser.add_argument(
        "--skip-odm",
        action="store_true",
        help=(
            "Skip the ODM orthophoto generation step and reuse an existing "
            "orthophoto if available. The controller will fail early with a "
            "clear error if no orthophoto is found."
        ),
    )

    parser.add_argument(
        "--skip-ndvi",
        action="store_true",
        help=(
            "Skip NDVI computation and reuse existing NDVI outputs if "
            "available. The controller will fail early if no NDVI GeoTIFF "
            "is found."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_full_pipeline(
        run_resize_step=args.run_resize,
        skip_odm=args.skip_odm,
        skip_ndvi=args.skip_ndvi,
    )


if __name__ == "__main__":
    main()
