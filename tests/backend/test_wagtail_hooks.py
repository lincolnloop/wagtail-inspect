"""Tests for wagtail_hooks.py."""

from unittest.mock import MagicMock

import pytest
from django.urls import reverse

from wagtail_inspect.wagtail_hooks import (
    InspectBlocksUserbarItem,
    add_inspect_blocks_item,
    global_admin_js,
)


def test_add_inspect_blocks_item_appends_on_preview_with_page_id():
    request = MagicMock()
    request.is_preview = True
    page = MagicMock()
    page.id = 1
    items = []

    add_inspect_blocks_item(request, items, page)

    assert len(items) == 1
    assert isinstance(items[0], InspectBlocksUserbarItem)
    assert items[0].page is page


def test_add_inspect_blocks_item_skips_when_page_missing_or_no_id():
    request = MagicMock(is_preview=True)
    items = []

    add_inspect_blocks_item(request, items, None)
    assert items == []

    page = MagicMock()
    page.id = None
    add_inspect_blocks_item(request, items, page)
    assert items == []


def test_add_inspect_blocks_item_skips_when_not_preview():
    request = MagicMock()
    request.is_preview = False
    page = MagicMock()
    page.id = 1
    items = []

    add_inspect_blocks_item(request, items, page)

    assert items == []


def test_add_inspect_blocks_item_skips_when_is_preview_absent():
    # Plain object: MagicMock would synthesize ``is_preview`` and make it truthy.
    request = object()
    page = MagicMock()
    page.id = 1
    items = []

    add_inspect_blocks_item(request, items, page)

    assert items == []


# ---------------------------------------------------------------------------
# get_context_data / global_admin_js / URL name
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_context_data_includes_api_and_script_urls(root_page):
    from testapp.models import TestPage

    page = root_page.add_child(instance=TestPage(title="HookCtx", slug="hook-ctx"))
    item = InspectBlocksUserbarItem(page)
    ctx = item.get_context_data({})

    assert ctx["inspect_preview_context"]["pageId"] == page.pk
    assert "editUrl" in ctx["inspect_preview_context"]
    assert "apiUrl" in ctx["inspect_preview_context"]
    assert str(page.pk) in ctx["inspect_preview_context"]["apiUrl"]
    for key in ("css_url", "core_js_url", "augment_js_url", "userbar_js_url"):
        assert key in ctx
        assert "wagtail_inspect" in ctx[key]


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
