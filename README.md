# wagtail-inspect

Block inspection tools for the Wagtail CMS preview panel.

There are two ways to use it: a crosshairs button in the **editor’s preview panel** (next to the preview size controls), and **Inspect blocks** in the Wagtail userbar on **standalone preview** pages (`…/edit/preview/`). Both turn on inspect mode so you can point at a block in the rendered page and jump to that block in the page editor.

## Requirements

- Python 3.12+
- Django 4.2+
- Wagtail 5, 6, or 7

## Installation

To use **wagtail-inspect** in your own Wagtail project (not the demo `testproject` in this repo), install the package into that project’s environment, then follow **[Configuration](#configuration)**.

<!--
**Published package** — When the project is on PyPI, use **[Installation](#installation)** (`pip install wagtail-inspect`).
-->

**Wheel from a GitHub Release** — Each [release](https://github.com/lincolnloop/wagtail-inspect/releases) includes build assets: download **`wagtail_inspect-<version>-py3-none-any.whl`** (or the `.tar.gz` sdist). From your site’s activated virtualenv:

```bash
pip install /path/to/wagtail_inspect-0.1.0-py3-none-any.whl
```

With [uv](https://docs.astral.sh/uv/): `uv pip install /path/to/wagtail_inspect-0.1.0-py3-none-any.whl`.

**Wheel from CI** — Successful runs of the **CI** workflow upload a **`dist`** artifact containing the same wheel and sdist; download it from the run’s **Summary** tab if you need a build that is not yet tagged.

**Editable install from a local clone** — While developing the library alongside your site:

```bash
pip install -e /path/to/wagtail-inspect
```

(or `uv pip install -e /path/to/wagtail-inspect`). The package root is the repository directory (the layout uses `src/`; `pyproject.toml` defines the build).

<!--

```bash
pip install wagtail-inspect
```
-->

## Configuration

Add `wagtail_inspect` to your `INSTALLED_APPS` **after** Wagtail's own apps:

```python
INSTALLED_APPS = [
    # ...
    "wagtail.admin",
    "wagtail",
    # ...
    "wagtail_inspect",
]
```

No URL configuration is required — the block-map JSON API registers itself via Wagtail's `register_admin_urls` hook under your existing Wagtail admin prefix (`/wagtail-inspect/api/page/<id>/`). There are no plugin settings or feature flags; installing the app enables the behaviour.

**List iteration:** `apply_patches()` replaces `ListValue.__iter__` during preview only so `{% for x in value.items %}{% include_block x %}` yields inspectable list children (aligned with `.bound_blocks`). Outside preview, iteration matches stock Wagtail. If a template treats the loop variable as a plain value, use `x.value` or `{% include_block x %}` instead.

## How it works

- **Preview-only wrapping:** A patch on `PreviewableMixin.make_preview_request` sets a `ContextVar` for the lifetime of each preview response. Monkey-patches on `BoundBlock.render` / `render_as_block` inject `data-block-id`, `data-block-type`, and `data-block-label` on rendered output when that flag is set (single-root injection, or a `display:contents` wrapper when the block renders multiple roots or plain text).
- **Authoritative block map:** The server walks the page’s StreamField data (`block_map.py`) and exposes a flat UUID → `{type, label, …}` map via the admin JSON API. The same walk is snapshotted during `make_preview_request` so the API matches the form-driven preview session (including unsaved edits).
- **DOM augmentation in the preview document:** Templates that bypass `{% include_block %}` (e.g. `django-includecontents` `django-cotton` and similar packages, or `{% for item in value.items %}` without `include_block`) never hit the BoundBlock patches. **`inspect-augment.js` therefore runs in the same document as the rendered preview** — the full preview page or the editor preview **iframe** — reads the block map from the API, and adds `data-block-*` where Python could not. That avoids cross-frame `postMessage` for annotation: the script sees the DOM it is meant to label.
- **Loading augment + controllers:** In the editor, a Stimulus controller (`preview-inspect-controller.js`) fetches the map on each iframe load, injects `inspect-augment.js` into the iframe, then calls `augmentPreviewBlocks`. On standalone preview, the userbar template uses a small inline script to chain-load CSS and JS in order, because Wagtail clones userbar items from a `<template>` into shadow DOM and external `<script src>` / `<link>` tags in that template do not execute when cloned.
- **Shared inspect UX:** `inspect-core.js` implements `WagtailInspectMode` (overlay highlight, keyboard access, click → block id). The preview-panel controller drives navigation inside the edit UI (expand panels, scroll, flash). The userbar controller navigates with `…/edit/#block-{uuid}-section`.

## Development

### Setup

Requires [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh), and [just](https://just.systems).

```bash
git clone https://github.com/lincolnloop/wagtail-inspect.git
cd wagtail-inspect
just install
```

### Run locally

From the repo root, start the bundled **`testproject`** demo site:

```bash
just run-with-fixture
```

That runs migrations and `runserver` (by default **http://127.0.0.1:8000/**). Open the Wagtail admin at **http://127.0.0.1:8000/cms/**.

On a fresh database, migration **`testapp.0004`** creates a superuser with username **`admin`** and password **`admin`**. The same account appears in **`tests/e2e/fixtures/test_data.json`**; if you load that fixture (**`just run-with-fixture`**, **`LOAD_E2E_FIXTURE=1 just run`**, or **`just load-fixture`**), log in with **`admin`** / **`admin`** there too. These credentials are only for local development.

### Common commands

| Command                       | Description                                                     |
| ----------------------------- | --------------------------------------------------------------- |
| `just test`                   | Run all tests (backend + frontend)                              |
| `just test-all`               | Backend + frontend + Playwright E2E                             |
| `just test-backend`           | Python/Django tests only                                        |
| `just test-frontend`          | JavaScript tests only (Bun)                                     |
| `just test-frontend-watch`    | JavaScript tests in watch mode                                  |
| `just test-e2e`               | Playwright E2E tests (needs `just install-browsers`)            |
| `just coverage`               | Python tests with coverage report                               |
| `just build`                  | Build wheel and sdist                                           |
| `just clean`                  | Remove build artefacts                                          |
| `just run`                    | Migrate and start the Django dev server                         |
| `just dump-fixture`           | Export local Wagtail DB → `tests/e2e/fixtures/test_data.json`   |
| `just load-fixture`           | Load that JSON fixture into the local dev database              |
| `just run-with-fixture`       | `migrate` + load non-empty `test_data.json` + `runserver`       |
| `LOAD_E2E_FIXTURE=1 just run` | Same load step as `run-with-fixture`, without a separate recipe |

Extra arguments are forwarded directly to the underlying tool:

```bash
just test-backend -k test_app_label -v
just test-frontend --bail 1
```

### E2E fixture (`test_data.json`)

Playwright tests can request the `loaded_fixture_data` fixture (see `tests/e2e/conftest.py`) to run `loaddata` on `tests/e2e/fixtures/test_data.json` before each test. The repo ships an empty `[]` file so the default is a no-op.

1. Run `just run`, build pages in the CMS, then run **`just dump-fixture`** to overwrite `test_data.json` from `testproject/testapp/db.sqlite3`.
2. In tests that need that content, add `loaded_fixture_data` to the test/fixture parameters.
3. To reset your dev DB from the committed fixture, run **`just load-fixture`** (run from the repo root; path is `tests/e2e/fixtures/test_data.json`).

4. To start the dev server **and** load that fixture in one step (after migrate), use **`just run-with-fixture`**, or **`LOAD_E2E_FIXTURE=1 just run`**. Empty `[]` fixtures are skipped. If the DB already has rows, `loaddata` may fail with duplicate key errors — use **`just load-fixture`** on a fresh DB, or `manage.py flush` first if you intend to replace everything.

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

## Licence

BSD 3-Clause
