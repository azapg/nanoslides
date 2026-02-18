# nanoslides

`nanoslides` is a Python CLI and library foundation for generating presentation slides
with AI image models.

## Quick start

```bash
pip install .
nanoslides --help
nanoslides setup
nanoslides init MyProject
nanoslides style create --base-prompt "Soft lighting, cinematic composition"
nanoslides style create studio-look --global --base-prompt "High-end studio product look"
nanoslides generate "A minimalist title slide about AI safety" --model flash
```

This repository currently includes the architecture skeleton, configuration loading,
and foundational CLI commands, including NanoBanana-backed slide generation.

## Persistent styles

- Project-level defaults live in `./style.json` (`base_prompt`, `negative_prompt`,
  `reference_images`, `reference_comments`, and optional `style_id`).
- Global reusable presets live in `~/.nanoslides/styles.json` and can be selected
  with `--style-id` or by setting `style_id` in project `style.json`.
- `nanoslides generate` automatically merges global + project style context and
  injects it into generation/edit prompts and reference inputs.
