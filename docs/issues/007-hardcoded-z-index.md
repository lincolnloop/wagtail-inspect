# Hardcoded z-index: 999999

**Labels:** `cleanup`, `css`
**Priority:** Low
**Status:** **Partially addressed** — Overlay stacking is no longer set from JavaScript. `#wagtail-inspect-overlay` uses `z-index: 999999` in `preview-inspect.css`, next to the other overlay rules (single place to edit or override in project CSS). A dedicated `--wagtail-inspect-z-index` token is still optional.

## Description (historical)

The overlay previously used an inline style in `inspect-core.js` with `z-index: 999999`. That duplicated layout concerns in JS and was hard to override.

Current code defines stacking in CSS:

```css
#wagtail-inspect-overlay {
  position: fixed;
  pointer-events: none;
  z-index: 999999;
  ...
}
```

The value could still conflict with other admin overlays, modals, or plugins that use similarly high z-index values.

## Context

Wagtail itself uses specific z-index layers for its admin UI (e.g., side panels, modals, userbar). The overlay needs to sit above page content in the preview but should not interfere with Wagtail's own layering.

## Suggested Improvements

1. Use a CSS custom property (`--wagtail-inspect-z-index: 999999`) so it can be overridden.
2. Document the chosen value and the reasoning (must be above preview content but below Wagtail modals).
3. Consider aligning with Wagtail's z-index scale if one exists.

## Acceptance Criteria

- [x] The z-index value lives in CSS (`preview-inspect.css`) and can be overridden by project stylesheets
- [ ] Optional: expose `--wagtail-inspect-z-index` (or similar) for one-line theming
- [ ] No z-index conflicts with Wagtail's built-in overlays (not formally verified)
