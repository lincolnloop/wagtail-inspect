# Architecture Overview

This document describes how the Wagtail Inspect plugin is structured, how data flows through it, and how its components interact.

## Core Idea

Wagtail renders StreamField content as plain HTML -- there is no built-in way to trace a rendered block back to the editor panel that produced it. This plugin closes that gap by:

1. **Tagging** every rendered `BoundBlock` with `data-block-id`, `data-block-type`, and `data-block-label` attributes (Python-side monkey-patches on `BoundBlock.render`, `BoundBlock.render_as_block`, and `ListValue.__iter__`).
2. **Augmenting** any blocks the Python patches missed (e.g. blocks rendered via `django-includecontents` or raw template loops) using `inspect-augment.js`, which reads a block map built from the page's data model by `block_map.py`.
3. **Signalling** preview mode via a `ContextVar` set by a patch on `PreviewableMixin.make_preview_request`, rather than thread-local state or URL matching.
4. **Detecting** those tagged elements in the preview and letting the user hover/click them (JavaScript-side controllers).
5. **Navigating** from the clicked block back to the correct editor section in the Wagtail admin (DOM traversal, panel expansion, scroll, flash highlight).

## High-Level Component Map

```mermaid
graph TD
  subgraph python ["Python (server-side)"]
    Init["__init__.py\npreview_active ContextVar\n_preview_block_maps cache"]
    AppConfig["apps.py\nWagtailInspectConfig"]
    Patches["patches.py\napply_patches()"]
    BlockMap["block_map.py\nflat_block_map_for_instance"]
    Views["views.py\nPageInspectView"]
    Hooks["wagtail_hooks.py\nhooks + InspectBlocksUserbarItem"]
    Template["item_inspect_preview.html"]
  end

  subgraph js ["JavaScript (client-side)"]
    InspectCore["inspect-core.js\nInspectMode"]
    AugmentJS["inspect-augment.js\nWagtailInspectAugment"]
    PreviewCtrl["preview-inspect-controller.js\nPreviewInspectController"]
    UserbarCtrl["userbar-inspect.js\nInspectController"]
  end

  subgraph css ["CSS"]
    Styles["preview-inspect.css"]
  end

  subgraph wagtail ["Wagtail Framework"]
    StimulusApp["Stimulus Application"]
    WagtailHooks["Hook Registry"]
    BlockRendering["Block Rendering\n(BoundBlock.render / render_as_block)"]
    PreviewMixin["PreviewableMixin.make_preview_request"]
    UserbarShadow["Userbar (Shadow DOM)"]
  end

  AppConfig -->|"ready()"| Patches
  Patches -->|"monkey-patches"| BlockRendering
  Patches -->|"monkey-patches"| PreviewMixin
  Patches -->|"reads / sets"| Init
  Patches -->|"imports"| BlockMap

  PreviewMixin -->|"after render: snapshots"| Init
  BlockMap --> Init

  Views -->|"reads _preview_block_maps"| Init
  Views -->|"imports"| BlockMap

  Hooks -->|"insert_global_admin_css"| WagtailHooks
  Hooks -->|"insert_global_admin_js"| WagtailHooks
  Hooks -->|"insert_global_admin_js\n(window.wagtailInspectConfig)"| PreviewCtrl
  Hooks -->|"register_admin_urls"| Views
  Hooks -->|"construct_wagtail_userbar"| WagtailHooks

  Hooks --> Template
  Template -->|"loads dynamically"| InspectCore
  Template -->|"loads dynamically"| AugmentJS
  Template -->|"loads dynamically"| UserbarCtrl

  WagtailHooks -->|"injects"| Styles
  WagtailHooks -->|"injects"| InspectCore
  WagtailHooks -->|"injects"| PreviewCtrl

  PreviewCtrl -->|"new InspectMode(iframeDoc)"| InspectCore
  UserbarCtrl -->|"new InspectMode(document)"| InspectCore

  PreviewCtrl -->|"registers with"| StimulusApp
  UserbarCtrl -->|"attaches to"| UserbarShadow

  PreviewCtrl -->|"GET /wagtail-inspect/api/page/{id}/"| Views
  PreviewCtrl -->|"injects into iframe, calls"| AugmentJS
  UserbarCtrl -->|"GET /wagtail-inspect/api/page/{id}/"| Views
  UserbarCtrl -->|"calls"| AugmentJS

  BlockRendering -->|"produces data-block-id HTML"| PreviewCtrl
  BlockRendering -->|"produces data-block-id HTML"| UserbarCtrl
```

