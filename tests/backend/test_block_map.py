"""Tests for block_map.py. The walk is tested in wagtail-block-ids.

- flat_block_map_for_instance returns a {uuid: {type, label, children}} dict
- flat_block_map_for_instance wires up parent → child relationships in order
- flat_block_map_for_instance skips blocks without an id
- block_map_for serves the editor's last preview, else the latest revision, else the page
- block_map_for(live=True) serves the published page
- remember_preview keeps one map per editor and page, and needs both
- the walk re-exports are deprecated
"""

import json

import pytest
from django.core.cache import cache
from testapp.models import TestPage

from wagtail_inspect import block_map
from wagtail_inspect.block_map import block_map_for, flat_block_map_for_instance, remember_preview

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _text(block_id):
    return {"type": "text", "id": block_id, "value": block_id}


def _page(*body):
    """An unsaved ``TestPage`` whose ``body`` holds the raw stream items *body*."""
    return TestPage(title="Test", body=json.dumps(list(body)))


def _tag_list(block_id, *tag_ids):
    tags = [{"type": "item", "id": tag_id, "value": {"label": tag_id}} for tag_id in tag_ids]
    return {"type": "tag_list", "id": block_id, "value": {"heading": "Tags", "tags": tags}}


@pytest.fixture
def saved_page(root_page):
    """A saved page whose body holds one ``live`` text block."""
    return root_page.add_child(instance=TestPage(title="Saved", slug="saved", body=json.dumps([_text("live")])))


@pytest.fixture
def editor(django_user_model):
    return django_user_model.objects.create_user(username="editor")


@pytest.fixture
def other_editor(django_user_model):
    return django_user_model.objects.create_user(username="other")


def _preview(page, *body):
    """*page* as a preview render sees it: same pk, unsaved *body*."""
    return TestPage(pk=page.pk, body=json.dumps(list(body)))


def _save_draft(page, *body):
    """Save a draft revision of *page* holding *body*; return the page as published."""
    draft = TestPage.objects.get(pk=page.pk)
    draft.body = json.dumps(list(body))
    draft.save_revision()
    return TestPage.objects.get(pk=page.pk)


# ---------------------------------------------------------------------------
# flat_block_map_for_instance
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# block_map_for / remember_preview
# ---------------------------------------------------------------------------


def test_block_map_for_uses_the_page_without_a_revision(saved_page, editor):
    assert list(block_map_for(saved_page, editor)) == ["live"]


def test_block_map_for_uses_the_latest_revision(saved_page, editor):
    page = _save_draft(saved_page, _text("draft"))

    assert list(block_map_for(page, editor)) == ["draft"]


def test_block_map_for_prefers_the_editors_last_preview(saved_page, editor):
    page = _save_draft(saved_page, _text("draft"))

    remember_preview(_preview(page, _text("unsaved")), editor)

    assert list(block_map_for(page, editor)) == ["unsaved"]


def test_block_map_for_live_ignores_preview_and_revision(saved_page, editor):
    page = _save_draft(saved_page, _text("draft"))
    remember_preview(_preview(page, _text("unsaved")), editor)

    assert list(block_map_for(page, editor, live=True)) == ["live"]


def test_previews_are_kept_per_editor(saved_page, editor, other_editor):
    remember_preview(_preview(saved_page, _text("mine")), editor)

    assert list(block_map_for(saved_page, editor)) == ["mine"]
    assert list(block_map_for(saved_page, other_editor)) == ["live"]


def test_remember_preview_needs_a_pk(saved_page, editor):
    remember_preview(_page(_text("unsaved")), editor)

    assert list(block_map_for(saved_page, editor)) == ["live"]


def test_remember_preview_needs_an_authenticated_user(saved_page, editor):
    from django.contrib.auth.models import AnonymousUser

    remember_preview(_preview(saved_page, _text("unsaved")), AnonymousUser())
    remember_preview(_preview(saved_page, _text("unsaved")), None)

    assert list(block_map_for(saved_page, editor)) == ["live"]


# ---------------------------------------------------------------------------
# Deprecated re-exports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["blocks_for_field", "resolve_block_label", "resolve_block_type"])
def test_walk_reexports_are_deprecated(name):
    import wagtail_block_ids

    with pytest.deprecated_call():
        assert getattr(block_map, name) is getattr(wagtail_block_ids, name)
