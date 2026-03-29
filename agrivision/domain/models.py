from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StageArtifact:
    name: str
    path: Path
    description: str = ""


@dataclass
class StageResult:
    stage_name: str
    success: bool = True
    artifacts: list[StageArtifact] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class PipelineContext:
    project_root: Path
    config: dict[str, Any]
    output_root: Path


@dataclass
class PipelineRunSummary:
    resize: StageResult | None = None
    odm_rgb: StageResult | None = None
    odm_mapir: StageResult | None = None
    vegetation_index: StageResult | None = None
    grid: StageResult | None = None
    weather: StageResult | None = None
    irrigation: StageResult | None = None
    report: StageResult | None = None
