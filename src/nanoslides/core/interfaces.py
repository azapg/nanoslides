"""Abstract interfaces for slide generation engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from nanoslides.core.style import ResolvedStyle


class SlideResult(BaseModel):
    """Result payload returned by slide generation/edit operations."""

    image_url: str
    local_path: Path | None = None
    revised_prompt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlideEngine(ABC):
    """Interface for AI image generation backends."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        style_id: str = "default",
        style: ResolvedStyle | None = None,
        ref_image: bytes | None = None,
    ) -> SlideResult:
        """Generate a slide from scratch."""

    @abstractmethod
    def edit(
        self,
        image: bytes,
        instruction: str,
        style_id: str = "default",
        style: ResolvedStyle | None = None,
        mask: dict[str, Any] | None = None,
    ) -> SlideResult:
        """Edit an existing slide."""

