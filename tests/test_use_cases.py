from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from nanoslides.core.presentation import Presentation
from nanoslides.core.style_steal import load_style_steal_source


def _seed_presentation() -> Presentation:
    presentation = Presentation(
        name="Roadmap Deck",
        created_at=datetime.now(timezone.utc),
        engine="nanobanana",
    )
    presentation.add_slide(
        prompt="Company vision overview",
        image_path="slides/1.png",
        metadata={},
    )
    presentation.add_slide(
        prompt="Market opportunity",
        image_path="slides/2.png",
        metadata={},
    )
    presentation.add_slide(
        prompt="Execution plan",
        image_path="slides/3.png",
        metadata={},
    )
    return presentation


def _require_method(obj: object, method_name: str):
    method = getattr(obj, method_name, None)
    if method is None:
        owner_name = obj.__name__ if hasattr(obj, "__name__") else obj.__class__.__name__
        pytest.fail(
            f"Missing API contract: {owner_name}.{method_name} "
            "should exist for this use case."
        )
    return method


def test_create_presentation_from_single_prompt_use_case() -> None:
    create_from_prompt = _require_method(Presentation, "create_from_prompt")
    presentation = create_from_prompt(
        prompt="Create a 6-slide investor deck about fusion energy.",
        language="en",
        target_slide_count=6,
    )
    assert isinstance(presentation, Presentation)
    assert len(presentation.ordered_main_slides) >= 1


def test_create_presentation_from_pdf_spec_use_case(tmp_path: Path) -> None:
    pdf_path = tmp_path / "research.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    create_from_pdf_spec = _require_method(Presentation, "create_from_pdf_spec")
    presentation = create_from_pdf_spec(
        source_pdf=pdf_path,
        objective="Convert this paper into a concise technical talk.",
        language="en",
    )
    assert isinstance(presentation, Presentation)
    assert len(presentation.ordered_main_slides) >= 3


def test_change_order_of_existing_slides_use_case() -> None:
    presentation = _seed_presentation()
    original_order = [slide.id for slide in presentation.ordered_main_slides]
    moving_slide_id = original_order[1]

    from_pos, to_pos = presentation.move_slide(moving_slide_id, 1)
    reordered_ids = [slide.id for slide in presentation.ordered_main_slides]

    assert (from_pos, to_pos) == (2, 1)
    assert reordered_ids[0] == moving_slide_id
    assert set(reordered_ids) == set(original_order)


def test_translate_entire_presentation_use_case() -> None:
    presentation = _seed_presentation()
    translate = _require_method(presentation, "translate")
    translated = translate(target_language="es")

    assert isinstance(translated, Presentation)
    assert len(translated.ordered_main_slides) == len(presentation.ordered_main_slides)
    assert translated is not presentation


def test_generate_single_dramatic_style_break_slide_use_case() -> None:
    presentation = _seed_presentation()
    add_style_break_slide = _require_method(presentation, "add_style_break_slide")
    first_slide_id = presentation.ordered_main_slides[0].id
    dramatic_slide = add_style_break_slide(
        after_slide_id=first_slide_id,
        prompt="Generate a high-contrast cinematic shock slide for emphasis.",
        style_override={
            "base_prompt": "neo-noir, dramatic lighting, deep shadows, punchy contrast"
        },
    )

    assert dramatic_slide.metadata.get("style_break") is True
    assert dramatic_slide.order == 2


def test_steal_style_from_existing_powerpoint_use_case(tmp_path: Path) -> None:
    source_pptx = tmp_path / "brand_deck.pptx"
    source_pptx.write_bytes(b"placeholder-pptx-content")

    source = load_style_steal_source(source_pptx)
    assert source.kind.value in {"pptx", "presentation"}