## Two Integration Modes

The plugin operates in two distinct contexts, each with its own JavaScript controller. Both controllers delegate the visual inspect experience to the shared `InspectMode` class:

```mermaid
graph LR
  subgraph cmsAdmin ["CMS Admin (edit page)"]
    EditorPanel["Editor Panel"]
    PreviewPanel["Preview Panel (iframe)"]
    ToolbarButton["Inspect Button (toolbar)"]
  end

  subgraph standalonePrev ["Standalone Preview Page"]
    PageContent["Page Content"]
    Userbar["Wagtail Userbar (Shadow DOM)"]
    UserbarButton["Inspect Blocks (menu item)"]
  end

  ToolbarButton -->|"activates"| PreviewInspectController
  PreviewInspectController -->|"new InspectMode(iframeDoc)"| InspectMode
  InspectMode -->|"highlights blocks in"| PreviewPanel
  PreviewInspectController -->|"navigates to block"| EditorPanel

  UserbarButton -->|"activates"| InspectController
  InspectController -->|"new InspectMode(document)"| InspectMode2["InspectMode"]
  InspectMode2 -->|"highlights blocks in"| PageContent
  InspectController -->|"redirects to"| cmsAdmin
```

### Mode 1: CMS Preview Panel (iframe)

Used when an editor has the page open in the Wagtail admin at `/cms/pages/{id}/edit/` and toggles the side preview panel.

- **Controller**: `PreviewInspectController` (Stimulus)
- **Where it runs**: In the admin page, interacting with the preview iframe's document
- **InspectMode target**: `iframe.contentDocument` (cross-frame)
- **Navigation**: In-page -- finds the `[data-contentpath]` element in the editor panel, expands collapsed panels, scrolls to it, and flashes a highlight
- **File**: `preview-inspect-controller.js`

### Mode 2: Standalone Preview Page (userbar)

Used when an editor opens the full preview at `/cms/pages/{id}/edit/preview/`.

- **Controller**: `InspectController` (plain JS)
- **Where it runs**: Directly on the preview page's document
- **InspectMode target**: `document` (same frame)
- **Navigation**: Full-page redirect to `/cms/pages/{id}/edit/#block-{uuid}-section`
- **File**: `userbar-inspect.js`

## Block Rendering Pipeline

The Python side patches Wagtail's block rendering so that every `BoundBlock` with a UUID has its HTML output annotated with `data-block-*` attributes. This happens at Django startup time via the `AppConfig.ready()` hook.

```mermaid
flowchart TD
  A["Django starts"] --> B["AppConfig.ready()"]
  B --> C["patches.apply_patches()"]
  C --> D1["Patch BoundBlock.render"]
  C --> D2["Patch BoundBlock.render_as_block"]
  C --> D3["Patch ListValue.__iter__"]
  C --> D4["Patch PreviewableMixin.make_preview_request"]

  subgraph previewRequest ["At preview request time"]
    PR["make_preview_request() called"]
    PR --> CV["preview_active.set(True)\n(ContextVar)"]
    CV --> SR["serve_preview() renders template"]
    SR --> BM["flat_block_map_for_instance(self)\nsnapshot into _preview_block_maps"]
    BM --> FN["preview_active.reset(token)\n(in finally)"]
  end

  subgraph rendering ["At render time"]
    E1["{{ page.body }} or {% include_block page.body %}"] --> F1["StreamBlock.render_basic\n→ child.render(context)"]
    E2["{% for block in page.body %}{% include_block block %}"] --> F2["IncludeBlockNode\n→ block.render_as_block(context)"]

    F1 --> G["patched_bound_block_render\n(or render_as_block)"]
    F2 --> G

    G --> H{"preview_active.get()\nand self.id?"}
    H -- Yes --> I["_wrap_if_preview():\nAnnotate output with\ndata-block-id / type / label"]
    H -- No --> J["Return original output unchanged"]
  end

  CV -.->|"ContextVar visible\nto all nested calls"| H
```

