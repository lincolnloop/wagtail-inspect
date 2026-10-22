# Test coverage & CI follow-ups

**Labels:** `testing`, `risk`, `quality`
**Priority:** Medium

## Status

Test infrastructure is in place (pytest, pytest-django, demo `testproject` / `testapp` models,
`RequestFactory` used for view tests). Core Python, JavaScript (Bun), and Playwright E2E tests
run locally via `just test` / `just test-all`.

**CI:** [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs on pushes and pull requests to `main`: dependency install, `just pre-commit --all-files`, `just lint --no-fix`, Playwright Chromium + `just test-all`, and `uv build`. This issue tracks **remaining coverage gaps** (see checklists below), not absence of automation.

Userbar visibility is enforced in `add_inspect_blocks_item()` (`construct_wagtail_userbar` hook)
with early returns — see `test_wagtail_hooks.py`.

---

## Python test cases (pytest / Django TestCase)

### `patches.py` — preview patch and live-page marker

Marking itself (`data-block-*` output, wrappers, `ListValue` proxies) is tested in wagtail-block-ids. The earlier `_wrap_if_preview` / `preview_active` tests went with it.

- [x] `make_preview_request` renders inside a wrapping marking scope — `test_make_preview_request_renders_inside_a_wrapping_scope`
- [x] Unknown kwargs are forwarded to the original — `test_patched_make_preview_request_forwards_unknown_kwargs`
- [x] The editor's preview map is remembered (positional and keyword request) — `test_make_preview_request_remembers_the_editors_preview`
- [x] No request → nothing remembered — `test_make_preview_request_without_a_request_remembers_nothing`
- [x] Marking scope closed when the original raises — `test_marking_always_closed_when_original_raises`
- [x] Live-page marker: editors yes, others no, setting respected — `test_live_page_marker_*`
- [x] `apply_patches()` registers the marker once and is idempotent — `test_apply_patches_registers_the_wrapping_live_marker_once`, `test_apply_patches_is_idempotent`

### `block_map.py` / `views.py`

- [x] Flat map: stream children, list children, order, empty stream, missing ids — `test_flat_block_map_*`
- [x] `block_map_for`: page without revision, latest revision, editor's last preview, `live` — `test_block_map_for_*`
- [x] Preview maps kept per editor; `remember_preview` needs a pk and an authenticated user — `test_previews_are_kept_per_editor`, `test_remember_preview_needs_*`
- [x] Deprecated walk re-exports warn — `test_walk_reexports_are_deprecated`
- [x] API: 401 / 403 / 404, editor's last preview, `?source=live` — `tests/backend/test_views.py`

### `wagtail_hooks.py` — `add_inspect_blocks_item` / `InspectBlocksUserbarItem`

- [x] Item added on preview and on live pages for editors — `test_adds_item_on_preview_for_editors`, `test_adds_item_on_live_pages_for_editors`
- [x] `WAGTAIL_INSPECT_LIVE_PAGES = False` keeps it off live pages only — `test_live_pages_can_be_switched_off`
- [x] Item skipped for anonymous users, non-editors, the preview panel, unsaved pages, and no page — `test_skips_item` (parametrized), `test_add_inspect_blocks_item_skips_preview_panel`
- [x] `get_context_data()` includes `inspect_preview_context` (`pageId`, `editUrl`, `apiUrl`, `cssUrl`); live item asks for `?source=live` — `test_get_context_data_includes_api_urls`, `test_live_item_requests_the_live_block_map`
- [x] Userbar `media` loads scripts in dependency order, no inline script — `test_userbar_item_media_loads_scripts_in_dependency_order`, `test_userbar_item_renders_no_inline_script`
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

- [x] Python test suite covers every Python checkbox above (marking itself is covered in wagtail-block-ids)
- [x] JavaScript test suite covers all JS cases listed under `InspectMode`
- [x] Tests run in CI on every push / PR to `main` (see `ci.yml`)
