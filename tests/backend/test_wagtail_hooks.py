"""Tests for wagtail_hooks.py."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from wagtail_inspect.wagtail_hooks import (
    InspectBlocksUserbarItem,
    add_inspect_blocks_item,
    global_admin_js,
)


class _Permissions:
    def __init__(self, can_edit):
        self._can_edit = can_edit

    def can_edit(self):
        return self._can_edit


class _Page:
    def __init__(self, pk=1, *, editable=True):
        self.pk = self.id = pk
        self._editable = editable

    def permissions_for_user(self, user):
        return _Permissions(self._editable)


def _request(*, is_preview=False, in_preview_panel=False, authenticated=True):
    return SimpleNamespace(
        is_preview=is_preview,
        in_preview_panel=in_preview_panel,
        user=SimpleNamespace(is_authenticated=authenticated),
    )


def test_adds_item_on_preview_for_editors():
    page = _Page()
    items = []

    add_inspect_blocks_item(_request(is_preview=True), items, page)

    assert len(items) == 1
    assert isinstance(items[0], InspectBlocksUserbarItem)
    assert items[0].page is page
    assert items[0].live is False


def test_adds_item_on_live_pages_for_editors():
    items = []

    add_inspect_blocks_item(_request(), items, _Page())

    assert len(items) == 1
    assert items[0].live is True


def test_live_pages_can_be_switched_off(settings):
    settings.WAGTAIL_INSPECT_LIVE_PAGES = False
    live, preview = [], []

    add_inspect_blocks_item(_request(), live, _Page())
    add_inspect_blocks_item(_request(is_preview=True), preview, _Page())

    assert live == []
    assert len(preview) == 1


@pytest.mark.parametrize(
    ("request_kwargs", "page"),
    [
        ({"authenticated": False}, _Page()),
        ({}, _Page(editable=False)),
        ({"is_preview": True, "in_preview_panel": True}, _Page()),
        ({"is_preview": True}, _Page(pk=None)),
        ({"is_preview": True}, None),
    ],
    ids=["anonymous", "non-editor", "preview-panel", "unsaved-page", "no-page"],
)
def test_skips_item(request_kwargs, page):
    items = []

    add_inspect_blocks_item(_request(**request_kwargs), items, page)

    assert items == []


# ---------------------------------------------------------------------------
# get_context_data / global_admin_js / URL name
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_context_data_includes_api_urls(root_page):
    from testapp.models import TestPage

    page = root_page.add_child(instance=TestPage(title="HookCtx", slug="hook-ctx"))
    item = InspectBlocksUserbarItem(page)
    ctx = item.get_context_data({})

    assert ctx["inspect_preview_context"]["pageId"] == page.pk
    assert "editUrl" in ctx["inspect_preview_context"]
    assert "apiUrl" in ctx["inspect_preview_context"]
    assert str(page.pk) in ctx["inspect_preview_context"]["apiUrl"]


@pytest.mark.django_db
def test_live_item_requests_the_live_block_map(root_page):
    from testapp.models import TestPage

    page = root_page.add_child(instance=TestPage(title="LiveMap", slug="live-map"))

    preview_url = InspectBlocksUserbarItem(page).get_context_data({})["inspect_preview_context"]["apiUrl"]
    live_url = InspectBlocksUserbarItem(page, live=True).get_context_data({})["inspect_preview_context"]["apiUrl"]

    assert "source=live" not in preview_url
    assert live_url == f"{preview_url}?source=live"


def test_userbar_item_media_loads_scripts_in_dependency_order():
    item = InspectBlocksUserbarItem(MagicMock(pk=1))
    js = [str(path) for path in item.media._js]

    assert js == [
        "wagtail_inspect/js/inspect-core.js",
        "wagtail_inspect/js/inspect-augment.js",
        "wagtail_inspect/js/userbar-inspect.js",
    ]
    assert "wagtail_inspect/css/preview-inspect.css" in item.media._css["all"]


@pytest.mark.django_db
def test_userbar_item_renders_no_inline_script(root_page, rf):
    # Inline scripts are blocked by a strict script-src CSP on preview responses.
    from testapp.models import TestPage

    page = root_page.add_child(instance=TestPage(title="NoInline", slug="no-inline"))
    html = InspectBlocksUserbarItem(page).render_html({"request": rf.get("/")})

    assert 'data-controller="wagtail-inspect-userbar"' in html
    assert "<script>" not in html
    assert 'type="application/json"' in html


def test_add_inspect_blocks_item_skips_preview_panel():
    request = MagicMock(is_preview=True, in_preview_panel=True)
    page = MagicMock()
    page.id = 1
    items = []

    add_inspect_blocks_item(request, items, page)

    assert items == []


@pytest.mark.django_db
def test_global_admin_js_emits_wagtail_inspect_config_and_scripts():
    html = str(global_admin_js())
    assert "wagtailInspectConfig" in html
    assert "apiBase" in html
    assert "augmentScriptUrl" in html
    assert "inspect-core.js" in html
    assert "preview-inspect-helpers.js" in html
    assert "preview-inspect-controller.js" in html
    assert "inspect-augment.js" in html


@pytest.mark.django_db
def test_inspect_api_url_reverse():
    url = reverse("wagtail_inspect_page_api", args=[42])
    assert "wagtail-inspect/api/page/42/" in url
