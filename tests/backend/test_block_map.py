"""Tests for block_map.py — flat_block_map_for_instance. The walk is tested in wagtail-block-ids.

- flat_block_map_for_instance returns a {uuid: {type, label, children}} dict
- flat_block_map_for_instance wires up parent → child relationships in order
- flat_block_map_for_instance covers all StreamFields on the page model
"""

import pytest
from wagtail.blocks import CharBlock, StructBlock
from wagtail.fields import StreamField as _StreamField

from tests.backend.block_map_fakes import (
    _FakeListValue,
    _FakePage,
    _FakeStreamField,
    _ListChild,
    _make_uuid,
    _StreamChild,
    make_page_with_stream,
)
from wagtail_inspect.block_map import flat_block_map_for_instance


@pytest.fixture(autouse=True)
def _patch_isinstance_for_fake_streamfield(monkeypatch):
    """Make _FakeStreamField pass isinstance(field, StreamField)."""
    import builtins

    _original = builtins.isinstance

    def _patched(obj, types):
        if types is _StreamField and type(obj) is _FakeStreamField:
            return True
        return _original(obj, types)

    monkeypatch.setattr(builtins, "isinstance", _patched)


@pytest.fixture(autouse=True)
def _patch_fake_page_meta(monkeypatch):
    """Route _meta.get_fields() on _FakePage instances."""

    class _Meta:
        def __init__(self, page):
            self._page = page

        def get_fields(self):
            return self._page._meta_get_fields()

    original_init = _FakePage.__init__

    def new_init(self, sv):
        original_init(self, sv)
        self._meta = _Meta(self)

    monkeypatch.setattr(_FakePage, "__init__", new_init)


# ---------------------------------------------------------------------------
# blocks_for_field
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# flat_block_map_for_instance
# ---------------------------------------------------------------------------


def test_flat_block_map_returns_stream_children():
    uid = _make_uuid()
    page = make_page_with_stream(_StreamChild(uid, "hero", "Hero", "text"))
    result = flat_block_map_for_instance(page)

    assert uid in result
    assert result[uid]["type"] == "hero"
    assert result[uid]["label"] == "Hero"
    assert result[uid]["children"] == []


def test_flat_block_map_wires_up_list_children():
    parent_id = _make_uuid()
    child_id_1 = _make_uuid()
    child_id_2 = _make_uuid()

    list_value = _FakeListValue(
        [
            _ListChild(child_id_1, "logo", "Logo", ""),
            _ListChild(child_id_2, "logo", "Logo", ""),
        ]
    )
    page = make_page_with_stream(_StreamChild(parent_id, "logo_cloud", "Logo Cloud", list_value))
    result = flat_block_map_for_instance(page)

    assert parent_id in result
    assert child_id_1 in result
    assert child_id_2 in result
    assert result[parent_id]["children"] == [child_id_1, child_id_2]


def test_flat_block_map_preserves_child_order():
    parent_id = _make_uuid()
    child_ids = [_make_uuid() for _ in range(4)]

    list_value = _FakeListValue([_ListChild(cid, "item", "Item", "") for cid in child_ids])
    page = make_page_with_stream(_StreamChild(parent_id, "section", "Section", list_value))
    result = flat_block_map_for_instance(page)

    assert result[parent_id]["children"] == child_ids


def test_flat_block_map_handles_empty_stream():
    page = make_page_with_stream()
    result = flat_block_map_for_instance(page)
    assert result == {}


# ---------------------------------------------------------------------------
# Label resolution for list children
# ---------------------------------------------------------------------------


def test_list_child_label_uses_explicit_meta_label():
    """When the child block has Meta.label, use it."""
    parent_id = _make_uuid()
    child_id = _make_uuid()

    child_block = type("B", (), {"name": "", "label": "Feature"})()
    child = _ListChild(child_id, None, "Feature", "")
    child.block = child_block
    list_value = _FakeListValue([child])

    page = make_page_with_stream(_StreamChild(parent_id, "grid", "Grid", list_value))
    result = flat_block_map_for_instance(page)

    assert result[child_id]["label"] == "Feature"


class FeatureItemBlock(StructBlock):
    title = CharBlock()


class StatItemBlock(StructBlock):
    value_field = CharBlock()

    class Meta:
        label = "Stat"


# ---------------------------------------------------------------------------
# Helpers: singularize, list parent label, resolve_block_type, class label
# ---------------------------------------------------------------------------


def test_flat_block_map_skips_none_block_id():
    """Entries with a falsy block id are omitted from the result dict."""
    page = make_page_with_stream(_StreamChild(None, "ghost", "Ghost", "x"))
    result = flat_block_map_for_instance(page)
    assert result == {}
