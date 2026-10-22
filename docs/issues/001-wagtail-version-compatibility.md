# Wagtail Version Compatibility Risk

**Labels:** `risk`, `maintenance`, `upstream-dependency`
**Priority:** High

## Description

Inspect depends on monkey-patches of Wagtail APIs that are not guaranteed as stable public contracts. Since 0.2.0 most of them live in [wagtail-block-ids](https://github.com/lincolnloop/wagtail-block-ids); wagtail-inspect patches only `make_preview_request`:

| Patched method                          | Location                 | Patched by        | Risk level                       |
| --------------------------------------- | ------------------------ | ----------------- | -------------------------------- |
| `BoundBlock.render`                     | `wagtail.blocks`         | wagtail-block-ids | Medium -- semi-public base class |
| `BoundBlock.render_as_block`            | `wagtail.blocks`         | wagtail-block-ids | Medium -- semi-public base class |
| `ListValue.__iter__`                    | `wagtail.blocks.list_block` | wagtail-block-ids | Medium -- list iteration internals |
| `Page.serve` / `PreviewableMixin.serve_preview` | `wagtail.models`  | wagtail-block-ids | Low -- stable lifecycle methods  |
| `PreviewableMixin.make_preview_request` | `wagtail.models.preview` (or `wagtail.models` on older releases) | wagtail-inspect | Low -- stable lifecycle method   |

These are implementation details of Wagtail's block rendering and preview pipeline. They may change signatures, move modules, or be removed entirely in future Wagtail releases without deprecation warnings.

The `README.md` states compatibility with Wagtail 5.x, 6.x, and 7.x. **CI** runs backend + frontend + E2E tests on every push/PR; a full version matrix is also defined under `[tool.tox]` in `pyproject.toml` (`just tox` / `just tox-env …`).

**Improvement over previous approach:** The original four patches targeted `IncludeBlockNode.render`, `StreamValue.render_as_block`, `StreamValue.__html__`, and `StreamChild.render` -- lower-level, more volatile internals. The current approach centres on `BoundBlock` (two methods), adds `ListValue.__iter__` for list-block iteration, and uses `PreviewableMixin.make_preview_request` for preview lifecycle -- generally more stable than the earlier set.

## Current Mitigation

- `apply_patches()` (and wagtail-block-ids' `install()`) guard against double-application by checking whether the original method reference has already been saved.
- Original methods are stored in module-level `_originals` dicts and called through those references.
- Each patch is wrapped in `try/except` via `_apply_patch()` (in both packages), so a single failure is logged and skipped without crashing the app.
- wagtail-block-ids logs a warning if the Wagtail version is outside its tested range (`TESTED_WAGTAIL_VERSIONS` in `wagtail_block_ids.marks`).

## Risks

1. A Wagtail upgrade could silently break the patches (e.g., method signature change causing `TypeError`).
2. A Wagtail upgrade could rename or move the classes, causing an `ImportError` at startup.
3. ~~The patches run at `AppConfig.ready()`, so a breakage would prevent the entire Django application from starting.~~ (Mitigated: patches now fail gracefully.)

## Remaining Improvements

- Optional: extend **GitHub Actions** to a multi-version matrix (today’s `ci.yml` runs one resolved environment from the lockfile; `just tox` / `pyproject.toml` `[tool.tox]` already define Django × Wagtail combinations for local or scheduled runs).
- Monitor Wagtail’s changelog for changes to `BoundBlock`, `ListValue`, `Page.serve`, and `PreviewableMixin` (the first three mainly concern wagtail-block-ids).

## Acceptance Criteria

- [x] A warning is logged for untested Wagtail versions (now in wagtail-block-ids)
- [x] Patch failures are handled gracefully (log error, skip patch, app still starts)
- [ ] CI (or scheduled job) runs tests against at least two distinct Wagtail minor lines without manual `tox`
