"""Nano Banana engine implementation using the Gemini API."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from nanoslides.core.interfaces import SlideEngine, SlideResult
from nanoslides.core.style import ResolvedStyle

_MODEL_MAP = {
    "flash": "gemini-2.5-flash-image",
    "pro": "gemini-3-pro-image-preview",
}
_SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


class NanoBananaModel(str, Enum):
    """Supported Nano Banana model selectors."""

    FLASH = "flash"
    PRO = "pro"

    @property
    def api_model(self) -> str:
        return _MODEL_MAP[self.value]


class ImageAspectRatio(str, Enum):
    """Supported image aspect ratios for generation."""

    RATIO_1_1 = "1:1"
    RATIO_2_3 = "2:3"
    RATIO_3_2 = "3:2"
    RATIO_3_4 = "3:4"
    RATIO_4_3 = "4:3"
    RATIO_4_5 = "4:5"
    RATIO_5_4 = "5:4"
    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
    RATIO_21_9 = "21:9"


class NanoBananaSlideEngine(SlideEngine):
    """SlideEngine backed by Gemini Nano Banana image generation."""

    def __init__(
        self,
        *,
        model: NanoBananaModel = NanoBananaModel.FLASH,
        api_key: str | None = None,
        output_dir: Path | str = "./slides",
    ) -> None:
        self.model = model
        self._api_model = model.api_model
        self._output_dir = Path(output_dir)
        self._client = genai.Client(api_key=_resolve_api_key(api_key))

    def generate(
        self,
        prompt: str,
        style_id: str = "default",
        style: ResolvedStyle | None = None,
        aspect_ratio: ImageAspectRatio = ImageAspectRatio.RATIO_16_9,
    ) -> SlideResult:
        resolved_style = style or _style_from_style_id(style_id)
        revised_prompt = _build_prompt(prompt, resolved_style)
        contents: list[Any] = [revised_prompt]
        contents.extend(_style_reference_parts(resolved_style))

        response = self._client.models.generate_content(
            model=self._api_model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio.value),
            ),
        )
        return self._to_slide_result(
            response,
            revised_prompt=revised_prompt,
            aspect_ratio=aspect_ratio,
        )

    def edit(
        self,
        image: bytes,
        instruction: str,
        style_id: str = "default",
        style: ResolvedStyle | None = None,
        mask: dict[str, Any] | None = None,
    ) -> SlideResult:
        resolved_style = style or _style_from_style_id(style_id)
        revised_prompt = _build_prompt(instruction, resolved_style, is_edit=True)
        contents: list[Any] = [revised_prompt, _bytes_part(image)]
        contents.extend(_style_reference_parts(resolved_style))
        response = self._client.models.generate_content(
            model=self._api_model,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        result = self._to_slide_result(response, revised_prompt=revised_prompt)
        if mask is not None:
            result.metadata["mask"] = mask
        return result

    def _to_slide_result(
        self,
        response: Any,
        *,
        revised_prompt: str,
        aspect_ratio: ImageAspectRatio | None = None,
    ) -> SlideResult:
        text_parts: list[str] = []
        image_bytes: bytes | None = None
        image_mime_type = "image/png"

        for part in _response_parts(response):
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)

            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and image_bytes is None:
                image_bytes = _inline_data_bytes(inline_data)
                image_mime_type = getattr(inline_data, "mime_type", "image/png")

        if image_bytes is None:
            raise RuntimeError("NanoBanana returned no image in the response.")

        local_path = self._persist_image(image_bytes, image_mime_type)
        metadata: dict[str, Any] = {
            "engine": "nanobanana",
            "model_selector": self.model.value,
            "model": self._api_model,
            "mime_type": image_mime_type,
        }
        if aspect_ratio is not None:
            metadata["aspect_ratio"] = aspect_ratio.value
        if text_parts:
            metadata["response_text"] = "\n".join(text_parts)

        return SlideResult(
            image_url=local_path.resolve().as_uri(),
            local_path=local_path,
            revised_prompt=revised_prompt,
            metadata=metadata,
        )

    def _persist_image(self, image_bytes: bytes, mime_type: str) -> Path:
        extension = _file_extension_for_mime_type(mime_type)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        file_name = (
            f"slide-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.{extension}"
        )
        local_path = self._output_dir / file_name
        local_path.write_bytes(image_bytes)
        return local_path


def _resolve_api_key(api_key: str | None) -> str:
    resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if resolved_key:
        return resolved_key
    raise ValueError(
        "Missing Gemini API key. Set api_keys.nanobanana in config.toml or define "
        "GEMINI_API_KEY."
    )


def _build_prompt(
    prompt: str,
    style: ResolvedStyle | None = None,
    *,
    is_edit: bool = False,
) -> str:
    if style is None and not is_edit:
        return prompt

    sections: list[str] = []
    if style is not None and style.base_prompt:
        sections.append(style.base_prompt)
    sections.append(prompt)
    if style is not None and style.reference_images:
        sections.append(
            f"{len(style.reference_images)} style reference image(s) are attached. "
            "Use them only as visual style guidance for palette, tone, and texture."
        )
    if style is not None and style.reference_comments:
        comments = "\n".join(f"- {comment}" for comment in style.reference_comments)
        sections.append(f"Style references:\n{comments}")
    if style is not None and style.negative_prompt:
        sections.append(f"Avoid:\n{style.negative_prompt}")
    if style is not None and style.style_id:
        sections.append(f"Apply global style preset: {style.style_id}")
    if is_edit:
        sections.append(
            "Do not modify anything else except what is specified by the user."
        )

    return "\n\n".join(section for section in sections if section)


def _style_reference_parts(style: ResolvedStyle | None) -> list[types.Part]:
    if style is None:
        return []

    parts: list[types.Part] = []
    for raw_path in style.reference_images:
        path = Path(raw_path).expanduser()
        if not path.exists():
            raise ValueError(f"Style reference image not found: {path}")
        parts.append(_bytes_part(path.read_bytes()))
    return parts


def _style_from_style_id(style_id: str) -> ResolvedStyle | None:
    normalized = style_id.strip()
    if not normalized or normalized == "default":
        return None
    return ResolvedStyle(style_id=normalized)


def _bytes_part(image_bytes: bytes) -> types.Part:
    return types.Part.from_bytes(data=image_bytes, mime_type="image/png")


def _response_parts(response: Any) -> list[Any]:
    direct_parts = getattr(response, "parts", None)
    if direct_parts is not None:
        return list(direct_parts)

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []

    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    return list(parts)


def _inline_data_bytes(inline_data: Any) -> bytes:
    data = getattr(inline_data, "data", b"")
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        try:
            return base64.b64decode(data)
        except ValueError:
            return data.encode("utf-8")
    raise TypeError("Unsupported inline image payload type.")


def _file_extension_for_mime_type(mime_type: str) -> str:
    normalized = mime_type.lower()
    if normalized not in _SUPPORTED_IMAGE_MIME_TYPES:
        return "png"
    if normalized == "image/jpeg":
        return "jpg"
    return normalized.split("/", maxsplit=1)[1]

