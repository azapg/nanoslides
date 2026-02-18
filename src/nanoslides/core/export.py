"""Slide deck export helpers."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol

from pptx import Presentation
from pptx.util import Emu

_SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class ExportFormat(str, Enum):
    """Supported export targets."""

    PPTX = "pptx"


class SlideDeckExporter(Protocol):
    """Exporter contract for slide deck formats."""

    def export(self, slide_images: list[Path], output_path: Path) -> None:
        """Export slide images into a deck file."""


class PptxSlideDeckExporter:
    """PowerPoint exporter implementation."""

    def export(self, slide_images: list[Path], output_path: Path) -> None:
        presentation = Presentation()
        blank_layout = presentation.slide_layouts[6]
        slide_width = presentation.slide_width
        slide_height = presentation.slide_height

        for image_path in slide_images:
            slide = presentation.slides.add_slide(blank_layout)
            picture = slide.shapes.add_picture(str(image_path), Emu(0), Emu(0))
            scale = min(slide_width / picture.width, slide_height / picture.height)
            picture.width = Emu(int(picture.width * scale))
            picture.height = Emu(int(picture.height * scale))
            picture.left = Emu(int((slide_width - picture.width) / 2))
            picture.top = Emu(int((slide_height - picture.height) / 2))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        presentation.save(str(output_path))


_EXPORTERS: dict[ExportFormat, SlideDeckExporter] = {
    ExportFormat.PPTX: PptxSlideDeckExporter(),
}


def list_slide_images(slides_dir: Path) -> list[Path]:
    """Collect and sort slide image files from a directory."""
    if not slides_dir.exists():
        raise FileNotFoundError(f"Slides directory not found: {slides_dir}")
    if not slides_dir.is_dir():
        raise NotADirectoryError(f"Slides path is not a directory: {slides_dir}")

    slide_images = sorted(
        path
        for path in slides_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _SUPPORTED_IMAGE_SUFFIXES
    )
    if not slide_images:
        raise ValueError(f"No slide images found in {slides_dir}.")
    return slide_images


def export_slides(
    *,
    slides_dir: Path,
    output_path: Path,
    format: ExportFormat = ExportFormat.PPTX,
) -> Path:
    """Export all slide images from a project folder into a deck."""
    slide_images = list_slide_images(slides_dir)
    _EXPORTERS[format].export(slide_images, output_path)
    return output_path
