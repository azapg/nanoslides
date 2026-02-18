"""Core primitives for nanoslides."""

from nanoslides.core.config import GLOBAL_CONFIG_PATH, GlobalConfig, load_global_config
from nanoslides.core.interfaces import SlideEngine, SlideResult
from nanoslides.core.project import PROJECT_STATE_FILE, ProjectState, SlideEntry

__all__ = [
    "GLOBAL_CONFIG_PATH",
    "PROJECT_STATE_FILE",
    "GlobalConfig",
    "ProjectState",
    "SlideEngine",
    "SlideEntry",
    "SlideResult",
    "load_global_config",
]

