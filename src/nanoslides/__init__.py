"""Nanoslides: A library and CLI for generating AI-powered presentation slides."""

__version__ = "0.1.0"

from nanoslides.core.interfaces import SlideEngine, SlideResult
from nanoslides.core.project import ProjectState, SlideEntry, load_project_state, save_project_state
from nanoslides.core.style import ResolvedStyle, ProjectStyleConfig, load_project_style
from nanoslides.engines.nanobanana import NanoBananaSlideEngine, NanoBananaModel, ImageAspectRatio

__all__ = [
    "SlideEngine",
    "SlideResult",
    "ProjectState",
    "SlideEntry",
    "load_project_state",
    "save_project_state",
    "ResolvedStyle",
    "ProjectStyleConfig",
    "load_project_style",
    "NanoBananaSlideEngine",
    "NanoBananaModel",
    "ImageAspectRatio",
]
