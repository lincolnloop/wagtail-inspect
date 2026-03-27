# Backlog & issues

Actionable tracking notes for maintenance, hardening, and test gaps. Resolved items are removed from this folder; a short archive list lives below.

## Open

| Topic                                             | File                                                                         |
| ------------------------------------------------- | ---------------------------------------------------------------------------- |
| Wagtail version compatibility & CI matrix         | [001-wagtail-version-compatibility.md](001-wagtail-version-compatibility.md) |
| Test suite gaps & CI                              | [002-no-test-suite.md](002-no-test-suite.md)                                 |
| Feature flag (`WAGTAIL_INSPECT_ENABLED`)          | [003-no-feature-flag.md](003-no-feature-flag.md)                             |
| Overlay z-index (CSS variable / Wagtail layering) | [007-hardcoded-z-index.md](007-hardcoded-z-index.md)                         |
| Inline script URL hardening                       | [012-template-script-injection.md](012-template-script-injection.md)         |

## Design reference (not backlog)

Long-form exploration of patching vs alternatives:

- [Monkey-patching alternatives](../monkey-patching-alternatives.md)

## Resolved (files removed)

These were addressed in code or docs; details stay in git history and in [Implementation review](../implementation-review.md#resolved-items).

| Topic                             | Resolution (summary)                                              |
| --------------------------------- | ----------------------------------------------------------------- |
| Resize / scroll overlay thrashing | Coalesced via `requestAnimationFrame` in `inspect-core.js`        |
| Userbar shadow DOM polling        | Replaced with `MutationObserver` in `userbar-inspect.js`          |
| Broken doc links / file map       | `README.md` and `docs/index.md` corrected                         |
| Middleware URL preview detection  | Removed; `ContextVar` via `PreviewableMixin.make_preview_request` |
| `ListValue` iteration & UUIDs     | `ListValue.__iter__` patch + `_ListChildProxy` in preview         |
