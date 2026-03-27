# Template Script URL Injection Pattern

**Labels:** `security`, `hardening`
**Priority:** Low

## Description

In `item_inspect_preview.html` (lines 37-38), static file URLs are rendered directly inside an inline `<script>` tag using Django template variables:

```html
<script>
  (function() {
    function loadScript(url, callback) { ... }
    loadScript('{{ core_js_url }}', function() {
      loadScript('{{ userbar_js_url }}');
    });
  })();
</script>
```

While `core_js_url` and `userbar_js_url` come from Django's `static()` helper (which produces trusted, predictable URLs), the pattern of injecting values into inline JavaScript without escaping is fragile. If the static URL configuration were ever compromised or if someone modified the context variable to include a single quote, it could enable script injection.

## Current Mitigation

- The values are produced by `django.templatetags.static.static()`, which is a trusted source.
- The template is only rendered for authenticated admin users with edit permissions.

## Suggested Hardening

Use Django's `escapejs` filter or `json_script` to safely pass URLs to JavaScript:

```html
{{ core_js_url|json_script:"inspect-core-url" }} {{ userbar_js_url|json_script:"inspect-userbar-url"
}}
<script>
  (function () {
    var coreUrl = JSON.parse(document.getElementById("inspect-core-url").textContent);
    var userbarUrl = JSON.parse(document.getElementById("inspect-userbar-url").textContent);
    // ...
  })();
</script>
```

Or more minimally, use `escapejs`:

```html
loadScript('{{ core_js_url|escapejs }}', function() { loadScript('{{ userbar_js_url|escapejs }}');
});
```

## Acceptance Criteria

- [ ] Template variables inside `<script>` blocks are properly escaped
- [ ] No behavior change in script loading
