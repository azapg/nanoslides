"""Global user configuration helpers."""

from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import BaseModel, Field

GLOBAL_CONFIG_PATH = Path.home() / ".nanoslides" / "config.toml"


class GlobalConfig(BaseModel):
    """User-level configuration stored in ~/.nanoslides/config.toml."""

    api_keys: dict[str, str] = Field(default_factory=dict)
    default_engine: str = "nanobanana"
    default_output_dir: str = "./slides"


def load_global_config(path: Path = GLOBAL_CONFIG_PATH) -> GlobalConfig:
    """Load global config from TOML, returning defaults when missing."""
    if not path.exists():
        return GlobalConfig()

    contents = path.read_text(encoding="utf-8")
    data = tomllib.loads(contents)
    return GlobalConfig.model_validate(data)


def save_global_config(config: GlobalConfig, path: Path = GLOBAL_CONFIG_PATH) -> None:
    """Persist global config to TOML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'default_engine = "{_escape_toml_string(config.default_engine)}"',
        f'default_output_dir = "{_escape_toml_string(config.default_output_dir)}"',
        "",
        "[api_keys]",
    ]
    for key, value in sorted(config.api_keys.items()):
        lines.append(f'{key} = "{_escape_toml_string(value)}"')

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

