# Wagtail Version Compatibility Risk

**Labels:** `risk`, `maintenance`, `upstream-dependency`
**Priority:** High

## Description

The library monkey-patches four Wagtail APIs that are not guaranteed as stable public contracts:

| Patched method                          | Location                 | Risk level                       |
| --------------------------------------- | ------------------------ | -------------------------------- |
| `BoundBlock.render`                     | `wagtail.blocks`         | Medium -- semi-public base class |
| `BoundBlock.render_as_block`            | `wagtail.blocks`         | Medium -- semi-public base class |
| `ListValue.__iter__`                    | `wagtail.blocks.list_block` | Medium -- list iteration internals |
| `PreviewableMixin.make_preview_request` | `wagtail.models.preview` (or `wagtail.models` on older releases) | Low -- stable lifecycle method   |

These are implementation details of Wagtail's block rendering and preview pipeline. They may change signatures, move modules, or be removed entirely in future Wagtail releases without deprecation warnings.

The `README.md` states compatibility with Wagtail 5.x, 6.x, and 7.x. **CI** runs backend + frontend + E2E tests on every push/PR; a full version matrix is also defined under `[tool.tox]` in `pyproject.toml` (`just tox` / `just tox-env …`).

**Improvement over previous approach:** The original four patches targeted `IncludeBlockNode.render`, `StreamValue.render_as_block`, `StreamValue.__html__`, and `StreamChild.render` -- lower-level, more volatile internals. The current approach centres on `BoundBlock` (two methods), adds `ListValue.__iter__` for list-block iteration, and uses `PreviewableMixin.make_preview_request` for preview lifecycle -- generally more stable than the earlier set.

## Current Mitigation

- `apply_patches()` guards against double-application by checking whether the original method reference has already been saved.
- Original methods are stored in module-level globals and called through those references.
- Each patch is wrapped in `try/except` via `_apply_patch()`, so a single failure is logged and skipped without crashing the app.
- A version check logs a warning if the Wagtail version is outside the tested range (`TESTED_WAGTAIL_VERSIONS`).

## Risks

1. A Wagtail upgrade could silently break the patches (e.g., method signature change causing `TypeError`).
2. A Wagtail upgrade could rename or move the classes, causing an `ImportError` at startup.
3. ~~The patches run at `AppConfig.ready()`, so a breakage would prevent the entire Django application from starting.~~ (Mitigated: patches now fail gracefully.)

## Remaining Improvements

- Optional: extend **GitHub Actions** to a multi-version matrix (today’s `ci.yml` runs one resolved environment from the lockfile; `just tox` / `pyproject.toml` `[tool.tox]` already define Django × Wagtail combinations for local or scheduled runs).
- Monitor Wagtail’s changelog for changes to `BoundBlock`, `ListValue`, and `PreviewableMixin`.

## Acceptance Criteria

- [x] `apply_patches()` logs a warning for untested Wagtail versions
- [x] Patch failures are handled gracefully (log error, skip patch, app still starts)
- [ ] CI (or scheduled job) runs tests against at least two distinct Wagtail minor lines without manual `tox`
