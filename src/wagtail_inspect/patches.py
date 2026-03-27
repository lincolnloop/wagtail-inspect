"""Monkey-patches applied from AppConfig.ready():

- ``BoundBlock.render`` / ``render_as_block``: in preview, add ``data-block-*``
  (inject into first tag, or ``display:contents`` wrapper for multi-root / text).
- ``ListValue.__iter__``: in preview, yield ``_ListChildProxy`` so list items
  still work as values but get inspect wrapping via ``include_block``.
- ``PreviewableMixin.make_preview_request``: set ``preview_active``, then store
  ``flat_block_map_for_instance`` for the page API.

Patches are idempotent; failures log and do not abort startup.
"""

import logging
import re
from html.parser import HTMLParser

from django.utils.html import conditional_escape, format_html, mark_safe
from wagtail import VERSION as WAGTAIL_VERSION
from wagtail.blocks import BoundBlock
from wagtail.blocks.list_block import ListValue

try:
    from wagtail.models.preview import PreviewableMixin
except ImportError:
    from wagtail.models import PreviewableMixin

from . import preview_active

logger = logging.getLogger(__name__)

TESTED_WAGTAIL_VERSIONS = ((5,), (6,), (7,))

_originals: dict = {}


# Matches the opening token of the first HTML element tag (e.g. "<div", "<section").
# Used by _inject_attrs_into_root to locate the injection point.
_FIRST_TAG_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9:-]*")

# Void elements have no closing tag and do not affect nesting depth.
_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


class _RootCounter(HTMLParser):
    def reset(self) -> None:
        super().reset()
        self.depth = 0
        self.roots = 0
        self.top_text = 0

    def handle_starttag(self, tag, _attrs) -> None:
        if not self.depth:
            self.roots += 1
        if tag not in _VOID_ELEMENTS:
            self.depth += 1

    def handle_endtag(self, tag) -> None:
        if tag not in _VOID_ELEMENTS:
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data) -> None:
        if not self.depth and data.strip():
            self.top_text += 1


_root_counter = _RootCounter()


def _is_multi_root_fragment(html: str) -> bool:
    """True if fragment has multiple roots or text siblings (markdown-style)."""
    _root_counter.reset()
    _root_counter.feed(html)
    return _root_counter.roots > 1 or (_root_counter.roots == 1 and _root_counter.top_text > 0)


def _inject_attrs_into_root(output, block_id, block_type, block_label):
    """Insert ``data-block-*`` after the first start tag; return ``(out, ok)``."""
    attrs = (
        f' data-block-id="{conditional_escape(block_id)}"'
        f' data-block-type="{conditional_escape(block_type)}"'
        f' data-block-label="{conditional_escape(block_label)}"'
    )
    result, n = _FIRST_TAG_RE.subn(
        lambda m: m.group(0) + attrs,
        str(output),
        count=1,
    )
    if n:
        return mark_safe(result), True
    return output, False


def _wrap_if_preview(self, output):
    """If preview + bound block has ``id``, annotate HTML or wrap with display:contents."""
    if not (preview_active.get() and getattr(self, "id", None)):
        return output

    from .block_map import resolve_block_label, resolve_block_type

    block_type = resolve_block_type(self)
    block_label = resolve_block_label(self)

    s = str(output)

    def _display_contents_wrap(content):
        return format_html(
            '<div data-block-id="{}" data-block-type="{}" data-block-label="{}" style="display:contents">{}</div>',
            self.id,
            block_type,
            block_label,
            content,
        )

    if not _FIRST_TAG_RE.search(s):
        return _display_contents_wrap(output)

    if _is_multi_root_fragment(s):
        return _display_contents_wrap(mark_safe(s))

    annotated, _ = _inject_attrs_into_root(output, self.id, block_type, block_label)
    return annotated


class _ListChildProxy:
    """Preview-only: ListChild with value-like access plus ``id`` / ``render_as_block``."""

    __slots__ = ("_child",)

    def __init__(self, list_child) -> None:
        object.__setattr__(self, "_child", list_child)

    id = property(lambda self: self._child.id)
    block = property(lambda self: self._child.block)
    block_type = property(lambda self: getattr(self._child, "block_type", None))
    value = property(lambda self: self._child.value)

    def render(self, context=None):
        return self._child.render(context)

    def render_as_block(self, context=None):
        return self._child.render_as_block(context)

    def __str__(self) -> str:
        return str(self._child.value)

    def __iter__(self):
        return iter(self._child.value)

    def __getattr__(self, name):
        v = self._child.value
        getitem = getattr(v, "__getitem__", None)
        if getitem is not None:
            try:
                return getitem(name)
            except (KeyError, TypeError, IndexError):
                pass
        return getattr(v, name)

    def __getitem__(self, key):
        return self._child.value[key]

    def __len__(self) -> int:
        return len(self._child.value)

    def __bool__(self) -> bool:
        return bool(self._child.value)


def patched_bound_block_render(self, context=None):
    return _wrap_if_preview(self, _originals["BoundBlock.render"](self, context=context))


def patched_bound_block_render_as_block(self, context=None):
    return _wrap_if_preview(self, _originals["BoundBlock.render_as_block"](self, context=context))


def patched_list_value_iter(self):
    if not preview_active.get():
        return _originals["ListValue.__iter__"](self)
    return iter(_ListChildProxy(child) for child in self.bound_blocks)


def patched_make_preview_request(self, *args, **kwargs):
    from . import _preview_block_maps
    from .block_map import flat_block_map_for_instance

    token = preview_active.set(True)
    try:
        response = _originals["PreviewableMixin.make_preview_request"](self, *args, **kwargs)
        page_pk = getattr(self, "pk", None)
        if page_pk:
            _preview_block_maps[page_pk] = flat_block_map_for_instance(self)
        return response
    finally:
        preview_active.reset(token)


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
    if not any(WAGTAIL_VERSION[: len(v)] == v for v in TESTED_WAGTAIL_VERSIONS):
        logger.warning(
            "wagtail_inspect: Wagtail %s has not been tested. Tested versions: %s. Patches may not work correctly.",
            ".".join(str(x) for x in WAGTAIL_VERSION[:3]),
            ", ".join(".".join(str(x) for x in v) for v in TESTED_WAGTAIL_VERSIONS),
        )

    _apply_patch(BoundBlock, "render", patched_bound_block_render, "BoundBlock.render")

    _apply_patch(
        BoundBlock,
        "render_as_block",
        patched_bound_block_render_as_block,
        "BoundBlock.render_as_block",
    )

    _apply_patch(
        PreviewableMixin,
        "make_preview_request",
        patched_make_preview_request,
        "PreviewableMixin.make_preview_request",
    )

    _apply_patch(
        ListValue,
        "__iter__",
        patched_list_value_iter,
        "ListValue.__iter__",
    )
