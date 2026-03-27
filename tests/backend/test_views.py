"""Tests for views.py — PageInspectView.

- Anonymous request → 401
- Authenticated user without edit permission → 403
- Nonexistent page → 404
- Authenticated editor → 200 + {"blocks": {...}}
- Response JSON contains block UUIDs from the page's StreamFields
- Cached _preview_block_maps entry is returned without calling flat_block_map_for_instance
"""

import json

import pytest
from django.test import RequestFactory
from wagtail.models import Page

import wagtail_inspect
from wagtail_inspect.views import PageInspectView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AnonUser:
    is_authenticated = False


class _AuthUser:
    is_authenticated = True

    def __init__(self, can_edit=True):
        self._can_edit = can_edit

    def __str__(self):
        return "testuser"


class _Permissions:
    def __init__(self, can_edit):
        self._can_edit = can_edit

    def can_edit(self):
        return self._can_edit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def make_test_page(root_page):
    """Return a helper that creates and saves a minimal TestPage."""
    from testapp.models import TestPage

    def _make(**kwargs):
        page = root_page.add_child(
            instance=TestPage(
                title=kwargs.get("title", "Test"),
                slug=kwargs.get("slug", "test"),
            )
        )
        return page

    return _make


@pytest.fixture
def monkeypatch_inspect_editor(monkeypatch):
    """Allow PageInspectView success-path tests to patch edit permission and the
    block-map builder in one call.
    """

    def _apply(*, flat_map_result=None, flat_map_fn=None):
        monkeypatch.setattr(
            Page,
            "permissions_for_user",
            lambda self, user: _Permissions(can_edit=True),
        )
        if flat_map_fn is not None:
            monkeypatch.setattr(
                "wagtail_inspect.views.flat_block_map_for_instance",
                flat_map_fn,
            )
        elif flat_map_result is not None:
            monkeypatch.setattr(
                "wagtail_inspect.views.flat_block_map_for_instance",
                lambda p: flat_map_result,
            )

    return _apply


# ---------------------------------------------------------------------------
# Auth / permission tests
# ---------------------------------------------------------------------------


def test_anonymous_gets_401(rf, make_test_page):
    page = make_test_page()
    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AnonUser()
    response = PageInspectView.as_view()(request, page_id=page.pk)
    assert response.status_code == 401


def test_non_editor_gets_403(rf, make_test_page, monkeypatch):
    page = make_test_page()

    # Patch permissions so the user cannot edit
    from wagtail.models import Page as _Page

    monkeypatch.setattr(
        _Page,
        "permissions_for_user",
        lambda self, user: _Permissions(can_edit=False),
    )

    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AuthUser(can_edit=False)
    response = PageInspectView.as_view()(request, page_id=page.pk)
    assert response.status_code == 403


@pytest.mark.django_db
def test_nonexistent_page_gets_404(rf):
    request = rf.get("/wagtail-inspect/api/page/99999/")
    request.user = _AuthUser()
    response = PageInspectView.as_view()(request, page_id=99999)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_editor_gets_200_with_blocks(rf, make_test_page, monkeypatch_inspect_editor):
    page = make_test_page()
    # Stub flat_block_map_for_instance so this test doesn't depend on
    # StreamField traversal logic (covered by test_block_map.py).
    monkeypatch_inspect_editor(
        flat_map_result={"fake-uuid": {"type": "hero", "label": "Hero", "children": []}},
    )

    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AuthUser()
    response = PageInspectView.as_view()(request, page_id=page.pk)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert "blocks" in data
    assert "fake-uuid" in data["blocks"]
    assert data["blocks"]["fake-uuid"]["type"] == "hero"


def test_editor_gets_cached_block_map_when_preview_map_exists(
    rf, make_test_page, monkeypatch_inspect_editor, monkeypatch
):
    """When _preview_block_maps[page_id] is populated (after a preview render),
    PageInspectView returns it and does not call flat_block_map_for_instance.
    """
    page = make_test_page()
    cached = {"cached-uuid": {"type": "text", "label": "Text", "children": []}}
    wagtail_inspect._preview_block_maps[page.pk] = cached

    called = []
    monkeypatch_inspect_editor(
        flat_map_fn=lambda p: called.append(p) or {},
    )

    try:
        request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
        request.user = _AuthUser()
        response = PageInspectView.as_view()(request, page_id=page.pk)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["blocks"] == cached
        assert called == []
    finally:
        wagtail_inspect._preview_block_maps.pop(page.pk, None)


def test_editor_uses_revision_as_object_when_present(rf, make_test_page, monkeypatch_inspect_editor, monkeypatch):
    page = make_test_page()
    sentinel = object()

    class _Rev:
        def as_object(self):
            return sentinel

    monkeypatch.setattr(Page, "get_latest_revision", lambda self: _Rev())

    called_with = []
    monkeypatch_inspect_editor(
        flat_map_fn=lambda p: called_with.append(p) or {},
    )

    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AuthUser()
    response = PageInspectView.as_view()(request, page_id=page.pk)
    assert response.status_code == 200
    assert called_with == [sentinel]


def test_editor_uses_live_page_when_no_revision(rf, make_test_page, monkeypatch_inspect_editor, monkeypatch):
    page = make_test_page()

    monkeypatch.setattr(Page, "get_latest_revision", lambda self: None)

    called_with = []
    monkeypatch_inspect_editor(
        flat_map_fn=lambda p: called_with.append(p) or {},
    )

    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AuthUser()
    response = PageInspectView.as_view()(request, page_id=page.pk)
    assert response.status_code == 200
    assert len(called_with) == 1
    assert called_with[0].pk == page.pk


def test_editor_response_blocks_include_children_arrays(rf, make_test_page, monkeypatch_inspect_editor):
    page = make_test_page()
    stub = {
        "a": {"type": "hero", "label": "Hero", "children": ["b"]},
        "b": {"type": "text", "label": "Text", "children": []},
    }

    monkeypatch_inspect_editor(flat_map_result=stub)

    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/")
    request.user = _AuthUser()
    response = PageInspectView.as_view()(request, page_id=page.pk)
    data = json.loads(response.content)
    assert data["blocks"]["a"]["children"] == ["b"]
    assert data["blocks"]["b"]["children"] == []
