#!/usr/bin/env python3
"""
AgriVision ADS entry point.

Run the full pipeline with:

    python run.py

or:

    python3 run.py
"""

from agrivision.pipeline.controller import run_full_pipeline

if __name__ == "__main__":
    run_full_pipeline()

