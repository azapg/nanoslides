# nanoslides

`nanoslides` is a Python library and CLI designed to generate high-quality presentation slides using AI image models. 

Unlike tools that prioritize one-off generations, `nanoslides` is built to be used **programmatically**. It focuses on maintaining visual consistency across an entire deck through a robust styling system and project-state management.

## Key Concepts

- **Library First**: Designed to be integrated into web apps, automated agents, and custom scripts.
- **Stateless Generation**: The core engines can generate multiple variations without forcing side effects on your project state.
- **Consistent Styling**: Define global or project-specific styles (base prompts, negative prompts, and reference images) to ensure every slide feels part of the same deck.
- **CLI for Humans & Agents**: A powerful interface for quick iterations and for AI agents like OpenClaw-based bots.

## Installation

```bash
pip install nanoslides
```

## Programmatic Usage

You can use `nanoslides` directly in your Python projects. This is the recommended way for building applications that need to generate multiple variations before committing them to a presentation.

```python
from pathlib import Path
from nanoslides.engines.nanobanana import NanoBananaSlideEngine, NanoBananaModel
from nanoslides.core.style import ResolvedStyle

# 1. Initialize the engine
engine = NanoBananaSlideEngine(
    model=NanoBananaModel.PRO,
    api_key="YOUR_GEMINI_API_KEY",
    output_dir=Path("./my_slides")
)

# 2. Define a style (optional)
style = ResolvedStyle(
    base_prompt="Minimalist corporate design, flat vectors, blue and white palette.",
    reference_images=["./assets/brand_guide_style.png"]
)

# 3. Generate variations
# The library doesn't update slides.json automatically; the client handles the state.
result = engine.generate(
    prompt="A slide showing a growth chart for Q4 revenue",
    style=style
)

print(f"Slide saved to: {result.local_path}")
print(f"Revised prompt used: {result.revised_prompt}")
```

## CLI Usage

The CLI is perfect for managing projects and providing a guided workflow.

### Quick Start
```bash
# Setup your API keys
nanoslides setup

# Initialize a new presentation project
nanoslides init MyPresentation
cd MyPresentation

# Create a consistent style for the project
nanoslides styles create --slides-base-reference ./branding.png

# Generate a slide
nanoslides generate "Introduction to AI in healthcare"
```

### Advanced CLI Commands
- `nanoslides styles steal ./image.png`: Automatically infer style parameters from an existing image using Gemini Vision.
- `nanoslides styles generate "clean Swiss-style layouts with muted blue accents" --reference-image ./brand.png`: Preview a generated style, then choose whether to save it to project `style.json` or globally.
- `nanoslides edit <slide-id> "Make the colors warmer"`: Iterate on a specific slide while maintaining its context.
- `nanoslides clearall`: Preview every slide in the current project, then confirm before deleting them all.
- `nanoslides deck "Launch plan for Product X" --detail-mode presenter --length short`: Plan and generate a full deck from one prompt with Gemini 3 Pro orchestration.
- `nanoslides export --format pptx`: Compile your generated images into a PowerPoint file.

## Project Structure

- `slides.json`: Tracks the current state of your presentation (order, IDs, prompts, and file paths).
- `style.json`: Project-specific style overrides.
- `slides/`: Default directory for generated assets.

## Roadmap & Improvements

We are currently working on:
- [ ] Separating CLI state management from the core library logic (removing "draft" hacks from the core).
- [ ] Enhancing the `SlideEngine` interface to support more providers (OpenAI, Flux).
- [ ] Improving the "Style Steal" accuracy for complex compositions.
- [ ] Adding more robust unit testing for the library API.
