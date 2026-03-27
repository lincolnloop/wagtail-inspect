# Wagtail Inspect -- Documentation

A Wagtail plugin that adds a browser DevTools-like inspect mode to the preview panel. Editors can hover over blocks in a page preview to see their type, then click to jump straight to the corresponding editor panel in the CMS admin. The feature works in both the CMS editor's built-in preview panel (iframe) and on standalone preview pages (via the Wagtail userbar).

## Getting Started

If you're new to this project, start with the [README](../README.md) for installation instructions, then read the [Architecture Overview](architecture.md) to understand how the pieces fit together.

## Documentation Index

| Document                                                        | Description                                                                                                                                                                                                                                                                        |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Architecture Overview](architecture.md)                        | High-level system design, data flow diagrams, and how the two integration modes (iframe preview vs. userbar) connect                                                                                                                                                               |
| [Python Backend](python-backend.md)                             | Deep dive into `__init__.py`, `block_map.py`, `patches.py`, `views.py`, `wagtail_hooks.py`, and `apps.py` -- block rendering patches, ContextVar-based preview detection, the block map data layer, the Page Inspect API, Wagtail hook registrations, and Django app configuration |
| [Front-End Controllers](frontend-controllers.md)                | Walkthrough of the JavaScript modules: `InspectMode`, `inspect-augment.js`, shared preview helpers, `PreviewInspectController`, and the userbar `InspectController`                                                                                                                |
| [Implementation Review](implementation-review.md)               | Code review covering resolved items, remaining concerns, and improvement suggestions                                                                                                                                                                                               |
| [Issues & backlog](issues/README.md)                            | Open tracking notes (compatibility, tests, flags, hardening)                                                                                                                                                                                                                       |
| [Monkey-patching alternatives](monkey-patching-alternatives.md) | Design doc: why patches exist and options considered                                                                                                                                                                                                                               |

## Quick Reference

### File Map

```
wagtail_inspect/
  __init__.py                        # Package init, preview_active ContextVar, _preview_block_maps cache
  apps.py                            # Django AppConfig -- applies patches on startup
  block_map.py                       # Block tree traversal -- builds UUID-keyed block map from page data
  patches.py                         # Monkey-patches Wagtail block/preview APIs for tagging + map snapshot
  views.py                           # PageInspectView -- block map API endpoint (/wagtail-inspect/api/page/<id>/)
  wagtail_hooks.py                   # Wagtail hooks for CSS/JS injection, config script, API URL, userbar item
  static/.../css/
    preview-inspect.css              # Button active state, focus ring, flash animation
  static/.../js/
    inspect-core.js                  # Shared InspectMode class (overlay, events, a11y)
    inspect-augment.js               # DOM augmentation utility -- annotates blocks Python patches missed
    preview-inspect-helpers.js       # Editor navigation helpers + hash scroll (WagtailInspectPreviewHelpers)
    preview-inspect-controller.js    # Stimulus controller for CMS preview panel
    userbar-inspect.js               # Plain-JS controller for standalone preview pages
  templates/.../userbar/
    item_inspect_preview.html        # Userbar menu item template
  docs/
    index.md                         # This file
    architecture.md                  # Architecture overview
    python-backend.md                # Python backend deep dive
    frontend-controllers.md          # JavaScript controllers deep dive
    implementation-review.md         # Code review and notes
    monkey-patching-alternatives.md  # Design: patching vs other approaches
    issues/                          # Open backlog (see issues/README.md)
```

### Key Concepts

| Concept                       | Description                                                                                                                                               |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data-block-id`               | UUID attribute injected onto the block's own root element during preview rendering                                                                        |
| `data-block-type`             | Block type name as registered (e.g., `"hero"`, `"stat_list_block"`)                                                                                       |
| `data-block-label`            | Human-readable block label (e.g., "Hero", "Rich Text")                                                                                                    |
| `data-contentpath`            | Wagtail's native attribute on editor panel sections -- its value matches the block UUID                                                                   |
| `display:contents`            | CSS fallback wrapper used for multi-root fragments (e.g. markdown) and text-only blocks that render no single HTML root element                           |
| `InspectMode`                 | Shared JS class providing overlay, highlighting, and event handling (`inspect-core.js`)                                                                   |
| `WagtailInspectAugment`       | Global exposed by `inspect-augment.js` -- `augmentPreviewBlocks(blocks)` annotates DOM elements that Python patches missed                                |
| `preview_active`              | `ContextVar[bool]` in `__init__.py` -- signals preview mode to the rendering patches; set by patching `PreviewableMixin.make_preview_request`             |
| `_preview_block_maps`         | Module-level `dict[int, dict]` in `__init__.py` -- caches the block map after each preview render so the API serves UUIDs that match the live preview DOM |
| `flat_block_map_for_instance` | Function in `block_map.py` -- returns a `{uuid: {type, label, children}}` dict for all StreamField blocks on a page instance                              |
| `ListValue.__iter__`          | Always patched in `apply_patches()` -- iterating a list field yields `_ListChildProxy` (use `{% include_block x %}` or `x.value` for inner struct fields) |
| `window.wagtailInspectConfig` | Inline config object injected by `global_admin_js()` -- provides `apiBase` and `augmentScriptUrl` to the admin-side controllers                           |

### Requirements

- Python 3.8+
- Django 4.2+
- Wagtail 5.0+ (tested with 5.x, 6.x, and 7.x)
