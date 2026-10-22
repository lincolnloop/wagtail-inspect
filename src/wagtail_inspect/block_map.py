"""Flat block maps for the inspect API: which blocks the inspected page rendered.

``block_map_for`` picks the map the overlay is looking at: the published page on a
live serve, otherwise the editor's last preview render (``remember_preview``), the
latest revision, or the page itself.
"""

import warnings

from django.core.cache import cache
from wagtail_block_ids import blocks_for_field as _blocks_for_field
from wagtail_block_ids import stream_values

__all__ = ["block_map_for", "flat_block_map_for_instance", "remember_preview"]

# Preview renders unsaved form data, so no revision holds these block ids. Kept in
# Django's cache so every worker sees them (with a shared backend), per editor.
PREVIEW_MAP_TIMEOUT = 60 * 60 * 24

_MOVED_TO_BLOCK_IDS = ("blocks_for_field", "resolve_block_label", "resolve_block_type")


def __getattr__(name):
    if name in _MOVED_TO_BLOCK_IDS:
        warnings.warn(
            f"wagtail_inspect.block_map.{name} is deprecated; import it from wagtail_block_ids.",
            DeprecationWarning,
            stacklevel=2,
        )
        import wagtail_block_ids

        return getattr(wagtail_block_ids, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def flat_block_map_for_instance(page):
    """``{uuid: {type, label, children}}`` for all StreamFields on *page*."""
    entries = [info for _name, value in stream_values(page) for info in _blocks_for_field(value) if info.id]
    result = {str(info.id): {"type": info.type, "label": info.label, "children": []} for info in entries}
    for info in entries:
        parent = result.get(str(info.parent_id)) if info.parent_id else None
        if parent is not None:
            parent["children"].append(str(info.id))
    return result


def _preview_key(page_pk, user):
    if not page_pk or not getattr(user, "is_authenticated", False):
        return None
    return f"wagtail_inspect:preview_map:{user.pk}:{page_pk}"


def remember_preview(obj, user) -> None:
    """Keep *obj*'s map after *user*'s preview render, for ``block_map_for``.

    No-op without a pk or an authenticated user.
    """
    key = _preview_key(getattr(obj, "pk", None), user)
    if key:
        cache.set(key, flat_block_map_for_instance(obj), PREVIEW_MAP_TIMEOUT)


def block_map_for(page, user, *, live=False):
    """The map of what *user*'s inspector shows for *page*.

    *live*: the published page (userbar on a live serve). Otherwise *user*'s last
    preview render of *page*, else its latest revision, else *page* itself.
    """
    if live:
        return flat_block_map_for_instance(page)
    key = _preview_key(page.pk, user)
    preview_map = cache.get(key) if key else None
    if preview_map is not None:
        return preview_map
    revision = page.get_latest_revision()
    return flat_block_map_for_instance(revision.as_object() if revision else page)
