"""Style command group."""

from pathlib import Path

import typer
from rich.console import Console

from nanoslides.core.style import (
    GLOBAL_STYLES_PATH,
    PROJECT_STYLE_PATH,
    ProjectStyleConfig,
    StyleDefinition,
    load_global_styles,
    save_global_styles,
    save_project_style,
)

style_app = typer.Typer(help="Style management commands.")
console = Console()


@style_app.command("create")
def style_create_command(
    style_id: str | None = typer.Argument(
        None,
        help="Style ID (required with --global, optional for project style).",
    ),
    base_prompt: str = typer.Option(
        "",
        "--base-prompt",
        help="Base prompt included in every generation/edit call.",
    ),
    negative_prompt: str = typer.Option(
        "",
        "--negative-prompt",
        help="Negative prompt included in every generation/edit call.",
    ),
    reference_image: list[Path] | None = typer.Option(
        None,
        "--reference-image",
        help="Reference image path (repeat --reference-image for multiple files).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    reference_comment: list[str] | None = typer.Option(
        None,
        "--reference-comment",
        help="Reference comment (repeat --reference-comment for multiple entries).",
    ),
    global_scope: bool = typer.Option(
        False,
        "--global",
        help="Save style to ~/.nanoslides/styles.json instead of ./style.json.",
    ),
) -> None:
    """Create/update a project style or a global style preset."""
    reference_images = [str(path) for path in (reference_image or [])]
    if global_scope:
        reference_images = [str(Path(path).resolve()) for path in reference_images]

    style = StyleDefinition(
        base_prompt=base_prompt.strip(),
        negative_prompt=negative_prompt.strip(),
        reference_images=reference_images,
        reference_comments=[
            comment.strip() for comment in (reference_comment or []) if comment.strip()
        ],
    )

    if global_scope:
        if not style_id:
            console.print("[bold red]A style_id is required when using --global.[/]")
            raise typer.Exit(code=1)
        styles = load_global_styles()
        styles.styles[style_id] = style
        save_global_styles(styles)
        console.print(
            f"[bold green]Saved global style '{style_id}' to {GLOBAL_STYLES_PATH}.[/]"
        )
        return

    project_style = ProjectStyleConfig(
        style_id=style_id,
        base_prompt=style.base_prompt,
        negative_prompt=style.negative_prompt,
        reference_images=style.reference_images,
        reference_comments=style.reference_comments,
    )
    save_project_style(project_style)
    console.print(f"[bold green]Saved project style to {PROJECT_STYLE_PATH}.[/]")


@style_app.command("steal")
def style_steal_command() -> None:
    """Placeholder command."""
    console.print("[yellow]Coming Soon: style steal command.[/]")

