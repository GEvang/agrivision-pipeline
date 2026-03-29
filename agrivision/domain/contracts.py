from __future__ import annotations

from typing import Protocol

from .models import PipelineContext, StageResult


class PipelineStage(Protocol):
    def __call__(self, context: PipelineContext) -> StageResult: ...