### Three Patches, Two Rendering Entry Points

Two `BoundBlock` methods are patched because Wagtail templates use two distinct rendering paths:

| Template syntax                                         | Wagtail method patched       | Patch function                        | Notes                                               |
| ------------------------------------------------------- | ---------------------------- | ------------------------------------- | --------------------------------------------------- |
| `{{ page.body }}` or `{% include_block page.body %}`    | `BoundBlock.render`          | `patched_bound_block_render`          | Called by `StreamBlock.render_basic` for each child |
| `{% for block in page.body %}{% include_block block %}` | `BoundBlock.render_as_block` | `patched_bound_block_render_as_block` | Called by `IncludeBlockNode` when iterating         |

Both methods delegate to `self.block.render(self.value, context)` internally; they never call each other, so there is no double-annotation.

### Preview Detection via ContextVar

Preview detection uses a `ContextVar[bool]` named `preview_active` (defined in `__init__.py`), set by patching `PreviewableMixin.make_preview_request`:

```mermaid
sequenceDiagram
  participant Wagtail as Wagtail Preview
  participant Patch as patched_make_preview_request
  participant CV as preview_active (ContextVar)
  participant Render as BoundBlock.render
  participant Cache as _preview_block_maps

  Wagtail->>Patch: make_preview_request(...)
  Patch->>CV: preview_active.set(True)
  Patch->>Wagtail: serve_preview() [renders template]
  Wagtail->>Render: child.render(context)
  Render->>CV: preview_active.get() → True
  Render->>Render: annotate output with data-block-id
  Patch->>Cache: _preview_block_maps[pk] = flat_block_map_for_instance(self)
  Patch->>CV: preview_active.reset(token) [in finally]
```

`ContextVar` is async-safe (unlike `threading.local`) and is visible to all rendering calls in the same execution context without requiring a template context argument.

The block map snapshot is taken **after** `serve_preview()` returns, at which point `self` has been updated with form-submitted field data. This means the map's UUIDs match those in the just-rendered DOM, even when Wagtail's form round-trip produces different UUIDs from the saved revision.

### Why `BoundBlock` Instead of `IncludeBlockNode`

`BoundBlock` is the common base class of both `StreamValue.StreamChild` and `ListValue.ListChild`. Patching at this level:

- Covers **both** rendering entry points (`render` for stream-level iteration, `render_as_block` for explicit `{% include_block %}`).
- **Automatically covers `ListChild`** objects (UUID-bearing `ListBlock` items), which `IncludeBlockNode` patching missed.
- Guards against wrapping by checking `getattr(self, "id", None)` — plain `BoundBlock` instances with no `.id` are silently skipped.

### Block Annotation Strategy

Block metadata is attached to the DOM using a three-path strategy in `_wrap_if_preview`:

**Primary — attribute injection:** `_inject_attrs_into_root` locates the first HTML element in the rendered output via a compiled regex and inserts `data-block-id`, `data-block-type`, and `data-block-label` directly into that element's opening tag. No wrapper element is emitted, so CSS Grid and Flexbox layouts are completely unaffected.

