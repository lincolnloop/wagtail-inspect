"""Wagtail Inspect — preview block inspection."""

from contextvars import ContextVar

__version__ = "0.1.0"

preview_active: ContextVar[bool] = ContextVar("wagtail_preview_active", default=False)

# Latest preview-render map per page pk (filled in patched_make_preview_request).
_preview_block_maps: dict[int, dict] = {}
