# Bug Reproduction Prompt — Image Block Not Inspectable in `wagtail-inspect`

## What `wagtail-inspect` does

`wagtail-inspect` is a Wagtail plugin that adds block-level inspection to the Wagtail preview panel, standalone preview, and live pages for users who can edit them. Rendered blocks get `data-block-id`, `data-block-type`, and `data-block-label` from [wagtail-block-ids](https://github.com/lincolnloop/wagtail-block-ids), which patches Wagtail's block rendering; wagtail-inspect decides when marking is on. **`inspect-augment.js`** fills gaps for DOM built outside those paths. A JavaScript overlay lets users hover or click a block to jump to that block's panel in the CMS editor (or redirect from the standalone preview / live page).

---

## How annotation works (Python side)

### In wagtail-block-ids (`wagtail_block_ids.marks`)

Patches install once, on first use (inspect's `apply_patches()` triggers it at startup); all are idempotent and log errors rather than crashing.

- **`BoundBlock.render` / `render_as_block`** -- while a `marking()` scope is open (`wagtail_block_ids.is_marking()`), add the three attributes to the first tag of each UUID-bearing block's output. Covers `{{ page.body }}`, `{% include_block page.body %}`, and explicit loops:

  ```django
  {% for block in page.body %}{% include_block block %}{% endfor %}
  ```

- **`ListValue.__iter__`** -- while marking, yields proxies that carry the list child's `.id` and render through `BoundBlock`, so `{% include_block item %}` gets marked, while field access (`item.title`) keeps working.
- **`Page.serve` / `PreviewableMixin.serve_preview`** -- ask every registered page marker whether to mark this serve.
- **Wrapping** -- in a scope opened with `wrap=True` (inspect always asks for it), output with no root element, several roots, or loose text beside the root is wrapped in `<div … style="display:contents">` instead.

See that package's README and module docstrings for details.

### In wagtail-inspect (`patches.py`)

- **`PreviewableMixin.make_preview_request` patch** -- renders the preview inside `marking(wrap=True)`, then `remember_preview(self, user)` stores the block map for that editor and page in Django's cache (24h).
- **`mark_live_page`** -- registered with `register_page_marker(..., wrap=True)`; marks live pages for users with `can_edit()` when `WAGTAIL_INSPECT_LIVE_PAGES` is on (default).

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

1. **No `data-block-id` on the root element** — The block's template renders its outermost element but no attributes landed on it. Check what the outermost output is: a Wagtail image tag `{% image … %}` emits `<img …>`, a void element that `closest('[data-block-id]')` would find, but clicking on the image might not register if there is a `pointer-events: none` rule or another element is in front.

2. **`ListBlock` child not marked** — If the image block is inside a `ListBlock` and the parent template iterates with `{% for item in value.items %}{{ item.image }}{% endfor %}` instead of `{% for item in value.items %}{% include_block item %}{% endfor %}`, the list proxy never renders through `BoundBlock`. The template must use `{% include_block item %}` (not `{{ item }}`) for each list item.

3. **Marking is off** — The block renders but `wagtail_block_ids.is_marking()` is `False` at that moment. This happens if:
   - `PreviewableMixin.make_preview_request` was not patched (check `wagtail_inspect.patches._originals`).
   - The block is rendered outside the preview request or page serve (e.g., server-side by a custom view, not through Wagtail's standard preview or `Page.serve` machinery).
   - On a live page: the user cannot edit the page, or `WAGTAIL_INSPECT_LIVE_PAGES = False`.

4. **`self.id` is `None`** — Plain `BoundBlock` instances (not `StreamChild` / `ListChild`) have no `.id` and are skipped. This can happen for blocks that are not direct children of a `StreamBlock` or `ListBlock` with UUIDs — for example, a `StructBlock` field rendered manually via `{{ value.image }}` rather than `{% include_block %}`.

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
# This WORKS (list proxy renders through BoundBlock and is marked):
#   {% for item in value.logos %}{% include_block item %}{% endfor %}
#
# This does NOT annotate list items individually:
#   {% for item in value.logos %}{{ item.image }}{% endfor %}

# Confirm inspect's preview patch is applied:
from wagtail_inspect.patches import _originals
print(_originals.keys())
# Expected: dict_keys(['PreviewableMixin.make_preview_request'])

# Confirm wagtail-block-ids' marking patches are applied:
from wagtail_block_ids.marks import _originals as block_ids_originals
print(block_ids_originals.keys())
```

### Minimal reproduction checklist

1. Open the page in the Wagtail editor preview panel (or standalone preview).
2. Activate inspect mode (crosshairs button in the preview toolbar, or "Inspect blocks" in the userbar).
3. Open browser DevTools → select the preview iframe as the execution context.
4. Run `document.querySelectorAll('[data-block-id]')` — the image block should appear.
5. **If it does not appear:** the problem is on the server side (rendering path, marking scope / `is_marking()`, or `ListBlock` iteration).
6. **If it appears but hovering shows no overlay:** the problem is in the JS layer — check that `getBoundingClientRect()` on the annotated element returns a non-zero rect.
7. **If hovering shows the overlay but clicking does not navigate:** `navigateToBlock` fired but no `[data-contentpath="{blockId}"]` / `#block-{blockId}-section` element exists in the editor DOM.