```html
<!-- Before annotation -->
<section class="hero">…</section>

<!-- After annotation -->
<section data-block-id="…" data-block-type="hero" data-block-label="Hero" class="hero">…</section>
```

**Multi-root wrapper:** when the rendered output contains more than one top-level HTML element (e.g. a markdown block rendered as several sibling `<p>` tags), injecting on the first tag would only annotate part of the block. In this case, a `<div style="display:contents">` wrapper is emitted around the full fragment so the whole block shares one `data-block-id`. `_is_multi_root_fragment` (backed by `_RootCounter`, an `HTMLParser` subclass) detects this case in a single pass.

**Text-only fallback:** when the block output contains no HTML element (e.g. a bare `CharBlock` rendering plain text), the same `<div style="display:contents">` wrapper is used. Text-only output cannot be a grid item, so layout impact is moot.

`_getBlockRect()` in `InspectMode` handles all three cases:

```javascript
_getBlockRect(element) {
    const rect = element.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) return rect;
    // Fallback for display:contents wrappers — union direct child rects
    // (Range API only as last resort for text-only wrappers with no element children)
    ...
}
```

## Block Map Augmentation Pipeline

Some blocks are invisible to the Python rendering patches because their DOM elements are created by template code that doesn't call `BoundBlock.render` or `BoundBlock.render_as_block` (e.g. `django-includecontents` components, or raw `{% for item in value.items %}` loops without `{% include_block %}`). The augmentation pipeline handles these:

```mermaid
sequenceDiagram
  participant Controller as JS Controller
  participant API as PageInspectView
  participant Cache as _preview_block_maps
  participant Augment as inspect-augment.js
  participant DOM as Preview DOM

  Controller->>API: GET /wagtail-inspect/api/page/{id}/
  API->>Cache: lookup _preview_block_maps[pk]
  Cache-->>API: block map (matches live DOM UUIDs)
  API-->>Controller: { blocks: { uuid: { type, label, children } } }
  Controller->>Augment: augmentPreviewBlocks(blocks)
  Augment->>DOM: find unannotated child elements
  Augment->>DOM: set data-block-id / type / label
  Augment->>DOM: repair empty labels on already-annotated elements
```

`PreviewInspectController` additionally injects `inspect-augment.js` into the preview iframe before calling `augmentPreviewBlocks`, since the script must run inside the same document as the DOM it is annotating.

## Inspect Mode Interaction Flow

### CMS Preview Panel

```mermaid
sequenceDiagram
  participant Editor as Editor (user)
  participant Button as Inspect Button
  participant Ctrl as PreviewInspectController
  participant IM as InspectMode
  participant IFrame as Preview Iframe
  participant Admin as Editor Panel

  Editor->>Button: Click crosshairs icon
  Button->>Ctrl: toggleInspectMode()
  Ctrl->>IM: new InspectMode(iframeDoc, callbacks)
  Ctrl->>IM: activate()
  IM->>IFrame: Inject cursor style, overlay, ARIA attributes
  IM->>IFrame: Attach mouse/keyboard/focus listeners

  Editor->>IFrame: Move mouse over content
  IFrame-->>IM: mouseover event
  IM->>IM: _findBlockElement(target)
  IM->>IFrame: Position overlay + show label

  Editor->>IFrame: Click on highlighted block
  IFrame-->>IM: click event (preventDefault)
  IM-->>Ctrl: onBlockClick(blockId)
  Ctrl->>Ctrl: deactivateInspectMode()
  Ctrl->>Admin: navigateToBlock(blockId)
  Admin->>Admin: expandCollapsedAncestors()
  Admin->>Admin: scrollIntoView({ smooth })
  Admin->>Admin: flashHighlight()
```

### Standalone Preview Page

