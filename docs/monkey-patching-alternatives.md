# Monkey-Patching Alternatives for Block Attribute Injection

**Labels:** `architecture`, `upstream`, `discussion`
**Priority:** High

## Description

The entire inspect feature depends on wrapping each rendered block with `data-block-id` and `data-block-label` attributes. Wagtail provides no extension point for this -- no hook, no signal, no template tag argument, no `Block.render()` wrapper mechanism.

The current approach patches three internal Wagtail methods. This works but creates version coupling to Wagtail internals (see [#001](issues/001-wagtail-version-compatibility.md)).

This document explores every alternative considered, from zero-patch approaches to hybrid strategies, with their trade-offs.

## Current Approach: 3 Monkey-Patches

Three Wagtail methods are patched in `patches.py`:

| Patched method                          | Template syntax covered                                 | Stability risk                                    | Wrapping condition                         |
| --------------------------------------- | ------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| `BoundBlock.render`                     | `{{ page.body }}`, `{% include_block page.body %}`      | Medium (`BoundBlock` is a semi-public base class) | `getattr(self, "id", None)` must be truthy |
| `BoundBlock.render_as_block`            | `{% for block in page.body %}{% include_block block %}` | Medium                                            | `getattr(self, "id", None)` must be truthy |
| `PreviewableMixin.make_preview_request` | (preview lifecycle, not a template)                     | Low (stable lifecycle method)                     | Always: sets `preview_active` ContextVar   |

Wrapping happens when `preview_active.get()` is `True` **and** the bound block carries a `.id` attribute. Only `StreamValue.StreamChild` and `ListValue.ListChild` instances carry a UUID; plain `BoundBlock` instances do not. This mirrors Wagtail's own rule that editor panels (`block-{uuid}-section`) are created only for UUID-bearing bound blocks.

**Why it was chosen:**

- Zero template changes, transparent to developers, preview-only.
- Patching `BoundBlock` (not `IncludeBlockNode`) covers both template rendering paths without requiring two entry-point patches.
- Automatically covers `ListChild` objects (UUID-bearing `ListBlock` items).
- The `ContextVar` (`preview_active`) set by the `make_preview_request` patch is async-safe and works even when no template context is available.

**Coverage:** Covers all template patterns: stream-level rendering (`{{ page.body }}`), explicit include (`{% include_block block %}`), and `ListBlock` items when iterated via `bound_blocks`. Templates that use plain Python attribute access to snippet sub-fields (`{{ block.value.body }}`) are not wrapped, since those UUIDs do not correspond to navigable editor panels.

**Root problems it causes:** [#001](issues/001-wagtail-version-compatibility.md), [#002](issues/002-no-test-suite.md).

---

## Alternatives Explored

### A. Custom `StreamBlock` Subclass

Override `StreamBlock.render_basic()` to wrap each child:

```python
class InspectableStreamBlock(StreamBlock):
    def render_basic(self, value, context=None):
        rendered = []
        for child in value:
            output = child.render(context=context)
            if hasattr(child, 'id') and child.id:
                output = _wrap_with_block_id(output, str(child.id), _get_block_label(child))
            rendered.append(output)
        return mark_safe("\n".join(rendered))
```

| Patches Wagtail? | Template changes?       | Coverage |
| ---------------- | ----------------------- | -------- |
| No               | Model definition change | Partial  |

**Covers:** `{% include_block page.content %}` and `{{ page.content }}` (entire stream rendering).

**Does NOT cover:** The most common pattern -- iterating children in templates:

```django
{% for block in page.content %}
    {% include_block block %}
{% endfor %}
```

Each child renders via `BoundBlock.render_as_block()` -> `Block.render()`, bypassing `StreamBlock.render_basic()`.

**Also requires:** Users to change model definitions to use `InspectableStreamBlock`.

---

### B. Custom Template Tag (`{% inspectable_include_block %}`)

Create a standalone template tag that wraps `{% include_block %}` logic:

```django
{% load wagtail_inspect_tags %}
{% for block in page.content %}
    {% inspectable_include_block block %}
{% endfor %}
```

The tag would resolve the block, render it via the standard path, then wrap the output with `data-block-id` if the block has an ID and we're in preview mode.

| Patches Wagtail? | Template changes?    | Coverage   |
| ---------------- | -------------------- | ---------- |
| No               | Yes (every template) | Where used |

**Covers:** Any rendering path where the tag is explicitly used.

**Does NOT cover:** `{{ streamfield }}` syntax (no template tag involved), third-party app templates that use `{% include_block %}`.

**Advantage:** Zero monkey-patching. The cleanest approach for projects that control all their templates.

**Disadvantage:** Doesn't work for third-party apps or `{{ streamfield }}`. Requires discipline to use everywhere.

---

### C. Fewer, More Stable Patches (Implemented)

Reduce to patches at the `BoundBlock` level, targeting more stable classes:

```python
# Patch BoundBlock.render — covers {{ page.body }} and {% include_block page.body %}
def patched_bound_block_render(self, context=None):
    return _wrap_if_preview(self, _original_bound_block_render(self, context=context))

# Patch BoundBlock.render_as_block — covers {% for block in page.body %}{% include_block block %}
def patched_bound_block_render_as_block(self, context=None):
    return _wrap_if_preview(self, _original_bound_block_render_as_block(self, context=context))

# Patch PreviewableMixin.make_preview_request — sets ContextVar for preview detection
def patched_make_preview_request(self, ...):
    token = preview_active.set(True)
    try:
        return _original_make_preview_request(self, ...)
    finally:
        preview_active.reset(token)
```

| Patches Wagtail? | Template changes? | Coverage                                  |
| ---------------- | ----------------- | ----------------------------------------- |
| Yes (3 methods)  | No                | Full coverage for all UUID-bearing blocks |

`BoundBlock` is a simpler, more public-facing class than `IncludeBlockNode`. Patching both `render` and `render_as_block` covers both rendering entry points without double-wrapping (the two methods never call each other). `PreviewableMixin.make_preview_request` is a lifecycle hook that is more stable than the previous thread-local/middleware approach.

**This is the current implementation.** See `patches.py`.

---

### D. Upstream Wagtail Contribution

Propose that Wagtail adds `data-block-id` and `data-block-type` attributes natively in preview mode:

- A flag on `StreamBlock` (`Meta.emit_block_ids = True`)
- A Wagtail setting (`WAGTAILSTREAMFIELD_EMIT_BLOCK_IDS`)
- A hook (`construct_block_output`) that fires after each block renders

| Patches Wagtail? | Template changes? | Coverage      |
| ---------------- | ----------------- | ------------- |
| No               | No                | 100% (native) |

**Long-term cleanest solution.** Would benefit the entire ecosystem (accessibility auditing, visual regression testing, content analytics).

**Depends on:** Wagtail maintainers accepting the proposal. The current monkey-patching code serves as a working proof of concept.

---

### E. Tag Registry Override (Django Public API)

Django's `Library.tags` is a public dictionary. We can replace the `include_block` compile function at the registry level without touching any Wagtail class internals:

```python
# In AppConfig.ready()
from wagtail.templatetags.wagtailcore_tags import register

original_compile = register.tags['include_block']

def inspectable_include_block(parser, token):
    node = original_compile(parser, token)
    return InspectableIncludeBlockNode(
        node.block_var, node.extra_context, node.use_parent_context
    )

register.tags['include_block'] = inspectable_include_block
```

Where `InspectableIncludeBlockNode` extends `IncludeBlockNode` and wraps the output:

```python
class InspectableIncludeBlockNode(IncludeBlockNode):
    def render(self, context):
        output = super().render(context)
        if not _is_preview(context):
            return output
        value = self.block_var.resolve(context)
        block_id = getattr(value, 'id', None)
        if not block_id:
            return output
        return _wrap_with_block_id(output, str(block_id), _get_block_label(value))
```

| Patches Wagtail?       | Template changes? | Coverage                   |
| ---------------------- | ----------------- | -------------------------- |
| No (Django public API) | No                | `{% include_block %}` only |

**Key insight:** This is NOT monkey-patching a Wagtail method. It uses Django's documented tag registration mechanism (`Library.tags` dict). The compile function signature is stable Django public API. We extend `IncludeBlockNode` via normal subclassing rather than replacing its method.

**Does NOT cover:** `{{ streamfield }}` syntax (no template tag involved).

---

### F. Hybrid: Tag Registry Override + Single StreamValue Patch

Combine Option E (tag registry) with a single patch on `StreamValue.__html__()`:

| Component                    | Mechanism         | Covers                                                         |
| ---------------------------- | ----------------- | -------------------------------------------------------------- |
| Tag registry override        | Django public API | `{% include_block field %}`, `{% include_block streamfield %}` |
| `StreamValue.__html__` patch | 1 Wagtail method  | `{{ streamfield }}`, `{{ child }}`                             |

| Patches Wagtail? | Template changes? | Coverage |
| ---------------- | ----------------- | -------- |
| Yes (1 method)   | No                | 100%     |

This reduces the Wagtail-internal patching surface from **4 methods to 1**, while the `{% include_block %}` path uses entirely standard Django mechanisms.

The one remaining patch (`StreamValue.__html__`) targets the `__html__` protocol, which is a well-established Python convention unlikely to change.

---

### G. Block Registry Iteration

Wagtail's `Block` base class maintains `Block.definition_registry` (a dict of all block instances by prefix). At startup, iterate all block subclasses and wrap their `render()` methods:

```python
import inspect
from wagtail.blocks import Block

def wrap_all_block_render_methods():
    for cls in _all_subclasses(Block):
        if 'render' in cls.__dict__:  # Only wrap if class defines its own render
            original = cls.render
            cls.render = _make_wrapped_render(original)
```

| Patches Wagtail?                     | Template changes? | Coverage               |
| ------------------------------------ | ----------------- | ---------------------- |
| Yes (systematic, but still patching) | No                | Individual blocks only |

**Problems:**

- `Block.render(value, context)` doesn't know the block's UUID -- the ID is on `StreamChild`, not on the block definition
- Need to traverse the full class hierarchy (`__subclasses__()` only returns direct subclasses)
- Still monkey-patching, just more systematically

**Verdict:** Not viable because block IDs are not available at the `Block.render()` level.

---

### H. `Block.__init_subclass__` Hook

Use Python's `__init_subclass__` on the base `Block` class to automatically modify all Block subclasses.

**Not viable:** Wagtail uses a metaclass (`BaseBlock`) instead of `__init_subclass__`. The metaclass handles `Meta` class construction. Adding `__init_subclass__` would conflict with the metaclass.

---

### I. Django Template Response Middleware

Use `TemplateResponse` middleware to post-process the rendered HTML.

**Not viable:** Template response middleware sees the final HTML string, not individual block outputs. Would require parsing HTML to identify and wrap blocks, which is fragile and doesn't know block IDs.

---

## Summary

| Option                                                     | Patches Wagtail internals | Template changes | Coverage                       | Viability                                      |
| ---------------------------------------------------------- | ------------------------- | ---------------- | ------------------------------ | ---------------------------------------------- |
| **Current (3 patches: BoundBlock + make_preview_request)** | 3 methods                 | None             | Full (all UUID-bearing blocks) | **Implemented**                                |
| **A. StreamBlock subclass**                                | None                      | Model change     | Partial                        | Limited use                                    |
| **B. Custom template tag**                                 | None                      | Every template   | Where used                     | Clean but incomplete                           |
| **C. BoundBlock + lifecycle patches**                      | 3 methods                 | None             | Full                           | **Implemented (this is the current approach)** |
| **D. Upstream Wagtail**                                    | None                      | None             | 100%                           | Best long-term                                 |
| **E. Tag registry override**                               | None                      | None             | `{% include_block %}` only     | Clean but incomplete                           |
| **F. Tag override + 1 patch**                              | 1 method                  | None             | 100%                           | Viable alternative                             |
| **G. Block registry iteration**                            | Systematic                | None             | Partial                        | Not viable (no block ID)                       |
| **H. `__init_subclass__`**                                 | N/A                       | N/A              | N/A                            | Not viable (metaclass)                         |
| **I. Template middleware**                                 | None                      | None             | N/A                            | Not viable (post-process)                      |

## Current Status

The implementation uses three patches:

1. `BoundBlock.render` -- covers stream-level rendering (`{{ page.body }}`, `{% include_block page.body %}`)
2. `BoundBlock.render_as_block` -- covers explicit iteration (`{% for block in page.body %}{% include_block block %}`)
3. `PreviewableMixin.make_preview_request` -- sets `preview_active` ContextVar for async-safe preview detection

The wrapping guard checks `getattr(self, "id", None)` on the bound block instance, which is truthy only for `StreamChild` and `ListChild` instances. This is derived from Wagtail's own JS-side `BaseSequenceChild` logic and replaces the earlier `isinstance(value, StreamValue.StreamChild)` check.

**Long-term:** Pursue **Option D** (upstream Wagtail contribution). The current code serves as a proof of concept demonstrating the value of block-level metadata in preview mode.

**For projects that control all templates:** **Option B** (custom template tag) is available as a zero-patch alternative, with the understanding that `{{ streamfield }}` and third-party templates won't be covered.

## Acceptance Criteria

- [x] This issue comprehensively documents all alternatives and why each was accepted or rejected
- [x] Refactored from `IncludeBlockNode.render` (1 patch) to `BoundBlock` (2 patches) + `make_preview_request` (1 patch) for better coverage and stability
- [ ] (Optional) Provide Option B (custom template tag) as an opt-in alternative
- [ ] (Optional) Open a Wagtail RFC for native block ID support in preview mode
