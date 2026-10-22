# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The inspect highlight follows its block while the page scrolls instead of trailing
  behind it. The box is positioned with `transform` and snaps to each block (no
  glide between blocks), and repositioning no longer forces a layout each frame.

### Changed

- Requires wagtail-block-ids 0.2.0. List children in the block map, and their marks on
  the page, are named from their list (a `tags` list's items are "Tag", not "Item").
- `flat_block_map_for_instance` reads the page's StreamFields through
  wagtail-block-ids' `stream_values`.
- The preview block map is kept per editor in Django's cache instead of a
  process-local dict, so one editor's unsaved preview no longer leaks into another's
  inspector, and every worker sees it when the cache backend is shared. Entries
  expire after a day.
- New `wagtail_inspect.block_map.block_map_for(page, user, *, live=False)` and
  `remember_preview(obj, user)` own the choice of map; `PageInspectView` delegates
  to them.

### Deprecated

- `wagtail_inspect.block_map.blocks_for_field`, `resolve_block_type` and
  `resolve_block_label`. Import them from `wagtail_block_ids`.

### Removed

- `wagtail_inspect._preview_block_maps`.

## [0.2.0]

### Changed

- Block marking (the `BoundBlock` / `ListValue` / `Page.serve` patches and the
  StreamField walk) moved to the new
  [wagtail-block-ids](https://github.com/lincolnloop/wagtail-block-ids) package, which
  wagtail-inspect now depends on. wagtail-live-comments uses the same core, so the two
  packages mark each block once instead of patching the same methods twice. Inspect's
  behaviour is unchanged: preview and editors' live pages are marked, with
  `display:contents` wrappers for multi-root or text-only blocks.
- `blocks_for_field`, `resolve_block_type` and `resolve_block_label` are re-exported
  from `wagtail_inspect.block_map`.

### Removed

- `wagtail_inspect.preview_active`. Use `wagtail_block_ids.is_marking()`.

## [0.1.1] - 2026-10-18

### Fixed

- **Inspect blocks** in the standalone preview userbar works under a strict
  `script-src` Content Security Policy (nonce, no `'unsafe-inline'`). Assets now load
  through the userbar item's `media` instead of an inline loader script.
- Editor preview panel: inspect follows Wagtail 6+ iframe swaps by listening for
  `w-preview:loaded`, and never targets the proxy iframe that is still loading.
- `<template data-block-id>` elements in host pages are no longer treated as blocks
  (hover, keyboard focus, and child augmentation).

### Added

- **Inspect blocks** on live pages for users who can edit the page
  (`WAGTAIL_INSPECT_LIVE_PAGES`, default `True`). Only those users' responses get the
  `data-block-*` attributes; the block map API serves the published body
  (`?source=live`).

### Changed

- The userbar item is no longer added inside the editor preview panel, where Wagtail
  hides the userbar; the panel's crosshairs control drives inspect there.

## [0.1.0] - 2025-03-26

### Added

- Initial release: block inspection for the Wagtail CMS preview panel.
- Crosshairs control in the editor preview panel and **Inspect blocks** in the userbar on standalone preview pages.
- Preview-only DOM attributes (`data-block-id`, `data-block-type`, `data-block-label`) and admin JSON API for the block map.
- Support for Django 4.2+ and Wagtail 5, 6, and 7 (Python 3.12+).

[Unreleased]: https://github.com/lincolnloop/wagtail-inspect/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/lincolnloop/wagtail-inspect/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/lincolnloop/wagtail-inspect/releases/tag/v0.1.0
