# No Feature Flag to Disable Without Uninstalling

**Labels:** `enhancement`, `configuration`
**Priority:** Low

## Description

There is no Django setting to disable the inspect feature without removing the app from `INSTALLED_APPS`. In production environments or during debugging, operators may want to temporarily disable the patches and UI without modifying `INSTALLED_APPS` and restarting.

## Current Behavior

The only way to disable the feature is to remove `"wagtail_inspect"` from `INSTALLED_APPS`, which requires a settings change and a server restart.

## Suggested Implementation

Add a setting like `WAGTAIL_INSPECT_ENABLED` (default `True`):

```python
# settings.py
WAGTAIL_INSPECT_ENABLED = False
```

Check this in three places:

1. **`apply_patches()`** -- Skip patching if disabled
2. **`global_admin_css()` / `global_admin_js()`** -- Skip asset injection if disabled
3. **`add_inspect_blocks_item()`** -- Skip userbar item if disabled

## Acceptance Criteria

- [ ] A `WAGTAIL_INSPECT_ENABLED` setting controls whether the feature is active
- [ ] When disabled, no patches are applied, no assets are injected, and no userbar item appears
- [ ] Default is `True` (opt-out, not opt-in)
