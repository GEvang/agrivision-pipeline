#!/usr/bin/env python3
"""Backward-compatible pipeline entrypoint.

The orchestration logic now lives in :mod:`agrivision.pipeline.orchestrator`.
This wrapper is retained so existing imports and scripts continue to work.
"""

from agrivision.pipeline.orchestrator import run_full_pipeline

__all__ = ["run_full_pipeline"]
