"""Inspect's part of block marking. The marking itself lives in wagtail-block-ids.

Applied from ``AppConfig.ready()``:

- ``PreviewableMixin.make_preview_request``: render inside a wrapping
  ``wagtail_block_ids.marking`` scope (so multi-root and text-only blocks get a
  ``display:contents`` wrapper the overlay can measure), then
  ``remember_preview`` the block map for the editor's page API calls.
- A page marker for live pages: users who can edit the page get marked blocks too
  (``WAGTAIL_INSPECT_LIVE_PAGES``), also wrapped. Anonymous and non-editor responses
  are untouched.

Patches are idempotent; failures log and do not abort startup.
"""

import logging

from wagtail_block_ids import marking, register_page_marker

try:
    from wagtail.models.preview import PreviewableMixin
except ImportError:
    from wagtail.models import PreviewableMixin

from . import inspect_live_pages_enabled, user_can_inspect
from .block_map import remember_preview

logger = logging.getLogger(__name__)

_originals: dict = {}
_live_marker_registered = False


def patched_make_preview_request(self, *args, **kwargs):
    with marking(wrap=True):
        response = _originals["PreviewableMixin.make_preview_request"](self, *args, **kwargs)
    original_request = kwargs.get("original_request", args[0] if args else None)
    remember_preview(self, getattr(original_request, "user", None))
    return response


def mark_live_page(page, request) -> bool:
    """Editors' live-page serves, unless ``WAGTAIL_INSPECT_LIVE_PAGES`` is off."""
    return inspect_live_pages_enabled() and user_can_inspect(page, getattr(request, "user", None))


def _apply_patch(target, attr, replacement, label) -> None:
    """Replace *attr* on *target* once; log failures without raising."""
    if label in _originals:
        return

    try:
        _originals[label] = getattr(target, attr)
        setattr(target, attr, replacement)
    except Exception:
        logger.exception("wagtail_inspect: failed to patch %s", label)


def apply_patches() -> None:
    global _live_marker_registered
    if not _live_marker_registered:
        register_page_marker(mark_live_page, wrap=True)
        _live_marker_registered = True

    _apply_patch(
        PreviewableMixin,
        "make_preview_request",
        patched_make_preview_request,
        "PreviewableMixin.make_preview_request",
    )
