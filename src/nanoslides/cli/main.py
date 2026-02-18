"""Main Typer application definition."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from nanoslides.cli.commands.edit import edit_command
from nanoslides.cli.commands.generate import generate_command
from nanoslides.cli.commands.init import init_command
from nanoslides.cli.commands.style import style_app
from nanoslides.core.config import load_global_config
from nanoslides.utils.logger import configure_logging

app = typer.Typer(help="Generate and manage AI-powered presentation slides.")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit logs in a JSON-friendly format."
    ),
) -> None:
    """Configure the runtime environment for all commands."""
    load_dotenv()
    configure_logging(verbose=verbose, json_output=json_output)
    ctx.obj = ctx.obj or {}
    ctx.obj["config"] = load_global_config()


app.command("init")(init_command)
app.command("generate")(generate_command)
app.command("edit")(edit_command)
app.add_typer(style_app, name="style")


def run() -> None:
    """CLI entrypoint used by console scripts."""
    app()

