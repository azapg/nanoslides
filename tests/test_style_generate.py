from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from nanoslides.cli.commands import style as style_commands
from nanoslides.core.style import load_project_style
from nanoslides.core.style_steal import (
    GeminiStyleStealAnalyzer,
    StyleStealSuggestion,
    load_style_steal_source,
)


class _FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=(
                '{"base_prompt":"clean modern editorial style",'
                '"negative_prompt":"busy, cluttered, low-contrast",'
                '"reference_comments":["Prefer balanced whitespace"],'
                '"use_as_base_reference":true,'
                '"base_reference_reason":"The references provide reusable visual anchors."}'
            )
        )


def test_analyze_instruction_uses_gemini_3_pro_with_reference_images(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"fake-image-bytes")
    source = load_style_steal_source(reference)

    fake_models = _FakeModels()
    analyzer = object.__new__(GeminiStyleStealAnalyzer)
    analyzer._client = SimpleNamespace(models=fake_models)

    suggestion = analyzer.analyze_instruction(
        instruction="Clean minimal Swiss-inspired corporate look.",
        reference_sources=[source],
    )

    assert suggestion == StyleStealSuggestion(
        base_prompt="clean modern editorial style",
        negative_prompt="busy, cluttered, low-contrast",
        reference_comments=["Prefer balanced whitespace"],
        use_as_base_reference=True,
        base_reference_reason="The references provide reusable visual anchors.",
    )
    assert len(fake_models.calls) == 1
    call = fake_models.calls[0]
    assert call["model"] == "gemini-3-pro-preview"
    assert any(
        isinstance(content, str) and "Style instruction:" in content
        for content in call["contents"]  # type: ignore[index]
    )


def test_analyze_instruction_requires_non_empty_instruction() -> None:
    analyzer = object.__new__(GeminiStyleStealAnalyzer)
    analyzer._client = SimpleNamespace(models=_FakeModels())
    with pytest.raises(ValueError, match="Instruction cannot be empty"):
        analyzer.analyze_instruction(instruction="   ")


def test_style_generate_command_writes_project_style(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "brand.png"
    reference.write_bytes(b"fake-image-bytes")
    output_path = tmp_path / "style.json"
    captured: dict[str, object] = {}

    class _FakeAnalyzer:
        def __init__(self, *, api_key: str, timeout_seconds: float = 120.0) -> None:
            captured["api_key"] = api_key
            captured["timeout_seconds"] = timeout_seconds

        def analyze_instruction(
            self, *, instruction: str, reference_sources: list[object] | None = None
        ) -> StyleStealSuggestion:
            captured["instruction"] = instruction
            captured["reference_count"] = len(reference_sources or [])
            return StyleStealSuggestion(
                base_prompt="refined minimalist brand style",
                negative_prompt="no heavy textures or ornate fonts",
                reference_comments=["Use restrained blue and gray accents."],
                use_as_base_reference=True,
                base_reference_reason="References capture a reusable brand language.",
            )

    monkeypatch.setattr(style_commands, "load_global_config", lambda: object())
    monkeypatch.setattr(style_commands, "get_gemini_api_key", lambda _config: "test-key")
    monkeypatch.setattr(style_commands, "GeminiStyleStealAnalyzer", _FakeAnalyzer)

    style_commands.style_generate_command(
        instruction="Create a restrained enterprise visual system.",
        reference_image=[reference],
        output=output_path,
        timeout_seconds=30,
    )

    saved_style = load_project_style(output_path)
    assert saved_style is not None
    assert saved_style.base_prompt == "refined minimalist brand style"
    assert saved_style.reference_images == ["brand.png"]
    assert captured == {
        "api_key": "test-key",
        "timeout_seconds": 30.0,
        "instruction": "Create a restrained enterprise visual system.",
        "reference_count": 1,
    }
