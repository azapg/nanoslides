# Nanoslides Use-Case Tests

This document explains the behavior contracts captured in `tests/test_use_cases.py`.

These tests are intentionally **use-case driven** and partly **aspirational**:
- some tests validate behavior that already exists;
- some tests define capability targets that do not exist yet and are expected to fail for now.

## Why these tests exist

`nanoslides` is library-first, so we need tests that describe end-to-end workflows the library should support for real product usage:

1. Create a presentation from a single prompt.
2. Create a presentation from a PDF spec/research paper.
3. Reorder slides in an existing presentation.
4. Translate a full presentation to another language.
5. Generate one "dramatic" slide in a style intentionally different from deck baseline.
6. Steal/infer style from an existing PowerPoint.

These tests serve as executable product requirements and a roadmap for missing APIs.

## Setup

From repository root:

```bash
pip install -e .
pip install pytest
pytest -q tests/test_use_cases.py
```

## Expected current status

- Reordering slides should pass (covered by existing `Presentation.move_slide` behavior).
- Multiple tests are expected to fail until corresponding APIs are implemented.

