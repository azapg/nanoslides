# nanoslides

`nanoslides` is a Python CLI and library foundation for generating presentation slides
with AI image models.

## Quick start

```bash
pip install .
nanoslides --help
nanoslides setup
nanoslides init MyProject
nanoslides styles create
nanoslides styles create historic --global --slides-base-reference .\image.png
nanoslides styles edit historic --slides-base-reference .\image.png
nanoslides styles
nanoslides generate "A minimalist title slide about AI safety" --model flash
nanoslides edit slide-abc123 "Translate all text to Spanish"
nanoslides edit .\slides\slide-abc123.png "Replace the person in the top-left with Ricardo J. Alfaro" --references .\rja.png
nanoslides export --format pptx
```

This repository currently includes the architecture skeleton, configuration loading,
and foundational CLI commands, including NanoBanana-backed slide generation.

## Persistent styles

- Project-level defaults live in `./style.json` (`base_prompt`, `negative_prompt`,
  `reference_images`, `reference_comments`, and optional `style_id`).
- Global reusable presets live in `~/.nanoslides/styles.json` and can be selected
  with `--style-id` or by setting `style_id` in project `style.json`.
- Use `--slides-base-reference` on `nanoslides styles create/edit` for images that
  are included in all slide generation/edit requests for visual consistency.
- `nanoslides generate` automatically merges global + project style context and
  injects it into generation/edit prompts and reference inputs.

## Guided CLI workflow

- `nanoslides generate` runs directly when a prompt is provided, and only opens
  the guided prompt/model/style/reference flow when the prompt is omitted.
- `nanoslides styles create` and `nanoslides styles edit` support guided setup.
- `nanoslides generate` defaults to a `16:9` output aspect ratio; override with
  `--aspect-ratio` for other formats.
- Long image generation calls display a spinner/status indicator.
- Default logging is quiet; use `-v` for verbose provider/network logs.
