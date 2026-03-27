# No Automated Test Suite

**Labels:** `testing`, `risk`, `quality`
**Priority:** High

## Status

Test infrastructure is in place (pytest, pytest-django, `testapp/` with a `TestPage` model,
`RequestFactory` used for view tests). Core Python, JavaScript (Bun), and Playwright E2E tests
are implemented locally (`just test`, `just test-e2e`). **CI:** there is no `.github/workflows`
in this repo yet — automated runs on every push are not configured here.

Userbar visibility is enforced in `add_inspect_blocks_item()` (`construct_wagtail_userbar` hook)
with early returns, not only via `InspectBlocksUserbarItem.is_shown()` — see `test_wagtail_hooks.py`.

---

## Python test cases (pytest / Django TestCase)

### `patches.py` — wrapping logic

- [x] `_wrap_if_preview()` produces correct HTML: `data-block-id`, `data-block-type`, `data-block-label`, and `style="display:contents"`
- [x] `_wrap_if_preview()` skips blocks with no `.id` attribute (plain `BoundBlock`)
- [x] `_wrap_if_preview()` does nothing when `preview_active` is `False`
- [x] `patched_bound_block_render` behaviour — same wrapping rules as `_wrap_if_preview` (covered by `_wrap_if_preview` tests; patch installed: `test_apply_patches_is_idempotent`)
- [x] Pass-through without block IDs / when preview inactive — `test_wrap_if_preview_skips_*`, `test_wrap_if_preview_skips_when_preview_is_inactive`
- [ ] `patched_bound_block_render_as_block` — dedicated test calling `BoundBlock.render_as_block` under preview (still optional)
- [x] `preview_active` ContextVar is `True` inside `patched_make_preview_request` and `False` after (including on exception)
- [x] `apply_patches()` is idempotent — calling twice does not double-patch

### `wagtail_hooks.py` — `add_inspect_blocks_item` / `InspectBlocksUserbarItem`

- [x] Item not added when `page` is `None` — `test_add_inspect_blocks_item_skips_when_page_missing_or_no_id`
- [x] Item not added when `page.id` is falsy — same test
- [x] Item not added when `request.is_preview` is falsy — `test_add_inspect_blocks_item_skips_when_not_preview`
- [x] Item not added when `is_preview` attribute missing — `test_add_inspect_blocks_item_skips_when_is_preview_absent`
- [ ] User lacks `can_edit()` — not asserted in unit tests (Wagtail userbar may filter elsewhere; optional)
- [x] Item appended on preview with valid page — `test_add_inspect_blocks_item_appends_on_preview_with_page_id`
- [x] `get_context_data()` includes `inspect_preview_context` (`pageId`, `editUrl`, `apiUrl`) and script URLs — `test_get_context_data_includes_api_and_script_urls`
- [x] `global_admin_js()` includes core/helpers/controller scripts — `test_global_admin_js_emits_wagtail_inspect_config_and_scripts`

---

## JavaScript test cases (Bun + happy-dom)

Infrastructure is set up: Bun + happy-dom; [tests/frontend/setup.js](../../tests/frontend/setup.js) loads `inspect-core.js` as
a classic browser script. Run with `bun test tests/frontend` (see [package.json](../../package.json)).

### `InspectMode` lifecycle

- [x] `activate()` injects overlay, style element, and ARIA live region
- [x] `activate()` sets `active` to `true`
- [x] `activate()` adds `role`, `tabindex`, and `aria-label` to existing block elements
- [x] `deactivate()` removes overlay, style element, and live region
- [x] `deactivate()` sets `active` to `false`
- [x] `deactivate()` removes accessibility attributes from block elements
- [x] `deactivate()` is safe to call multiple times

### `InspectMode` methods

- [x] `_findBlockElement()` returns the element itself when it carries `data-block-id`
- [x] `_findBlockElement()` returns the closest ancestor with `data-block-id`
- [x] `_findBlockElement()` returns `null` when no ancestor has `data-block-id`
- [x] `_resolveColors()` falls back to `DEFAULTS` when CSS variables are not set
- [x] `_getBlockRect()` delegates to `Range.getBoundingClientRect` (mocked in jsdom)
- [x] `_buildBreadcrumbLabel()` returns the label for a top-level block
- [x] `_buildBreadcrumbLabel()` produces "Parent › Child" for nested blocks
- [x] `_buildBreadcrumbLabel()` falls back to "Block" when label attribute is absent
- [x] `_enableBlockAccessibility()` adds `role="button"`, `tabindex`, and `aria-label`
- [x] `_disableBlockAccessibility()` removes those attributes

### `InspectMode` event handling

- [x] Escape keydown calls `onEscape`
- [x] Click on a block element calls `onBlockClick` with the block ID
- [x] Enter keydown on a block element calls `onBlockClick`
- [x] Enter keydown on a non-block element does not call `onBlockClick`
- [x] `activateHighlightedBlock()` calls `onBlockClick` for the highlighted element
- [x] `activateHighlightedBlock()` does nothing when there is no highlighted element

---

## Integration tests (Playwright)

- [x] Editor preview: activate inspect → click block → URL hash `#block-{uuid}-section` — `test_clicking_block_in_iframe_updates_editor_url_hash`
- [x] Userbar standalone preview: inspect control visible and block click navigation — `tests/e2e/test_standalone_preview.py`
- [x] Iframe reload: inspect usable after reload + re-toggle — `test_inspect_mode_usable_after_preview_iframe_reload`
- [x] Escape deactivates inspect (overlay removed) — `test_escape_key_deactivates_inspect_mode`
- [ ] Full keyboard flow: Tab through blocks, Enter to inspect (not covered end-to-end)
- [ ] Explicit flash-highlight assertion after navigation (optional)

---

## Acceptance criteria

- [ ] Python test suite covers every checkbox above (see remaining gaps, e.g. `render_as_block` integration)
- [x] JavaScript test suite covers all JS cases listed under `InspectMode`
- [ ] Tests run in CI on every push (no workflow files in repo yet)
