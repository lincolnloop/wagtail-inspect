# Wagtail Version Compatibility Risk

**Labels:** `risk`, `maintenance`, `upstream-dependency`
**Priority:** High

## Description

The library monkey-patches three Wagtail methods that are not part of Wagtail's public API:

| Patched method                          | Location                 | Risk level                       |
| --------------------------------------- | ------------------------ | -------------------------------- |
| `BoundBlock.render`                     | `wagtail.blocks`         | Medium -- semi-public base class |
| `BoundBlock.render_as_block`            | `wagtail.blocks`         | Medium -- semi-public base class |
| `PreviewableMixin.make_preview_request` | `wagtail.models.preview` | Low -- stable lifecycle method   |

These methods are implementation details of Wagtail's block rendering and preview pipeline. They may change signatures, move modules, or be removed entirely in future Wagtail releases without deprecation warnings.

The `README.md` states compatibility with Wagtail 5.x, 6.x, and 7.x, but there is no automated verification of this claim.

**Improvement over previous approach:** The original four patches targeted `IncludeBlockNode.render`, `StreamValue.render_as_block`, `StreamValue.__html__`, and `StreamChild.render` -- lower-level, more volatile internals. The current three patches target `BoundBlock` (a public base class) and `PreviewableMixin` (a lifecycle mixin), which are more stable and less likely to change without notice.

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

- Add a CI matrix that tests against multiple Wagtail versions (at minimum: latest stable, previous LTS).
- Monitor Wagtail's changelog for changes to `BoundBlock` and `PreviewableMixin`.

## Acceptance Criteria

- [x] `apply_patches()` logs a warning for untested Wagtail versions
- [x] Patch failures are handled gracefully (log error, skip patch, app still starts)
- [ ] CI tests run against at least two Wagtail versions
