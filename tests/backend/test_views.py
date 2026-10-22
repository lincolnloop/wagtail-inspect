"""Tests for views.py — PageInspectView.

- Anonymous request → 401
- Authenticated user without edit permission → 403
- Nonexistent page → 404
- Authenticated editor → 200 + {"blocks": {...}}
- Response JSON is the block map for the editor (their last preview, or ?source=live)
"""

import json

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from testapp.models import TestPage

from wagtail_inspect.block_map import remember_preview
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


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


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
# Success path (which map is served is covered in test_block_map.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser(username="admin", password="x")


def _get(rf, page, user, query=""):
    request = rf.get(f"/wagtail-inspect/api/page/{page.pk}/{query}")
    request.user = user
    return PageInspectView.as_view()(request, page_id=page.pk)


def _text_body(block_id):
    return json.dumps([{"type": "text", "id": block_id, "value": "x"}])


def _page_with_text(make_test_page, block_id):
    page = make_test_page()
    page.body = _text_body(block_id)
    page.save()
    return page


def test_editor_gets_200_with_blocks(rf, make_test_page, superuser):
    page = _page_with_text(make_test_page, "hero")

    response = _get(rf, page, superuser)

    assert response.status_code == 200
    assert json.loads(response.content) == {"blocks": {"hero": {"type": "text", "label": "Text", "children": []}}}


def test_editor_gets_their_last_preview(rf, make_test_page, superuser):
    page = _page_with_text(make_test_page, "saved")
    remember_preview(TestPage(pk=page.pk, body=_text_body("unsaved")), superuser)

    assert list(json.loads(_get(rf, page, superuser).content)["blocks"]) == ["unsaved"]


def test_live_source_serves_the_published_page(rf, make_test_page, superuser):
    page = _page_with_text(make_test_page, "live")
    remember_preview(TestPage(pk=page.pk, body=_text_body("unsaved")), superuser)

    assert list(json.loads(_get(rf, page, superuser, "?source=live").content)["blocks"]) == ["live"]
