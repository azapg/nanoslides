from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from nanoslides.cli.commands import style as style_commands
from nanoslides.core.style import GlobalStylesConfig, load_project_style
import nanoslides.core.style_steal as style_steal_module
from nanoslides.core.style_steal import (
    GeminiStyleStealAnalyzer,
    StyleStealSuggestion,
    infer_project_style_from_instruction,
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


def test_style_analyzer_initializes_timeout_in_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_client(*, api_key: str, http_options: object) -> object:
        captured["api_key"] = api_key
        captured["http_options"] = http_options
        return SimpleNamespace(models=_FakeModels())

    monkeypatch.setattr(style_steal_module.genai, "Client", _fake_client)
    GeminiStyleStealAnalyzer(api_key="abc", timeout_seconds=120.0)

    assert captured["api_key"] == "abc"
    http_options = captured["http_options"]
    assert getattr(http_options, "timeout", None) == 120000


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


def test_analyze_instruction_wraps_read_timeout() -> None:
    class _TimeoutModels:
        def generate_content(self, **kwargs: object) -> object:
            raise httpx.ReadTimeout("timed out")

    analyzer = object.__new__(GeminiStyleStealAnalyzer)
    analyzer._client = SimpleNamespace(models=_TimeoutModels())
    with pytest.raises(RuntimeError, match="Style analysis timed out"):
        analyzer.analyze_instruction(instruction="Generate a calm style.")


def test_infer_project_style_from_instruction_keeps_style_in_memory() -> None:
    class _FakeAnalyzer:
        def analyze_instruction(
            self, *, instruction: str, reference_sources: list[object] | None = None
        ) -> StyleStealSuggestion:
            assert instruction == "Minimal visual language."
            assert reference_sources == []
            return StyleStealSuggestion(
                base_prompt="minimal editorial look",
                negative_prompt="no visual clutter",
                reference_comments=["Prioritize whitespace."],
                use_as_base_reference=False,
                base_reference_reason="No reference images were provided.",
            )

    inferred = infer_project_style_from_instruction(
        analyzer=_FakeAnalyzer(),
        instruction="Minimal visual language.",
        reference_sources=[],
    )

    assert inferred.project_style.base_prompt == "minimal editorial look"
    assert inferred.project_style.reference_images == []
    assert inferred.suggestion.base_reference_reason == "No reference images were provided."


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
        set_base_reference=False,
        global_scope=False,
        style_id=None,
        output=output_path,
        timeout_seconds=30,
        no_interactive=True,
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


def test_style_generate_command_can_discard_after_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "style.json"

    class _FakeAnalyzer:
        def __init__(self, *, api_key: str, timeout_seconds: float = 120.0) -> None:
            pass

        def analyze_instruction(
            self, *, instruction: str, reference_sources: list[object] | None = None
        ) -> StyleStealSuggestion:
            return StyleStealSuggestion(
                base_prompt="preview-only",
                negative_prompt="none",
                reference_comments=[],
                use_as_base_reference=False,
                base_reference_reason="No references provided.",
            )

    monkeypatch.setattr(style_commands, "load_global_config", lambda: object())
    monkeypatch.setattr(style_commands, "get_gemini_api_key", lambda _config: "test-key")
    monkeypatch.setattr(style_commands, "GeminiStyleStealAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(
        style_commands,
        "sys",
        SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True)),
    )
    monkeypatch.setattr(style_commands.Confirm, "ask", lambda *args, **kwargs: False)

    style_commands.style_generate_command(
        instruction="Preview but do not save.",
        reference_image=[],
        set_base_reference=False,
        global_scope=False,
        style_id=None,
        output=output_path,
        timeout_seconds=30,
        no_interactive=False,
    )

    assert not output_path.exists()


def test_style_generate_command_can_save_globally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = tmp_path / "brand.png"
    reference.write_bytes(b"fake-image-bytes")
    saved: dict[str, GlobalStylesConfig] = {}
    registry = GlobalStylesConfig()

    class _FakeAnalyzer:
        def __init__(self, *, api_key: str, timeout_seconds: float = 120.0) -> None:
            pass

        def analyze_instruction(
            self, *, instruction: str, reference_sources: list[object] | None = None
        ) -> StyleStealSuggestion:
            return StyleStealSuggestion(
                base_prompt="global-style",
                negative_prompt="avoid clutter",
                reference_comments=["Stay minimal."],
                use_as_base_reference=True,
                base_reference_reason="Reference is reusable.",
            )

    monkeypatch.setattr(style_commands, "load_global_config", lambda: object())
    monkeypatch.setattr(style_commands, "get_gemini_api_key", lambda _config: "test-key")
    monkeypatch.setattr(style_commands, "GeminiStyleStealAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(style_commands, "load_global_styles", lambda: registry)
    monkeypatch.setattr(
        style_commands, "save_global_styles", lambda styles: saved.setdefault("styles", styles)
    )

    style_commands.style_generate_command(
        instruction="Save as global style.",
        reference_image=[reference],
        set_base_reference=False,
        global_scope=True,
        style_id="brand-global",
        output=tmp_path / "unused-style.json",
        timeout_seconds=30,
        no_interactive=True,
    )

    assert "styles" in saved
    assert "brand-global" in registry.styles
