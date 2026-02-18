"""Setup command for configuring API keys."""

from __future__ import annotations

from pathlib import Path

import typer
from click import Choice
from rich.console import Console

from nanoslides.core.config import (
    GEMINI_API_KEY_NAME,
    GLOBAL_CONFIG_PATH,
    OPENAI_API_KEY_NAME,
    apply_provider_api_key,
    load_global_config,
    save_global_config,
)

console = Console()
_PROVIDER_KEYS = [GEMINI_API_KEY_NAME, OPENAI_API_KEY_NAME]


def setup_command(
    provider: str = typer.Option(
        GEMINI_API_KEY_NAME,
        "--provider",
        click_type=Choice(_PROVIDER_KEYS, case_sensitive=False),
        prompt="Select API key to configure",
        show_choices=True,
        help="Provider API key entry to configure.",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Provider API key value (prompted if omitted).",
        hide_input=True,
    ),
    config_path: Path = typer.Option(
        GLOBAL_CONFIG_PATH,
        "--config-path",
        hidden=True,
    ),
) -> None:
    """Configure provider API keys and default engine."""
    provider_key = provider.upper()
    if provider_key not in _PROVIDER_KEYS:
        console.print(f"[bold red]Unsupported provider key: {provider}[/]")
        raise typer.Exit(code=1)

    key_value = api_key or typer.prompt(
        f"Enter {provider_key}",
        hide_input=True,
        confirmation_prompt=True,
    )
    config = load_global_config(path=config_path)
    try:
        apply_provider_api_key(
            config,
            provider_key=provider_key,
            api_key=key_value,
        )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    save_global_config(config, path=config_path)
    console.print(
        f"[bold green]Saved {provider_key} to {config_path}.[/]\n"
        f"Default engine: [bold]{config.default_engine}[/]"
    )

