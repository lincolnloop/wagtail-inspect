# Bug Reproduction Prompt — Image Block Not Inspectable in `wagtail-inspect`

## What `wagtail-inspect` does

`wagtail-inspect` is a Wagtail plugin that adds block-level inspection to the Wagtail preview panel. It monkey-patches **four** Wagtail internals at Django startup (via `AppConfig.ready()`) so that during a preview request, blocks that go through `BoundBlock` rendering receive `data-block-id`, `data-block-type`, and `data-block-label`. **`inspect-augment.js`** fills gaps for DOM built outside those paths. A JavaScript overlay lets users hover or click a block in the preview to jump to that block’s panel in the CMS editor (or redirect from standalone preview).

---

## How annotation works (Python side — `patches.py`)

Four patches are applied once at startup; all are idempotent and log errors rather than crashing.

**Patch 1a — `BoundBlock.render`**
Called by `StreamBlock.render_basic` when Wagtail renders a stream via `{{ page.body }}` or `{% include_block page.body %}`. The patched version calls `_wrap_if_preview(self, original_output)`.

**Patch 1b — `BoundBlock.render_as_block`**
Called by `{% include_block block %}` when templates iterate explicitly:

```django
{% for block in page.body %}{% include_block block %}{% endfor %}
```

**Patch 1c — `ListValue.__iter__`**
During preview (`preview_active` ContextVar is `True`), each iteration yields a `_ListChildProxy` instead of a plain value. The proxy exposes `.id`, `.block`, and `.render_as_block` so that `{% include_block item %}` triggers Patch 1b, while still forwarding `__getattr__`, `__getitem__`, `__iter__`, etc. to the underlying value so templates that read fields directly keep working.

**Patch 2 — `PreviewableMixin.make_preview_request`**
Sets `preview_active` for the duration of the original `make_preview_request` (ContextVar token reset in `finally`), then snapshots `flat_block_map_for_instance(self)` into `_preview_block_maps` after the preview response is built.

**Annotation logic — `_wrap_if_preview`** (simplified; see `patches.py` for full logic)

Uses `resolve_block_type` / `resolve_block_label` from `block_map.py` for consistent labels with the API. If there is no HTML element, or the fragment is multi-root (markdown-style), a `display:contents` wrapper is used; otherwise attributes are injected on the first tag via `_inject_attrs_into_root`.

`_inject_attrs_into_root` uses this regex to find the opening tag and insert the three `data-*` attributes right after the tag name:

```python
_FIRST_TAG_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9:-]*")
```

If the block renders no HTML element at all (plain text from a `CharBlock`), a `display:contents` wrapper `<div>` is emitted instead.

---

## How the UI works (JavaScript side)

**`inspect-core.js` — `InspectMode` class**
Attached to the preview document (inside the iframe). On `activate()`:

- Appends `#wagtail-inspect-overlay` and `#wagtail-inspect-live` to the preview `document.body`.
- Listens for `mouseover`, `mouseout`, `click`, `keydown`, `focusin`, `focusout`, `resize` (window), and `scroll` on the document (capture phase); resize/scroll reposition the overlay via `requestAnimationFrame` coalescing.
- Block detection: `element.closest('[data-block-id]')`.
- Overlay positioning: `getBoundingClientRect()` on the annotated element; for zero-size rects, union **direct child** rects, then Range API only as last resort for text-only `display:contents` wrappers.

**`preview-inspect-controller.js` — Stimulus controller**
Registered as `preview-inspect`, attached to the same element as Wagtail's `w-preview` controller. Injects a crosshairs button into `.w-preview__sizes`. On button click, creates an `InspectMode` instance for the preview document and calls `.activate()`. On block click, calls `navigateToBlock(blockId)` which pushes `#block-{uuid}-section` to `window.history` and scrolls the editor to the matching `[data-contentpath="{blockId}"]` or `#block-{blockId}-section` element.

---

## The specific failure to reproduce: an image block that cannot be inspected

