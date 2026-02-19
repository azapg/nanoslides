from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu

_EMU_PER_PIXEL_AT_96_DPI = 9525
_EXPORT_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "nanoslides" / "core" / "export.py"
_EXPORT_SPEC = importlib.util.spec_from_file_location("nanoslides_core_export", _EXPORT_MODULE_PATH)
assert _EXPORT_SPEC is not None and _EXPORT_SPEC.loader is not None
_EXPORT_MODULE = importlib.util.module_from_spec(_EXPORT_SPEC)
_EXPORT_SPEC.loader.exec_module(_EXPORT_MODULE)
PptxSlideDeckExporter = _EXPORT_MODULE.PptxSlideDeckExporter


def _write_image(path: Path, *, width: int, height: int) -> None:
    Image.new("RGB", (width, height), color=(20, 20, 20)).save(path)


def test_export_sets_slide_size_for_nearly_uniform_aspect_ratios(tmp_path: Path) -> None:
    first = tmp_path / "slide-01.png"
    second = tmp_path / "slide-02.png"
    output = tmp_path / "deck.pptx"
    _write_image(first, width=1376, height=768)
    _write_image(second, width=1344, height=768)

    PptxSlideDeckExporter().export([first, second], output)

    deck = Presentation(str(output))
    assert deck.slide_width == Emu(1376 * _EMU_PER_PIXEL_AT_96_DPI)
    assert deck.slide_height == Emu(768 * _EMU_PER_PIXEL_AT_96_DPI)
    assert len(deck.slides) == 2

