# Implementation Review

A candid review of the codebase, covering code quality observations, resolved items, and remaining concerns. For the open backlog, see [issues/README.md](issues/README.md).

## Table of Contents

- [Resolved items](#resolved-items)
- [Architecture decisions](#architecture-decisions)
- [Remaining concerns](#remaining-concerns)
- [Code quality summary](#code-quality-summary)

---

## Resolved Items

The following findings from the original review have been addressed:

| Finding                                                                     | Resolution                                                                                                                                                                                            |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Leftover `# pdb.set_trace()` in `patches.py`                                | Removed                                                                                                                                                                                               |
| Unused `_is_in_preview_panel()` function                                    | Removed                                                                                                                                                                                               |
| Unused `_is_preview_from_thread_local()` function                           | Removed                                                                                                                                                                                               |
| Commented-out preview guards                                                | Re-introduced as proper guards via `preview_active` ContextVar                                                                                                                                        |
| `mark_safe()` with unescaped string interpolation                           | Replaced by `format_html()` which auto-escapes all interpolated values                                                                                                                                |
| `patched_stream_child_render` required `context` parameter                  | Both `BoundBlock` patch functions accept `context=None` to prevent `TypeError`                                                                                                                        |
| Scroll handler fires on every frame                                         | Scroll handling removed; resize handler is the only layout-repositioning path                                                                                                                         |
| `loadConfiguration()` silently swallows errors                              | Catch block now logs `console.warn` with the error                                                                                                                                                    |
| Module docstring outdated                                                   | Rewritten to accurately describe the three patches and BoundBlock approach                                                                                                                            |
| Shared JS logic duplicated across controllers                               | Extracted into `inspect-core.js` as the `InspectMode` class, used by both controllers                                                                                                                 |
| `console.log` in `preview-inspect-controller.js`                            | Removed                                                                                                                                                                                               |
| Middleware URL-based preview detection is fragile                           | Removed entirely; preview detection now uses a `ContextVar` set by patching `PreviewableMixin.make_preview_request`                                                                                   |
| Patch failures crash the entire Django app at startup                       | Each patch is wrapped in `try/except` via `_apply_patch()`; a single failure is logged and skipped without blocking startup ([#001](issues/001-wagtail-version-compatibility.md))                     |
| No warning for untested Wagtail versions                                    | `apply_patches()` logs a warning if the Wagtail version is outside the tested range ([#001](issues/001-wagtail-version-compatibility.md))                                                             |
| Snippet-embedded StreamFields produced unnavigable `data-block-id` wrappers | Replaced by patching `BoundBlock.render` and `BoundBlock.render_as_block` with an `id` guard -- only blocks that carry a UUID (i.e. `StreamChild` and `ListChild`) are wrapped                        |
| Block labels don't distinguish ListBlock items                              | `_wrap_if_preview()` reads `self.block_type` (StreamChild) or `self.block.name` (ListChild), plus `self.block.label` for the human-readable label                                                     |
| Thread-local state is not async-safe                                        | Replaced by `preview_active: ContextVar[bool]` in `__init__.py`; set/reset in `patched_make_preview_request`                                                                                          |
| Preview detection relies on template context or URL matching                | Moved to `PreviewableMixin.make_preview_request` patch -- fires before template rendering, requires no context argument                                                                               |
| `data-block-type` attribute missing                                         | `_wrap_if_preview()` now writes `data-block-type` alongside `data-block-id` and `data-block-label`                                                                                                    |
| `InspectBlocksUserbarItem` used wrong template attribute                    | Changed `template = ...` to `template_name = ...`; Wagtail's `BaseItem` requires `template_name` — using `template` caused the userbar item to silently fail to render                                |
| `InspectBlocksUserbarItem.get_context_data` had wrong signature             | Changed `(self, request)` to `(self, parent_context)` to match Wagtail's `BaseItem` API; incorrect signature caused `super().get_context_data()` to fail                                              |
| `print(output)` debug statement in `global_admin_js()`                      | Removed stray `print(output)` that logged the admin JS HTML to stdout on every admin page load                                                                                                        |
| `ListValue.__iter__` yielded plain values instead of `ListChild`            | Patched `ListValue.__iter__` in `apply_patches()` (preview-gated proxies); `{% for x in value.items %}{% include_block x %}` produces `data-block-id` wrappers without relying on `__getitem__` alone |

---

## Architecture Decisions

These are intentional design choices that may look unusual but have specific reasons:

### 1. Monkey-patching instead of template tags

Wagtail's block rendering pipeline has no extension point for injecting attributes around individual blocks. A custom template tag would require modifying every template that uses `{% include_block %}`, which is impractical. Monkey-patching is the only way to transparently add `data-block-id` without template changes.

**Trade-off:** Version coupling to Wagtail internals. See [issue #001](issues/001-wagtail-version-compatibility.md).

### 2. Patching `BoundBlock` instead of `IncludeBlockNode`

`BoundBlock` is the common base class of `StreamValue.StreamChild` and `ListValue.ListChild`. Patching at this level covers both rendering entry points (`render` for `{{ page.body }}` / `{% include_block page.body %}`, and `render_as_block` for explicit `{% include_block block %}` iteration) and automatically handles `ListChild` objects with UUIDs.

The `.id` guard (`getattr(self, "id", None)`) ensures that plain `BoundBlock` instances with no UUID are never wrapped -- this replaces the earlier `isinstance(value, StreamValue.StreamChild)` check in the `IncludeBlockNode` patch.

### 3. `ContextVar` instead of thread-local state

`preview_active` is a `ContextVar[bool]` rather than `threading.local`. This is async-safe (works with both WSGI and ASGI), is automatically scoped per execution context, and does not require passing a `context` argument to the wrapping logic.

The ContextVar is set by patching `PreviewableMixin.make_preview_request` -- the earliest entry point that fires before template rendering and is available in all nested calls.

### 4. No middleware required

`middleware.py` was deleted. Preview detection is handled entirely by the `patched_make_preview_request` patch, which sets `preview_active` before template rendering. No `MIDDLEWARE` entry is required.

### 5. Python-only wrapping is sufficient

`BoundBlock.render`, `BoundBlock.render_as_block`, and `ListValue.__iter__` together cover every block rendering path in standard Wagtail templates. No client-side DOM annotation ("augmentation") is needed: if a template uses `{% include_block %}` on list items, Python's `ListValue.__iter__` patch ensures those items arrive as `ListChild` with UUIDs and are wrapped correctly.

### 6. Attribute injection with `display:contents` fallback

`_inject_attrs_into_root` injects `data-block-*` attributes directly onto the block's own root element, emitting no wrapper. This preserves all CSS layouts including Grid and Flexbox without any side-effects.

**Fallback:** when a block renders plain text with no HTML element (rare — typically only bare `CharBlock`s), a `<div style="display:contents">` wrapper is used instead. The wrapper exists in the DOM but generates no layout box, remaining queryable via `[data-block-id]`.

**Rect computation:** `_getBlockRect()` calls `getBoundingClientRect()` directly on the annotated root element (primary path). It falls back to the Range API only when the rect is zero-sized, which indicates a `display:contents` wrapper (text-only fallback case).

### 7. Dynamic script loading in the userbar template

Wagtail clones userbar content from a `<template>` element into Shadow DOM. Cloned `<script src>` tags don't execute, but inline scripts do. The inline script bootstrapper dynamically creates `<script>` elements to load `inspect-core.js` and `userbar-inspect.js` in the correct order.

### 8. Two controllers instead of one

The CMS preview panel (iframe) and standalone preview page (no iframe) have fundamentally different requirements: cross-frame communication, iframe reload handling, in-page vs. redirect navigation, Stimulus vs. plain JS. A single controller would need to handle all these cases, increasing complexity. Two focused controllers with a shared core (`InspectMode`) is cleaner.

### 9. `MutationObserver` for auto-attachment

The preview panel's `data-controller` attribute is set by Wagtail's own templates, which we cannot modify. A `MutationObserver` watches for the preview panel to appear in the DOM and dynamically appends `preview-inspect` to its controller list. This is the standard pattern for extending Wagtail's Stimulus controllers from external code.

---

## Remaining Concerns

### Browser Compatibility

The `color-mix()` CSS function is used in `preview-inspect.css` (defaults) and in runtime style injection in `inspect-core.js`:

| Feature          | Chrome     | Firefox    | Safari     |
| ---------------- | ---------- | ---------- | ---------- |
| `color-mix()`    | 111+       | 113+       | 16.2+      |
| `:focus-visible` | 86+        | 85+        | 15.4+      |
| Range API        | All modern | All modern | All modern |
| Shadow DOM       | 53+        | 63+        | 10+        |

Since Wagtail's admin itself requires modern browsers, these requirements are acceptable. If broader support is needed, CSS fallbacks can be added.

### Test Coverage

Three test suites are in place:

- **Backend unit tests** (`tests/backend/`) — patch behaviour, idempotency, ContextVar reset, ListValue iteration, wagtail hooks
- **Frontend unit tests** (`tests/frontend/`) — `InspectMode` class via Bun + happy-dom: activation, deactivation, accessibility, event handling, overlay, breadcrumbs
- **E2E tests** (`tests/e2e/`) — Playwright tests for editor preview, standalone preview, and rich block scenarios

Remaining gaps: no unit tests for `preview-inspect-controller.js` (Stimulus lifecycle, iframe reload) or `userbar-inspect.js` (shadow DOM initialisation). These are covered indirectly by the E2E suite.

---

## Code Quality Summary

### Strengths

1. **Clear separation of concerns** -- Python patches handle data tagging, the API handles structure, JS controllers handle UI, shared core handles interaction
2. **Preview-only wrapping** -- Blocks are only wrapped during preview; public pages are unaffected
3. **Defense-in-depth escaping** -- `format_html()` auto-escapes all interpolated values (`block_id`, `block_type`, `block_label`) even though they come from trusted sources
4. **Graceful cleanup** -- ContextVar reset in `finally` block, `deactivate()` safe to call multiple times, listeners removed on disconnect
5. **Accessibility** -- ARIA live region, keyboard Tab navigation, focus-visible outlines, screen reader announcements
6. **Theme awareness** -- Colors resolved from Wagtail's CSS variables, works with light/dark/auto themes
7. **Iframe reload resilience** -- Inspect mode survives live preview refreshes via MutationObserver + state flag in `PreviewInspectController`
8. **Resilient patching** -- `apply_patches()` guard prevents double-application, wraps each patch in `try/except`, warns on untested Wagtail versions
9. **Principled wrapping rule** -- Only blocks carrying a `.id` (UUID) are wrapped, mirroring Wagtail's own logic that editor panels are only created for UUID-bearing blocks
10. **Async-safe preview detection** -- `ContextVar` works with both WSGI and ASGI; no thread-local leakage between concurrent requests

### Areas for Improvement

Open backlog: [issues/README.md](issues/README.md).

| Area                          | Link                                                | Notes                                                       |
| ----------------------------- | --------------------------------------------------- | ----------------------------------------------------------- |
| Wagtail version compatibility | [#001](issues/001-wagtail-version-compatibility.md) | Graceful patching + version warning; CI matrix still wanted |
| Test suite gaps & CI          | [#002](issues/002-no-test-suite.md)                 | Suites exist locally; CI workflow not in repo               |
| Feature flag                  | [#003](issues/003-no-feature-flag.md)               | Opt-out setting not implemented                             |
| Hardcoded z-index             | [#007](issues/007-hardcoded-z-index.md)             | Stacking in CSS; optional token / Wagtail layering check    |
| Template script injection     | [#012](issues/012-template-script-injection.md)     | Harden inline bootstrap URLs                                |

**Design reference:** [Monkey-patching alternatives](monkey-patching-alternatives.md) (upstream RFC / template-tag options).
