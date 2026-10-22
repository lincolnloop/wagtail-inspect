# Wagtail Inspect -- Documentation

A Wagtail plugin that adds a browser DevTools-like inspect mode to the preview panel. Editors can hover over blocks in a page preview to see their type, then click to jump straight to the corresponding editor panel in the CMS admin. The feature works in the CMS editor's built-in preview panel (iframe), on standalone preview pages, and on live pages for users who can edit them (the last two via the Wagtail userbar).

Marking the rendered blocks with `data-block-*` attributes is done by the sibling package [wagtail-block-ids](https://github.com/lincolnloop/wagtail-block-ids), which wagtail-inspect depends on. This repo decides *when* blocks are marked (previews, editors' live pages), serves the block map API, and provides the overlay.

## Getting Started

If you're new to this project, start with the [README](../README.md) for installation instructions, then read the [Architecture Overview](architecture.md) to understand how the pieces fit together.

## Documentation Index

| Document                                                        | Description                                                                                                                                                                                                                                                                        |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Architecture Overview](architecture.md)                        | High-level system design, data flow diagrams, and how the two integration modes (iframe preview vs. userbar) connect                                                                                                                                                               |
| [Python Backend](python-backend.md)                             | Deep dive into `__init__.py`, `block_map.py`, `patches.py`, `views.py`, `wagtail_hooks.py`, and `apps.py` -- the preview patch and live-page marker, the per-editor block map cache, the Page Inspect API, Wagtail hook registrations, and Django app configuration |
| [Front-End Controllers](frontend-controllers.md)                | Walkthrough of the JavaScript modules: `InspectMode`, `inspect-augment.js`, shared preview helpers, `PreviewInspectController`, and the userbar `InspectController`                                                                                                                |
| [Implementation Review](implementation-review.md)               | Code review covering resolved items, remaining concerns, and improvement suggestions                                                                                                                                                                                               |
| [Issues & backlog](issues/README.md)                            | Open tracking notes (compatibility, tests, flags, hardening)                                                                                                                                                                                                                       |
| [Monkey-patching alternatives](monkey-patching-alternatives.md) | Design doc: why patches exist and options considered                                                                                                                                                                                                                               |
| [Bug reproduction prompt](bug-reproduction-prompt.md)         | Structured notes for debugging “block not inspectable” reports (patches, augment, DOM checks)                                                                                                                                                                                         |

## Quick Reference

### File Map

Library code lives under `src/wagtail_inspect/` (see `pyproject.toml`).

```
src/wagtail_inspect/
  __init__.py                        # Package init, inspect_live_pages_enabled(), user_can_inspect()
  apps.py                            # Django AppConfig -- applies patches on startup
  block_map.py                       # Flat block map + per-editor preview map cache (block_map_for, remember_preview)
  patches.py                         # make_preview_request patch + live-page marker (marking itself is in wagtail-block-ids)
  views.py                           # PageInspectView -- block map API endpoint (/wagtail-inspect/api/page/<id>/)
  wagtail_hooks.py                   # Wagtail hooks for CSS/JS injection, config script, API URL, userbar item
  static/.../css/
    preview-inspect.css              # Button active state, focus ring, flash animation
  static/.../js/
    inspect-core.js                  # Shared InspectMode class (overlay, events, a11y)
    inspect-augment.js               # DOM augmentation utility -- annotates blocks the server-side marks missed
    preview-inspect-helpers.js       # Editor navigation helpers + hash scroll (WagtailInspectPreviewHelpers)
    preview-inspect-controller.js    # Stimulus controller for CMS preview panel
    userbar-inspect.js               # Plain-JS controller for standalone preview and live pages
  templates/.../userbar/
    item_inspect_preview.html        # Userbar menu item template
  docs/
    index.md                         # This file
    architecture.md                  # Architecture overview
    python-backend.md                # Python backend deep dive
    frontend-controllers.md          # JavaScript controllers deep dive
    implementation-review.md         # Code review and notes
    monkey-patching-alternatives.md  # Design: patching vs other approaches
    bug-reproduction-prompt.md       # Debugging checklist for inspect failures
    issues/                          # Open backlog (see issues/README.md)
```

### Key Concepts

| Concept                       | Description                                                                                                                                               |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data-block-id`               | UUID attribute added (by wagtail-block-ids) to the block's own root element in previews and editors' live pages                                           |
| `data-block-type`             | Block type name as registered (e.g., `"hero"`, `"stat_list_block"`)                                                                                       |
| `data-block-label`            | Human-readable block label (e.g., "Hero", "Rich Text")                                                                                                    |
| `data-contentpath`            | Wagtail's native attribute on editor panel sections -- its value matches the block UUID                                                                   |
| `display:contents`            | CSS fallback wrapper used for multi-root fragments (e.g. markdown) and text-only blocks that render no single HTML root element                           |
| `InspectMode`                 | Shared JS class providing overlay, highlighting, and event handling (`inspect-core.js`)                                                                   |
| `WagtailInspectAugment`       | Global exposed by `inspect-augment.js` -- `augmentPreviewBlocks(blocks)` annotates DOM elements the server-side marks missed                              |
| `marking(wrap=True)`          | `wagtail_block_ids` scope: blocks rendered inside it get `data-block-*`; `wrap=True` allows `display:contents` wrappers. `is_marking()` tells whether one is open |
| `register_page_marker`        | `wagtail_block_ids` hook: inspect registers `mark_live_page` so editors' live-page serves are marked                                                      |
| `flat_block_map_for_instance` | Function in `block_map.py` -- returns a `{uuid: {type, label, children}}` dict for all StreamField blocks on a page instance                              |
| `remember_preview`            | Function in `block_map.py` -- after a preview render, stores that editor's map in Django's cache (key: user pk + page pk, 24h timeout)                    |
| `block_map_for`               | Function in `block_map.py` -- the map the API serves: live page, else the editor's last preview, else latest revision, else the page                     |
| `window.wagtailInspectConfig` | Inline config object injected by `global_admin_js()` -- provides `apiBase` and `augmentScriptUrl` to the admin-side controllers                           |

### Requirements

- Python 3.12+ (`requires-python` in `pyproject.toml`)
- Django 4.2+
- Wagtail 5.0+ (tox matrix in `pyproject.toml` covers 5.x, 6.x, and 7.x; wagtail-block-ids warns at startup outside its `TESTED_WAGTAIL_VERSIONS`)
- [wagtail-block-ids](https://github.com/lincolnloop/wagtail-block-ids) 0.2.0+ (installed as a dependency)
