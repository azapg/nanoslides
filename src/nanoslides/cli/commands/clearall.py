"""Clear all slides command implementation."""

from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from nanoslides.core.presentation import Presentation
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    SlideEntry,
    load_project_state,
    save_project_state,
)

console = Console()


def clearall_command() -> None:
    """Remove every slide from the local project state after confirmation."""
    try:
        presentation = Presentation.from_project_state(load_project_state())
    except FileNotFoundError as exc:
        console.print(
            f"[bold red]{PROJECT_STATE_FILE} not found. Run `nanoslides init` first.[/]"
        )
        raise typer.Exit(code=1) from exc

    ordered_slides = presentation.ordered_slides
    if not ordered_slides:
        console.print("[yellow]No slides found in project.[/]")
        return

    console.print(_slides_table(ordered_slides))
    should_delete = Confirm.ask(
        f"Delete all {len(ordered_slides)} slides from {PROJECT_STATE_FILE}? "
        "This cannot be undone.",
        default=False,
    )
    if not should_delete:
        console.print("[yellow]Cancelled. No slides were deleted.[/]")
        return

    presentation.slides = []
    save_project_state(presentation.to_project_state())

    console.print(
        Panel.fit(
            f"[bold green]Cleared all slides[/]\n"
            f"Deleted: [bold]{len(ordered_slides)}[/]\n"
            f"Project file: [bold]{PROJECT_STATE_FILE}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _slides_table(slides: list[SlideEntry]) -> Table:
    table = Table(title="Slides to delete", box=box.ROUNDED, header_style="bold")
    table.add_column("Order", justify="right")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Path")
    for slide in slides:
        table.add_row(
            str(slide.order),
            slide.id,
            "draft" if slide.is_draft else "main",
            slide.image_path or "-",
        )
    return table
