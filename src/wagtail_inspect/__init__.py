"""Wagtail Inspect — preview block inspection."""

from contextvars import ContextVar

__version__ = "0.1.1"

preview_active: ContextVar[bool] = ContextVar("wagtail_preview_active", default=False)

# Latest preview-render map per page pk (filled in patched_make_preview_request).
_preview_block_maps: dict[int, dict] = {}


def inspect_live_pages_enabled() -> bool:
    """``WAGTAIL_INSPECT_LIVE_PAGES`` (default ``True``): inspect on live pages too."""
    from django.conf import settings

    return bool(getattr(settings, "WAGTAIL_INSPECT_LIVE_PAGES", True))


def user_can_inspect(page, user) -> bool:
    """Editors only: the overlay links into the page editor."""
    if not getattr(page, "pk", None) or not getattr(user, "is_authenticated", False):
        return False
    return bool(page.permissions_for_user(user).can_edit())
