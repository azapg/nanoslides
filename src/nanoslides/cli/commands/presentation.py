"""Presentation command implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any

from google import genai
from google.genai import types
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from nanoslides.cli.image_store import persist_slide_result
from nanoslides.cli.reference_files import (
    add_reference_file_metadata,
    inject_reference_file_context,
    resolve_reference_files,
)
from nanoslides.core.config import GlobalConfig, get_gemini_api_key, load_global_config
from nanoslides.core.presentation import Presentation
from nanoslides.core.provider_errors import is_service_unavailable_error
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    load_project_state,
    save_project_state,
)
from nanoslides.core.style import (
    ResolvedStyle,
    load_project_style,
    merge_style_references,
    resolve_style_context,
)
from nanoslides.engines.nanobanana import (
    ImageAspectRatio,
    NanoBananaModel,
    NanoBananaSlideEngine,
)
from pydantic import BaseModel, Field

console = Console()
_PLANNER_PRIMARY_MODEL = "gemini-3-pro-preview"
_PLANNER_FALLBACK_MODEL = "gemini-2.5-pro"


class DetailLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IllustrationLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlannedSlide(BaseModel):
    """One slide planned by Gemini 3 Pro."""

    title: str
    prompt: str


class PresentationPlan(BaseModel):
    """Deck-level planning output from Gemini 3 Pro."""

    deck_title: str
    planning_summary: str = ""
    inferred_style_base_prompt: str = ""
    inferred_style_negative_prompt: str = ""
    slides: list[PlannedSlide] = Field(default_factory=list, min_length=1, max_length=40)


@dataclass(frozen=True)
class PresentationRequest:
    prompt: str
    audience: str | None
    use_case: str | None
    duration_minutes: int | None
    slide_count: int | None
    detail_level: str
    illustration_level: str
    language: str
    style_id: str | None
    references: list[Path]
    reference_files: list[Path]


def presentation_command(
    ctx: typer.Context,
    prompt: str | None = typer.Argument(
        None,
        help="Single prompt describing the full presentation objective.",
    ),
    style_id: str | None = typer.Option(
        None,
        "--style-id",
        "--style",
        help="Style preset ID. If omitted, project/global style context is used when present.",
    ),
    references: list[Path] | None = typer.Option(
        None,
        "--references",
        help="Reference image paths (repeat --references for multiple files).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    reference_file: list[Path] | None = typer.Option(
        None,
        "--reference-file",
        help="Text file path used as context (repeat --reference-file for multiple files).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory where generated images are saved.",
    ),
    model: NanoBananaModel | None = typer.Option(
        None,
        "--model",
        case_sensitive=False,
        help="NanoBanana model for slide generation.",
    ),
    aspect_ratio: ImageAspectRatio = typer.Option(
        ImageAspectRatio.RATIO_16_9,
        "--aspect-ratio",
        case_sensitive=False,
        help="Deck slide image aspect ratio.",
    ),
    audience: str | None = typer.Option(
        None,
        "--audience",
        help="Intended audience (e.g., executives, students, engineers).",
    ),
    use_case: str | None = typer.Option(
        None,
        "--use-case",
        help="Where/how this deck will be used (pitch, class, demo, etc.).",
    ),
    duration_minutes: int | None = typer.Option(
        None,
        "--duration-minutes",
        min=1,
        help="Estimated presentation length in minutes.",
    ),
    slide_count: int | None = typer.Option(
        None,
        "--slide-count",
        min=1,
        max=40,
        help="Target number of slides.",
    ),
    detail_level: DetailLevel = typer.Option(
        DetailLevel.MEDIUM,
        "--detail-level",
        case_sensitive=False,
        help="How technical/detailed slide content should be: low, medium, high.",
    ),
    illustration_level: IllustrationLevel = typer.Option(
        IllustrationLevel.MEDIUM,
        "--illustration-level",
        case_sensitive=False,
        help="How illustration-heavy deck visuals should be: low, medium, high.",
    ),
    language: str = typer.Option(
        "en",
        "--language",
        help="Language for deck content and prompts.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Disable guided prompts and use only provided arguments/options.",
    ),
) -> None:
    """Generate an entire presentation deck from one high-level prompt."""
    try:
        request = PresentationRequest(
            prompt=prompt or "",
            audience=audience,
            use_case=use_case,
            duration_minutes=duration_minutes,
            slide_count=slide_count,
            detail_level=detail_level.value,
            illustration_level=illustration_level.value,
            language=language.strip() or "en",
            style_id=style_id,
            references=list(references or []),
            reference_files=resolve_reference_files(reference_file),
        )
        if not no_interactive and sys.stdin.isatty() and not request.prompt:
            request = _collect_interactive_inputs(request)
        if not request.prompt.strip():
            console.print("[bold red]Presentation prompt is required.[/]")
            raise typer.Exit(code=1)
        _validate_level("detail-level", request.detail_level)
        _validate_level("illustration-level", request.illustration_level)
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    config = _resolve_config(ctx)
    api_key = get_gemini_api_key(config)
    if not api_key:
        console.print("[bold red]Missing Gemini API key. Run `nanoslides setup` first.[/]")
        raise typer.Exit(code=1)
    target_output_dir = output_dir or Path(config.default_output_dir)
    effective_model = model or NanoBananaModel.PRO

    resolved_style = resolve_style_context(style_id=request.style_id)
    has_existing_style = _has_resolved_style_context(resolved_style)
    merged_style = merge_style_references(resolved_style, request.references)

    try:
        with console.status("[bold cyan]Planning presentation with Gemini 3 Pro...[/]"):
            plan, planner_model = _plan_presentation(
                api_key=api_key,
                request=request,
                style=merged_style,
                has_existing_style=has_existing_style,
            )
    except RuntimeError as exc:
        console.print(f"[bold red]Presentation planning failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    effective_style = _apply_inferred_style_if_needed(
        style=merged_style,
        plan=plan,
        has_existing_style=has_existing_style,
    )
    _print_plan_summary(plan, request, effective_style)

    try:
        generated_rows = _generate_planned_slides(
            plan=plan,
            style=effective_style,
            model=effective_model,
            api_key=api_key,
            aspect_ratio=aspect_ratio,
            output_dir=target_output_dir,
            reference_files=request.reference_files,
        )
    except (ValueError, RuntimeError) as exc:
        console.print(f"[bold red]Presentation generation failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    summary = Table(title="Generated deck")
    summary.add_column("#", justify="right")
    summary.add_column("Slide")
    summary.add_column("ID")
    summary.add_column("Path")
    summary.add_column("Equivalent generate call")
    for row in generated_rows:
        summary.add_row(
            str(row["index"]),
            str(row["title"]),
            str(row["slide_id"] or "-"),
            str(row["path"]),
            str(row["generate_command"]),
        )
    console.print(summary)
    console.print(
        Panel.fit(
            f"[bold green]Presentation generated[/]\n"
            f"Slides: [bold]{len(generated_rows)}[/]\n"
            f"Planner: [bold]{planner_model}[/]\n"
            f"Generator model: [bold]{effective_model.value}[/]\n"
            f"Reference files: [bold]{len(request.reference_files)}[/]\n"
            f"Output dir: [bold]{target_output_dir.resolve()}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _collect_interactive_inputs(request: PresentationRequest) -> PresentationRequest:
    console.print(
        Panel.fit(
            "[bold cyan]Guided presentation creation[/]\nWe'll define the full deck step by step.",
            title="nanoslides",
            border_style="cyan",
        )
    )
    prompt = Prompt.ask("1) Presentation prompt")
    audience = _prompt_optional("2) Target audience (optional)", request.audience)
    use_case = _prompt_optional("3) Use case (optional)", request.use_case)
    duration_minutes = _prompt_optional_int(
        "4) Duration in minutes (optional)",
        request.duration_minutes,
        minimum=1,
    )
    slide_count = _prompt_optional_int(
        "5) Target slide count (optional)",
        request.slide_count,
        minimum=1,
    )
    detail_level = Prompt.ask(
        "6) Detail level",
        choices=[level.value for level in DetailLevel],
        default=request.detail_level,
    )
    illustration_level = Prompt.ask(
        "7) Illustration level",
        choices=[level.value for level in IllustrationLevel],
        default=request.illustration_level,
    )
    language = Prompt.ask("8) Language", default=request.language).strip() or "en"

    project_style = load_project_style()
    default_style = request.style_id
    if default_style is None and project_style is not None:
        default_style = project_style.style_id or ""
    style_id = _prompt_optional("9) Style ID (optional)", default_style)

    refs_default = ", ".join(str(path) for path in request.references)
    raw_refs = Prompt.ask(
        "10) Reference image paths (optional, comma-separated)",
        default=refs_default,
    ).strip()
    references = _parse_reference_paths(raw_refs, item_label="Reference image")
    raw_reference_files = Prompt.ask(
        "11) Reference text file paths (optional, comma-separated)",
        default=", ".join(str(path) for path in request.reference_files),
    ).strip()
    reference_files = _parse_reference_paths(
        raw_reference_files,
        item_label="Reference file",
    )

    return PresentationRequest(
        prompt=prompt.strip(),
        audience=audience,
        use_case=use_case,
        duration_minutes=duration_minutes,
        slide_count=slide_count,
        detail_level=detail_level,
        illustration_level=illustration_level,
        language=language,
        style_id=style_id,
        references=references,
        reference_files=resolve_reference_files(reference_files),
    )


def _prompt_optional(label: str, default: str | None) -> str | None:
    value = Prompt.ask(label, default=default or "").strip()
    return value or None


def _prompt_optional_int(label: str, default: int | None, *, minimum: int) -> int | None:
    while True:
        value = Prompt.ask(label, default=str(default) if default is not None else "").strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError:
            console.print("[bold red]Enter a valid integer value.[/]")
            continue
        if parsed < minimum:
            console.print(f"[bold red]Value must be at least {minimum}.[/]")
            continue
        return parsed


def _parse_reference_paths(raw_paths: str, *, item_label: str) -> list[Path]:
    if not raw_paths.strip():
        return []
    references: list[Path] = []
    seen: set[str] = set()
    for token in raw_paths.split(","):
        path = Path(token.strip()).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"{item_label} not found: {path}")
        normalized = str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        references.append(path)
    return references


def _validate_level(name: str, value: str) -> None:
    if value not in {level.value for level in DetailLevel}:
        raise ValueError(f"{name} must be one of: low, medium, high.")


def _plan_presentation(
    *,
    api_key: str,
    request: PresentationRequest,
    style: ResolvedStyle,
    has_existing_style: bool,
) -> tuple[PresentationPlan, str]:
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            api_version="v1alpha",
            timeout=120.0,
            retry_options=types.HttpRetryOptions(attempts=2),
        ),
    )
    prompt = _build_planner_prompt(
        request=request,
        style=style,
        has_existing_style=has_existing_style,
    )
    prompt = inject_reference_file_context(prompt, request.reference_files)
    contents: list[Any] = [prompt]
    contents.extend(_planner_reference_parts(style.reference_images))
    planner_models = [_PLANNER_PRIMARY_MODEL, _PLANNER_FALLBACK_MODEL]
    response = None
    planner_model_used = _PLANNER_PRIMARY_MODEL
    last_error: BaseException | None = None
    for index, planner_model in enumerate(planner_models):
        try:
            response = client.models.generate_content(
                model=planner_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    response_mime_type="application/json",
                    response_json_schema=PresentationPlan.model_json_schema(),
                    thinking_config=types.ThinkingConfig(thinking_level="high"),
                ),
            )
            planner_model_used = planner_model
            break
        except Exception as exc:
            last_error = exc
            should_retry = (
                index < len(planner_models) - 1 and is_service_unavailable_error(exc)
            )
            if not should_retry:
                raise
    if response is None:
        if last_error is not None:
            raise last_error
        raise RuntimeError("Presentation planner failed before receiving a response.")
    payload = _parse_json_response(response)
    plan = PresentationPlan.model_validate(payload)
    if request.slide_count is not None and len(plan.slides) != request.slide_count:
        raise RuntimeError(
            f"Planner returned {len(plan.slides)} slides but slide-count={request.slide_count}."
        )
    return plan, planner_model_used


def _build_planner_prompt(
    *,
    request: PresentationRequest,
    style: ResolvedStyle,
    has_existing_style: bool,
) -> str:
    style_context = "none"
    if has_existing_style:
        style_context = (
            f"style_id={style.style_id or 'project/default'}\n"
            f"base_prompt={style.base_prompt or '(empty)'}\n"
            f"negative_prompt={style.negative_prompt or '(empty)'}\n"
            f"reference_comments={style.reference_comments or []}\n"
            f"reference_images_count={len(style.reference_images)}"
        )
    return (
        "You are orchestrating an entire slide deck for nanoslides.\n"
        "Return strict JSON that matches the provided schema.\n"
        "For each planned slide, produce a strong standalone image prompt suitable for "
        "a single `nanoslides generate` call.\n"
        f"Deck prompt: {request.prompt}\n"
        f"Audience: {request.audience or 'general'}\n"
        f"Use case: {request.use_case or 'general presentation'}\n"
        f"Duration minutes: {request.duration_minutes or 'not specified'}\n"
        f"Requested slide count: {request.slide_count or 'choose sensible count'}\n"
        f"Detail level: {request.detail_level}\n"
        f"Illustration level: {request.illustration_level}\n"
        f"Language: {request.language}\n"
        f"Reference files count: {len(request.reference_files)}\n"
        f"Existing style context:\n{style_context}\n"
        "Rules:\n"
        "1) Keep slide sequence coherent and presentation-ready.\n"
        "2) Each slide.prompt must describe visual content + text intent for the slide.\n"
        "3) If existing style context is present, do not infer a new style and keep "
        "inferred_style_base_prompt and inferred_style_negative_prompt empty strings.\n"
        "4) If no style context is present, infer a reusable style by filling "
        "inferred_style_base_prompt and optionally inferred_style_negative_prompt.\n"
        "5) If requested slide count is specified, return exactly that many slides.\n"
    )


def _planner_reference_parts(reference_paths: list[str]) -> list[types.Part]:
    parts: list[types.Part] = []
    for raw_path in reference_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"Style reference image not found: {path}")
        mime_type, _ = mimetypes.guess_type(str(path))
        resolved_mime_type = mime_type or "image/png"
        parts.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=resolved_mime_type))
    return parts


def _parse_json_response(response: Any) -> dict[str, Any]:
    raw_text = getattr(response, "text", None)
    if not raw_text:
        raw_text = "\n".join(_response_text_parts(response))
    if not raw_text:
        raise RuntimeError("Gemini planner returned no text output.")
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json") :].strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini planner returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Gemini planner JSON payload must be an object.")
    return payload


def _response_text_parts(response: Any) -> list[str]:
    text_parts: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(str(text))
    return text_parts


def _has_resolved_style_context(style: ResolvedStyle) -> bool:
    return bool(
        style.style_id
        or style.base_prompt.strip()
        or style.negative_prompt.strip()
        or style.reference_images
        or style.reference_comments
    )


def _apply_inferred_style_if_needed(
    *,
    style: ResolvedStyle,
    plan: PresentationPlan,
    has_existing_style: bool,
) -> ResolvedStyle:
    if has_existing_style:
        return style
    inferred_base = plan.inferred_style_base_prompt.strip()
    inferred_negative = plan.inferred_style_negative_prompt.strip()
    if not inferred_base and not inferred_negative:
        return style
    return style.model_copy(
        update={
            "base_prompt": inferred_base,
            "negative_prompt": inferred_negative,
        }
    )


def _print_plan_summary(
    plan: PresentationPlan,
    request: PresentationRequest,
    style: ResolvedStyle,
) -> None:
    table = Table(title=f"Planned deck: {plan.deck_title}")
    table.add_column("#", justify="right")
    table.add_column("Slide")
    table.add_column("Prompt preview")
    for index, slide in enumerate(plan.slides, start=1):
        table.add_row(str(index), slide.title, _truncate(slide.prompt))
    console.print(table)
    style_label = style.style_id or "inferred/default"
    console.print(
        Panel.fit(
            f"Audience: [bold]{request.audience or 'general'}[/]\n"
            f"Use case: [bold]{request.use_case or 'general'}[/]\n"
            f"Style: [bold]{style_label}[/]\n"
            f"Summary: {plan.planning_summary or '(none)'}",
            title="Plan summary",
            border_style="cyan",
        )
    )


def _truncate(value: str, *, length: int = 96) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= length:
        return cleaned
    return cleaned[: length - 3] + "..."


def _generate_planned_slides(
    *,
    plan: PresentationPlan,
    style: ResolvedStyle,
    model: NanoBananaModel,
    api_key: str,
    aspect_ratio: ImageAspectRatio,
    output_dir: Path,
    reference_files: list[Path],
) -> list[dict[str, object]]:
    engine = NanoBananaSlideEngine(model=model, api_key=api_key)
    presentation: Presentation | None = None
    if PROJECT_STATE_FILE.exists():
        presentation = Presentation.from_project_state(load_project_state())

    generated_rows: list[dict[str, object]] = []
    for index, slide in enumerate(plan.slides, start=1):
        with console.status(
            f"[bold cyan]Generating slide {index}/{len(plan.slides)}: {slide.title}[/]"
        ):
            result = engine.generate(
                prompt=slide.prompt,
                style=style,
                aspect_ratio=aspect_ratio,
            )
        persisted_path = persist_slide_result(
            result,
            output_dir=output_dir,
            file_prefix=f"slide-{index:02d}",
        )
        resolved_path = persisted_path
        slide_id: str | None = None
        if presentation is not None:
            entry = presentation.add_slide(
                prompt=result.revised_prompt,
                image_path=None,
                metadata=add_reference_file_metadata(
                    {
                        **result.metadata,
                        "deck_title": plan.deck_title,
                        "deck_slide_index": index,
                        "deck_slide_title": slide.title,
                    },
                    reference_files,
                ),
            )
            renamed_path = _rename_slide_file(persisted_path, entry.order, entry.id)
            entry.image_path = str(renamed_path) if renamed_path else None
            resolved_path = renamed_path or persisted_path
            slide_id = entry.id

        generated_rows.append(
            {
                "index": index,
                "title": slide.title,
                "slide_id": slide_id,
                "path": str(resolved_path),
                "generate_command": _generate_command_preview(
                    prompt=slide.prompt,
                    style=style,
                    aspect_ratio=aspect_ratio,
                ),
            }
        )

    if presentation is not None:
        save_project_state(presentation.to_project_state())
    return generated_rows


def _generate_command_preview(
    *,
    prompt: str,
    style: ResolvedStyle,
    aspect_ratio: ImageAspectRatio,
) -> str:
    escaped_prompt = prompt.replace('"', '\\"')
    command = f'nanoslides generate "{escaped_prompt}" --aspect-ratio {aspect_ratio.value}'
    if style.style_id:
        command = f"{command} --style-id {style.style_id}"
    return command


def _rename_slide_file(local_path: Path | None, order: int, slide_id: str) -> Path | None:
    if local_path is None or not local_path.exists():
        return local_path
    suffix = local_path.suffix
    target = local_path.with_name(f"{order}_{slide_id}{suffix}")
    if target == local_path:
        return local_path
    if target.exists():
        counter = 2
        while True:
            candidate = local_path.with_name(f"{order}_{slide_id}-{counter}{suffix}")
            if not candidate.exists():
                target = candidate
                break
            counter += 1
    local_path.rename(target)
    return target


def _resolve_config(ctx: typer.Context) -> GlobalConfig:
    if ctx.obj and isinstance(ctx.obj.get("config"), GlobalConfig):
        return ctx.obj["config"]
    return load_global_config()

