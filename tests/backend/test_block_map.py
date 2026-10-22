"""Tests for block_map.py — flat_block_map_for_instance. The walk is tested in wagtail-block-ids.

- flat_block_map_for_instance returns a {uuid: {type, label, children}} dict
- flat_block_map_for_instance wires up parent → child relationships in order
- flat_block_map_for_instance skips blocks without an id
"""

import json

import pytest
from testapp.models import TestPage

from wagtail_inspect.block_map import flat_block_map_for_instance

pytestmark = pytest.mark.django_db


def _page(*body):
    """An unsaved ``TestPage`` whose ``body`` holds the raw stream items *body*."""
    return TestPage(title="Test", body=json.dumps(list(body)))


def _tag_list(block_id, *tag_ids):
    tags = [{"type": "item", "id": tag_id, "value": {"label": tag_id}} for tag_id in tag_ids]
    return {"type": "tag_list", "id": block_id, "value": {"heading": "Tags", "tags": tags}}


def test_flat_block_map_returns_stream_children():
    result = flat_block_map_for_instance(_page({"type": "text", "id": "hero", "value": "text"}))

    assert result == {"hero": {"type": "text", "label": "Text", "children": []}}


def test_flat_block_map_wires_up_list_children():
    result = flat_block_map_for_instance(_page(_tag_list("tags", "a", "b")))

    assert result["tags"]["children"] == ["a", "b"]
    assert result["a"] == {"type": "tag", "label": "Tag", "children": []}


def test_flat_block_map_preserves_child_order():
    child_ids = ["d", "b", "a", "c"]

    result = flat_block_map_for_instance(_page(_tag_list("tags", *child_ids)))

    assert result["tags"]["children"] == child_ids


def test_flat_block_map_handles_empty_stream():
    assert flat_block_map_for_instance(_page()) == {}


def test_flat_block_map_skips_none_block_id():
    """Stream items saved without an id are omitted from the result dict."""
    assert flat_block_map_for_instance(_page({"type": "text", "value": "x"})) == {}
