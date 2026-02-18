"""Export command implementation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from nanoslides.core.export import ExportFormat, export_slides

console = Console()


def export_command(
    slides_dir: Path = typer.Option(
        Path("slides"),
        "--slides-dir",
        help="Directory containing generated slide images.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Exported deck output path.",
    ),
    format: ExportFormat = typer.Option(
        ExportFormat.PPTX,
        "--format",
        case_sensitive=False,
        help="Deck format to export.",
    ),
) -> None:
    """Export project slides into a deck file."""
    target_output = output or Path(f"{Path.cwd().name}.{format.value}")
    if not target_output.suffix:
        target_output = target_output.with_suffix(f".{format.value}")

    try:
        saved_path = export_slides(
            slides_dir=slides_dir,
            output_path=target_output,
            format=format,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold green]Exported {slides_dir} to [bold]{saved_path}[/] "
        f"as {format.value.upper()}.[/]"
    )
