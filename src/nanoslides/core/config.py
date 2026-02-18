"""Global user configuration helpers."""

from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import BaseModel, Field

GLOBAL_CONFIG_PATH = Path.home() / ".nanoslides" / "config.toml"
GEMINI_API_KEY_NAME = "GEMINI_API_KEY"
OPENAI_API_KEY_NAME = "OPENAI_API_KEY"
_PROVIDER_DEFAULT_ENGINES = {
    GEMINI_API_KEY_NAME: "nanobanana",
    OPENAI_API_KEY_NAME: "gpt-image",
}


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


def apply_provider_api_key(
    config: GlobalConfig,
    *,
    provider_key: str,
    api_key: str,
) -> None:
    """Store a provider API key and update the default engine."""
    if provider_key not in _PROVIDER_DEFAULT_ENGINES:
        raise ValueError(f"Unsupported provider key: {provider_key}")

    cleaned_api_key = api_key.strip()
    if not cleaned_api_key:
        raise ValueError("API key cannot be empty.")

    config.api_keys[provider_key] = cleaned_api_key
    if provider_key == GEMINI_API_KEY_NAME:
        config.api_keys["nanobanana"] = cleaned_api_key
    if provider_key == OPENAI_API_KEY_NAME:
        config.api_keys["openai"] = cleaned_api_key

    config.default_engine = _PROVIDER_DEFAULT_ENGINES[provider_key]


def get_gemini_api_key(config: GlobalConfig) -> str | None:
    """Resolve a Gemini API key from known config aliases."""
    return config.api_keys.get(GEMINI_API_KEY_NAME) or config.api_keys.get("nanobanana")