The bug is that **one specific block containing images cannot be highlighted or clicked in inspect mode**. The expected behaviour is that hovering over the block in the preview iframe shows the teal overlay and label; clicking it scrolls the editor to that block's panel.

### Likely root causes to check, in order

1. **No `data-block-id` on the root element** — The block's template renders its outermost element but `_inject_attrs_into_root` failed to inject into it. Check whether the outermost tag matches `<[a-zA-Z][a-zA-Z0-9:-]*` (e.g. it could be a self-closing element, or the block renders a Wagtail image tag `{% image … %}` which emits `<img …>` — a void element that `closest('[data-block-id]')` would find, but layout-wise the block wrapper may be the `<img>` itself and clicking on the image might not bubble up if there is a `pointer-events: none` rule or the overlay is in front).

2. **`ListBlock` child not wrapped** — If the image block is inside a `ListBlock` and the parent template iterates with `{% for item in value.items %}` instead of `{% for item in value.items %}{% include_block item %}`, the `_ListChildProxy` path is bypassed. The template must use `{% include_block item %}` (not `{{ item }}`) for each list item.

3. **`preview_active` is `False`** — The block renders but the patch guard `preview_active.get()` returns `False`. This happens if:
   - `PreviewableMixin.make_preview_request` was not patched (check `patches._originals`).
   - The block is rendered outside the preview request (e.g., rendered server-side by a custom view, not through Wagtail's standard preview machinery).

4. **`self.id` is `None`** — Plain `BoundBlock` instances (not `StreamChild` / `ListChild`) have no `.id`. The `getattr(self, "id", None)` guard skips them. This can happen for blocks that are not direct children of a `StreamBlock` or `ListBlock` with UUIDs — for example, a `StructBlock` field rendered manually via `{{ value.image }}` rather than `{% include_block %}`.

5. **`display:contents` wrapper + zero-size image** — If the block renders only an `<img>` (a replaced element) and the annotation was injected onto the `<img>` tag itself, `getBoundingClientRect()` returns a real size, so this is usually fine. But if the annotation landed on a `display:contents` wrapper and the image has not loaded yet, the Range API fallback may also return a zero rect — the overlay would be positioned at `(0,0)` with near-zero size and be invisible.

### What to look for in the DOM (browser DevTools on the preview iframe)

```js
// Check if any blocks have been annotated at all:
document.querySelectorAll("[data-block-id]");

// For the specific image block, check whether its root element has the attribute:
document.querySelector(".your-image-block-class").closest("[data-block-id]");

// Check whether the block's root is a display:contents wrapper:
document.querySelector("[data-block-id]").style.display; // "contents" = fallback path was used
```

### What to look for on the Python side

```python
# In the block's template, find how list items are iterated.
# This WORKS (triggers Patch 1b + ListChildProxy):
#   {% for item in value.logos %}{% include_block item %}{% endfor %}
#
# This does NOT annotate list items individually:
#   {% for item in value.logos %}{{ item.image }}{% endfor %}

# Confirm all four patches are applied:
from wagtail_inspect.patches import _originals
print(_originals.keys())
# Expected: dict_keys(['BoundBlock.render', 'BoundBlock.render_as_block',
#                       'PreviewableMixin.make_preview_request', 'ListValue.__iter__'])
```

### Minimal reproduction checklist

1. Open the page in the Wagtail editor preview panel (or standalone preview).
2. Activate inspect mode (crosshairs button in the preview toolbar, or "Inspect blocks" in the userbar).
3. Open browser DevTools → select the preview iframe as the execution context.
4. Run `document.querySelectorAll('[data-block-id]')` — the image block should appear.
5. **If it does not appear:** the problem is in the Python patch (rendering path, `preview_active`, or `ListBlock` iteration).
6. **If it appears but hovering shows no overlay:** the problem is in the JS layer — check that `getBoundingClientRect()` on the annotated element returns a non-zero rect.
7. **If hovering shows the overlay but clicking does not navigate:** `navigateToBlock` fired but no `[data-contentpath="{blockId}"]` / `#block-{blockId}-section` element exists in the editor DOM.
