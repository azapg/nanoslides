"""Core primitives for nanoslides."""

from nanoslides.core.config import GLOBAL_CONFIG_PATH, GlobalConfig, load_global_config
from nanoslides.core.interfaces import SlideEngine, SlideResult
from nanoslides.core.project import PROJECT_STATE_FILE, ProjectState, SlideEntry
from nanoslides.core.style import (
    GLOBAL_STYLES_PATH,
    PROJECT_STYLE_PATH,
    GlobalStylesConfig,
    ProjectStyleConfig,
    ResolvedStyle,
    StyleDefinition,
    load_global_styles,
    load_project_style,
    resolve_style_context,
)

__all__ = [
    "GLOBAL_CONFIG_PATH",
    "GLOBAL_STYLES_PATH",
    "PROJECT_STATE_FILE",
    "PROJECT_STYLE_PATH",
    "GlobalConfig",
    "GlobalStylesConfig",
    "ProjectState",
    "ProjectStyleConfig",
    "ResolvedStyle",
    "SlideEngine",
    "SlideEntry",
    "SlideResult",
    "StyleDefinition",
    "load_global_styles",
    "load_global_config",
    "load_project_style",
    "resolve_style_context",
]

