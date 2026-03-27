"""Scenario A — Editor preview panel.

The user is on the Wagtail editor page (/cms/pages/{id}/edit/).  The right
panel shows a preview iframe.  preview-inspect-controller.js injects a
crosshairs button into the preview toolbar.  Clicking it activates inspect
mode inside the iframe.  Clicking a block navigates the editor to that block's
panel section via a URL hash change.
"""

import re

import pytest
from django.urls import reverse
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
def test_inspect_button_visible_in_editor_preview(editor, make_test_page):
    """The crosshairs (Inspect) button injected by preview-inspect-controller.js
    must appear in the preview toolbar after the editor loads.
    """
    page = make_test_page()
    editor.goto(page.pk)
    expect(editor.page.locator("[data-preview-inspect-button]")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_clicking_inspect_activates_overlay_in_iframe(editor, make_test_page):
    """After activating inspect mode and hovering over a block, the highlight
    overlay becomes visible.  The overlay starts with display:none and is
    shown by InspectMode._highlight() on the first mouseover event.
    """
    page = make_test_page()
    editor.goto(page.pk)
    editor.wait_for_preview_block_elements()
    editor.activate_inspect()
    # Hover over the first block to trigger the overlay display.
    editor.iframe.locator("[data-block-id]").first.hover()
    expect(editor.iframe.locator("#wagtail-inspect-overlay")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_clicking_block_in_iframe_updates_editor_url_hash(editor, make_test_page):
    """After clicking a block inside the preview iframe, the editor URL must
    gain a hash of the form #block-{uuid}-section, indicating that
    navigateToBlock() ran and updated window.history.
    """
    page = make_test_page()
    editor.goto(page.pk)
    editor.wait_for_preview_block_elements()
    editor.activate_inspect()
    editor.click_first_block()
    expect(editor.page).to_have_url(re.compile(r"#block-.+-section"))


@pytest.mark.django_db(transaction=True)
def test_inspect_api_uuids_are_subset_of_preview_dom(editor, make_test_page, live_server):
    """Block UUIDs returned by the inspect JSON API must appear as data-block-id
    values in the preview iframe (same session as the authenticated editor).

    Subset holds when the API serves the preview-aligned block map (e.g. from
    ``_preview_block_maps`` after a preview render) so every API key exists in
    the live iframe DOM; the iframe may still contain extra nodes in edge cases.
    """
    page = make_test_page()
    editor.goto(page.pk)
    editor.wait_for_preview_block_elements()
    path = reverse("wagtail_inspect_page_api", args=[page.pk])
    resp = editor.page.request.get(f"{live_server.url}{path}")
    assert resp.ok
    api_ids = set(resp.json()["blocks"])
    count = editor.iframe.locator("[data-block-id]").count()
    dom_ids = {editor.iframe.locator("[data-block-id]").nth(i).get_attribute("data-block-id") for i in range(count)}
    assert api_ids <= dom_ids


@pytest.mark.django_db(transaction=True)
def test_inspect_mode_usable_after_preview_iframe_reload(editor, make_test_page):
    """Reloading the preview iframe destroys the iframe document; toggling inspect
    off and on must attach a fresh overlay so hover still works.
    """
    page = make_test_page()
    editor.goto(page.pk)
    editor.wait_for_preview_block_elements()
    editor.activate_inspect()

    handle = editor.page.locator('[data-w-preview-target="iframe"]').first.element_handle()
    assert handle is not None
    frame = handle.content_frame()
    assert frame is not None
    frame.evaluate("() => window.location.reload()")
    frame.wait_for_load_state("load")

    editor.wait_for_preview_block_elements()
    editor.page.locator("[data-preview-inspect-button]").click()
    editor.page.locator("[data-preview-inspect-button]").click()
    editor.iframe.locator("[data-block-id]").first.hover()
    # After reload + re-activate, duplicate overlay nodes can exist briefly.
    expect(editor.iframe.locator("#wagtail-inspect-overlay").first).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_escape_key_deactivates_inspect_mode(editor, make_test_page):
    """Pressing Escape while inspect mode is active must remove the overlay from
    the DOM, confirming that InspectMode.deactivate() was called.
    """
    page = make_test_page()
    editor.goto(page.pk)
    editor.wait_for_preview_block_elements()
    editor.activate_inspect()
    editor.press_escape()
    # deactivate() removes the overlay from the DOM entirely.
    expect(editor.iframe.locator("#wagtail-inspect-overlay")).to_have_count(0)
