"""Local project state helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml

PROJECT_STATE_FILE = Path("slides.yaml")


class SlideEntry(BaseModel):
    """Metadata for a generated slide."""

    id: str | None = None
    prompt: str = ""
    image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectState(BaseModel):
    """State file model stored in ./slides.yaml."""

    name: str
    created_at: datetime
    engine: str
    slides: list[SlideEntry] = Field(default_factory=list)


def load_project_state(path: Path = PROJECT_STATE_FILE) -> ProjectState:
    """Load local project state from YAML."""
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = raw_data if raw_data is not None else {}
    return ProjectState.model_validate(data)


def save_project_state(state: ProjectState, path: Path = PROJECT_STATE_FILE) -> None:
    """Write local project state to YAML."""
    serialized = state.model_dump(mode="json")
    path.write_text(yaml.safe_dump(serialized, sort_keys=False), encoding="utf-8")

