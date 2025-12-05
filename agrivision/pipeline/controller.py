#!/usr/bin/env python3
"""
agrivision.pipeline.controller

AgriVision pipeline:

  1. Resize images
  2. ODM orthophoto generation (Docker)
  3. NDVI computation
  4. NDVI grid report
  5. Final HTML report


# Import pipeline modules
from agrivision.pipeline.resize import run_resize
from agrivision.pipeline.odm import run_odm
from agrivision.pipeline.ndvi import run_ndvi
from agrivision.pipeline.grid import run_grid_report
from agrivision.pipeline.report import run_report


def run_full_pipeline() -> None:
    """
    Run the entire AgriVision ADS pipeline end-to-end.

    This is the main function that will be called from run.py.
    """
    print("\n================== AgriVision Pipeline Start ==================\n")

    print("Step 1/5: Resizing images...")
    run_resize()

    print("\nStep 2/5: Running ODM to generate orthophoto...")
    run_odm()

    print("\nStep 3/5: Computing NDVI...")
    run_ndvi()  # default camera from config

    print("\nStep 4/5: Generating NDVI grid & tables...")
    run_grid_report()

    print("\nStep 5/5: Creating final HTML report...")
    run_report()

    print("\n================== Pipeline Complete ==================\n")


if __name__ == "__main__":
    run_full_pipeline()

