# `slides.json` schema (draft)

`nanoslides` stores per-project slide state in `./slides.json`.

## Top-level object

```json
{
  "schema_version": 1,
  "name": "my-project",
  "created_at": "2026-02-18T22:45:39.052732Z",
  "engine": "nanobanana",
  "slides": []
}
```

### Fields

- `schema_version` (integer, required): format version for the state document. Current value is `1`.
- `name` (string, required): project name.
- `created_at` (string, required): UTC timestamp in ISO-8601 format.
- `engine` (string, required): selected generation engine identifier.
- `slides` (array, required): ordered slide entries.

## Slide entry object

```json
{
  "id": "history-overview",
  "order": 1,
  "prompt": "A minimal timeline slide",
  "image_path": "build/slides/1_history-overview.png",
  "metadata": {},
  "is_draft": false,
  "draft_of": null
}
```

- `id` (string, required): unique slide identifier in the project.
- `order` (integer, required): 1-based order index.
- `prompt` (string, required): latest prompt or edit instruction recorded for this slide.
- `image_path` (string or null, optional): generated image path for the slide.
- `metadata` (object, required): engine/provider metadata stored as key/value pairs.
- `is_draft` (boolean, required): whether this entry is a draft pending review (primarily used by the CLI).
- `draft_of` (string or null, optional): source slide ID for drafts (`null` for non-draft slides). Used by the CLI to track iterations.

## Edit review draft flow (CLI implementation)

> **Note**: This flow is specific to the `nanoslides` CLI. Programmatic users of the library are encouraged to handle slide variations and approvals in their own application logic before committing them to the project state.

- `nanoslides edit` now saves edits as draft slide entries when the target maps to a project slide.
- The CLI marks the output as `Needs review before applying` and prompts whether to save/apply it now (default is `yes`).
- If approved, the draft is applied to the source slide and the draft entry is removed.
- If not approved, the CLI asks whether to modify the edit instruction and retry immediately.
- If not approved and not retried, the draft entry remains in `slides.json` for later review.

## Legacy migration

- Legacy `slides.yaml` files are read automatically.
- When loaded through the CLI/library, legacy data is rewritten to `slides.json`.
