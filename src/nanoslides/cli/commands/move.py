"""Move command implementation."""

from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nanoslides.core.project import PROJECT_STATE_FILE, SlideEntry, load_project_state, save_project_state

console = Console()


def move_command(
    slide_id: str = typer.Argument(..., help=f"Slide ID from {PROJECT_STATE_FILE} to move."),
    new_pos: int = typer.Argument(..., help="New 1-based position for the slide."),
) -> None:
    """Move a slide to a new position in the local project state."""
    if new_pos < 1:
        console.print("[bold red]new-pos must be at least 1.[/]")
        raise typer.Exit(code=1)

    try:
        project = load_project_state()
    except FileNotFoundError as exc:
        console.print(
            f"[bold red]{PROJECT_STATE_FILE} not found. Run `nanoslides init` first.[/]"
        )
        raise typer.Exit(code=1) from exc

    ordered_slides = sorted(project.slides, key=lambda slide: (slide.order, slide.id))
    if not ordered_slides:
        console.print("[bold red]No slides found in project.[/]")
        raise typer.Exit(code=1)
    if new_pos > len(ordered_slides):
        console.print(
            f"[bold red]new-pos must be between 1 and {len(ordered_slides)}.[/]"
        )
        raise typer.Exit(code=1)

    current_index = next(
        (index for index, slide in enumerate(ordered_slides) if slide.id == slide_id),
        None,
    )
    if current_index is None:
        console.print(f"[bold red]Slide '{slide_id}' was not found in {PROJECT_STATE_FILE}.[/]")
        raise typer.Exit(code=1)

    current_pos = current_index + 1
    if current_pos == new_pos:
        console.print(f"[yellow]Slide '{slide_id}' is already at position {new_pos}.[/]")
        console.print(_slides_table(ordered_slides))
        return

    moving_slide = ordered_slides.pop(current_index)
    ordered_slides.insert(new_pos - 1, moving_slide)
    _reindex_slide_orders(ordered_slides)
    project.slides = ordered_slides
    save_project_state(project)

    console.print(
        Panel.fit(
            f"[bold green]Moved slide[/]\n"
            f"ID: [bold]{slide_id}[/]\n"
            f"From: [bold]{current_pos}[/]\n"
            f"To: [bold]{new_pos}[/]",
            title="nanoslides",
            border_style="green",
        )
    )
    console.print(_slides_table(project.slides))


def _reindex_slide_orders(slides: list[SlideEntry]) -> None:
    for index, slide in enumerate(slides, start=1):
        slide.order = index


def _slides_table(slides: list[SlideEntry]) -> Table:
    table = Table(title="Updated slide order", box=box.ROUNDED, header_style="bold")
    table.add_column("Order", justify="right")
    table.add_column("ID")
    table.add_column("Path")
    for slide in slides:
        table.add_row(str(slide.order), slide.id, slide.image_path or "-")
    return table