```mermaid
sequenceDiagram
  participant Editor as Editor (user)
  participant UB as Userbar (Shadow DOM)
  participant Ctrl as InspectController
  participant IM as InspectMode
  participant Doc as Page Document

  Editor->>UB: Open userbar menu
  Editor->>UB: Click "Inspect blocks"
  UB->>Ctrl: toggle()
  Ctrl->>IM: new InspectMode(document, callbacks)
  Ctrl->>IM: activate()
  IM->>Doc: Inject cursor style, overlay, ARIA attributes
  IM->>Doc: Attach mouse/keyboard/focus listeners

  Editor->>Doc: Hover over block
  Doc-->>IM: mouseover event
  IM->>Doc: Position overlay + show label

  Editor->>Doc: Click on block
  Doc-->>IM: click event (preventDefault)
  IM-->>Ctrl: onBlockClick(blockId)
  Ctrl->>Ctrl: deactivate()
  Ctrl-->>Editor: Redirect to /cms/pages/{id}/edit/#block-{uuid}-section
```

## Theme Bridging

The inspect overlay needs to match Wagtail's active theme (light, dark, or auto). Since the preview iframe may not have Wagtail's CSS variables, `InspectMode` bridges the theme at activation time:

```mermaid
flowchart LR
  subgraph admin ["Admin Document"]
    CSSVars["--w-color-secondary\n--w-color-text-button"]
  end

  subgraph core ["InspectMode._resolveColors()"]
    Read["Read CSS variables\nfrom parent/admin doc"]
    Fallback["Fallback to defaults\n(#007D7E, #fff)"]
  end

  subgraph preview ["Preview Document"]
    Inject["Inject as:\n--wagtail-inspect-color\n--wagtail-inspect-bg\n--wagtail-inspect-label-color"]
  end

  admin -->|"getComputedStyle()"| Read
  Read -->|"values found"| Inject
  Read -->|"cross-origin or missing"| Fallback
  Fallback --> Inject
```

## Cross-Frame Communication

- **Standalone preview** (`userbar-inspect.js`): the userbar runs on the preview page; clicking a block sets `window.location` to the edit URL with `#block-{uuid}-section` (full navigation, no `postMessage`).
- **Editor preview panel** (`preview-inspect-controller.js`): `InspectMode` runs in the **iframe** document; clicking a block calls `navigateToBlock()` in the **parent** admin window (same process, direct DOM access — no `postMessage` for navigation). `inspect-augment.js` is injected into the iframe so it runs in the iframe's document context and can annotate the iframe's DOM directly.

## URL Hash Convention

The plugin uses a URL hash format to deep-link to specific blocks:

```
#block-{uuid}-section
```

This hash is:

- Set by `navigateToBlock()` via `history.pushState()` in the CMS admin
- Used as the target anchor when the userbar redirects to the edit page
- Detected on page load by `scrollToHashBlock()` to auto-navigate after redirect (uses instant scroll to avoid layout-shift interference from Wagtail's side panels)

## Data Attributes Reference

| Attribute                             | Where                                                            | Purpose                                                                           |
| ------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `data-block-id`                       | Preview HTML (block root element, or `display:contents` wrapper) | UUID of the StreamField block                                                     |
| `data-block-type`                     | Preview HTML (same element)                                      | Block type slug (e.g., `"hero"`, `"stat_list_block"`)                             |
| `data-block-label`                    | Preview HTML (same element)                                      | Human-readable block label (e.g., "Hero", "Stat List")                            |
| `data-contentpath`                    | Admin editor panel                                               | Wagtail's native attribute on block editor sections, value matches the block UUID |
| `data-controller`                     | Admin preview panel                                              | Stimulus controller identifier (`w-preview preview-inspect`)                      |
| `data-w-preview-target`               | Admin preview panel                                              | Stimulus target for the preview iframe (`iframe`)                                 |
| `data-preview-inspect-button`         | Admin preview toolbar                                            | Marker on the injected inspect button                                             |
| `data-wagtail-inspect-userbar-target` | Userbar template                                                 | Target for the inspect trigger button (`trigger`)                                 |
