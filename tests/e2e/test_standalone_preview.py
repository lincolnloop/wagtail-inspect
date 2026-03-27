"""Scenario B — Standalone preview via the Wagtail userbar.

The user navigates to /cms/pages/{id}/preview/, which Wagtail renders with
request.is_preview=True.  This causes InspectBlocksUserbarItem.is_shown() to
return True and the "Inspect blocks" button appears inside the <wagtail-userbar>
shadow root.

Clicking that button activates InspectMode on the page itself (not inside an
iframe).  Clicking a block navigates the user to the CMS edit page with a
#block-{uuid}-section hash, so the editor can scroll to the right panel.

Playwright's `pierce/` CSS selector engine is used to reach elements inside the
userbar shadow DOM without manually traversing shadowRoot.
"""

import re

import pytest
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
def test_userbar_inspect_button_visible_on_standalone_preview(preview, make_test_page):
    """The "Inspect blocks" button rendered by item_inspect_preview.html must be
    discoverable inside the userbar shadow DOM on a standalone preview page.
    The userbar menu must be opened first — the button is a menu item, not
    a permanent visible element.
    """
    page = make_test_page()
    preview.goto(page.pk)
    preview.open_userbar_menu()
    expect(preview.page.locator("#inspect-blocks-trigger")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_clicking_userbar_inspect_activates_inspect_mode(preview, make_test_page):
    """After activating inspect mode via the userbar and hovering over a block,
    the highlight overlay becomes visible.
    """
    page = make_test_page()
    preview.goto(page.pk)
    preview.activate_inspect()
    # Hover over the first block to trigger the overlay display.
    preview.page.locator("[data-block-id]").first.hover()
    expect(preview.page.locator("#wagtail-inspect-overlay")).to_be_visible()


@pytest.mark.django_db(transaction=True)
def test_clicking_block_via_userbar_redirects_to_edit_page_with_hash(preview, make_test_page):
    """Clicking a block while userbar inspect mode is active must navigate to the
    CMS edit page with a #block-{uuid}-section hash so the editor scrolls to
    the correct panel section.
    """
    page = make_test_page()
    preview.goto(page.pk)
    preview.activate_inspect()
    preview.click_first_block()
    expect(preview.page).to_have_url(re.compile(r"/cms/pages/\d+/edit/.*#block-.+-section"))


@pytest.mark.django_db(transaction=True)
def test_clicking_below_fold_block_scrolls_to_section_in_editor(preview, make_test_page):
    """Clicking a below-the-fold block in the standalone preview must scroll the
    matching block section into the editor viewport after redirect.

    Regression: scrollIntoView previously fired at readyState='interactive',
    before Wagtail's widget initialisation completed. The subsequent layout
    mutations caused the scroll to land in the wrong position and the block
    stayed out of view. The fix defers the scroll to window.load.
    """
    blocks = [{"type": "text", "value": f"Block {i}"} for i in range(10)]
    page = make_test_page(blocks=blocks)
    preview.goto(page.pk)
    preview.activate_inspect()

    block_id = preview.click_nth_block(-1)

    preview.page.wait_for_url(re.compile(r"/cms/pages/\d+/edit/.*#block-.+-section"))
    preview.page.wait_for_load_state("load")

    expect(preview.page.locator(f'[data-contentpath="{block_id}"]')).to_be_in_viewport()


@pytest.mark.django_db(transaction=True)
def test_hash_scroll_lands_on_block_after_page_load(auth_page, make_test_page):
    """Navigating to the editor with a #block-{uuid}-section hash must scroll
    the matching block into the viewport after the page fully loads.

    The scroll logic runs at the page level (not inside the Stimulus
    controller) so it works regardless of which side panels are open.

    Regression: the scroll previously used behavior:'smooth' which was
    interrupted by Wagtail's side-panel layout shifts, and the readyState
    check had a dead branch that silently skipped the scroll on fast
    refresh.
    """
    blocks = [{"type": "text", "value": f"Block {i}"} for i in range(10)]
    page = make_test_page(blocks=blocks)
    last_block_id = page.body[-1].id

    auth_page.goto(f"/cms/pages/{page.pk}/edit/#block-{last_block_id}-section")
    auth_page.wait_for_load_state("load")

    block = auth_page.locator(f'[data-contentpath="{last_block_id}"]')
    expect(block).to_be_in_viewport()


@pytest.mark.django_db(transaction=True)
def test_escape_deactivates_inspect_without_navigating(preview, make_test_page):
    """Pressing Escape while userbar inspect mode is active must remove the overlay
    and keep the user on the preview page — no redirect should occur.
    """
    page = make_test_page()
    preview.goto(page.pk)
    preview.activate_inspect()
    preview.press_escape()
    # deactivate() removes the overlay from the DOM entirely.
    expect(preview.page.locator("#wagtail-inspect-overlay")).to_have_count(0)
    # The "new tab" preview URL in Wagtail 7 is /cms/pages/{id}/edit/preview/
    expect(preview.page).to_have_url(re.compile(r"/cms/pages/\d+/edit/preview/"))


# ---------------------------------------------------------------------------
# JS augmentation — blocks rendered without {% include_block %}
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_augmentation_annotates_list_children_without_include_block(preview, make_test_page):
    """TagListBlock renders its children via ``{% for tag in value.tags %}``
    with direct field access — no ``{% include_block %}``. Python patches
    cannot annotate these elements.

    The userbar's ``fetchAndAugment`` fetches the block map from the API
    and ``augmentPreviewBlocks`` matches the sibling group by count, then
    annotates each child with the correct UUID.

    A revision must exist so the API returns UUIDs that match the preview.
    """
    page = make_test_page(
        title="Augment Tags E2E",
        blocks=[
            {
                "type": "tag_list",
                "value": {
                    "heading": "Topics",
                    "tags": [
                        {"label": "Python"},
                        {"label": "Django"},
                        {"label": "Wagtail"},
                    ],
                },
            }
        ],
    )
    page.save_revision()

    preview.goto(page.pk)
    preview.activate_inspect()

    tag_elements = preview.page.locator('[data-block-type="tag"]')
    expect(tag_elements).to_have_count(3)

    expect(preview.page.locator('[data-block-type="tag"]:has-text("Python")')).to_have_count(1)
    expect(preview.page.locator('[data-block-type="tag"]:has-text("Django")')).to_have_count(1)
    expect(preview.page.locator('[data-block-type="tag"]:has-text("Wagtail")')).to_have_count(1)


@pytest.mark.django_db(transaction=True)
def test_augmentation_annotates_exactly_two_tag_children(preview, make_test_page):
    """Regression: _findSiblingGroup must match exactly two siblings (da0e15c3)."""
    page = make_test_page(
        title="Two Tag Augment E2E",
        blocks=[
            {
                "type": "tag_list",
                "value": {
                    "heading": "Topics",
                    "tags": [{"label": "Alpha"}, {"label": "Beta"}],
                },
            }
        ],
    )
    page.save_revision()

    preview.goto(page.pk)
    preview.activate_inspect()

    tag_elements = preview.page.locator('[data-block-type="tag"]')
    expect(tag_elements).to_have_count(2)
    expect(preview.page.locator('[data-block-type="tag"]:has-text("Alpha")')).to_have_count(1)
    expect(preview.page.locator('[data-block-type="tag"]:has-text("Beta")')).to_have_count(1)


@pytest.mark.django_db(transaction=True)
def test_python_annotated_blocks_not_double_annotated(preview, make_test_page):
    """Blocks wrapped by Python patches must not get a second data-block-id
    from JS augmentation; each UUID appears once in the DOM.
    """
    page = make_test_page(
        title="No Double Annotation E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "Double annotation test",
                    "subheading": "",
                    "body": "",
                    "buttons": [{"label": "CTA", "href": "https://example.com"}],
                },
            }
        ],
    )
    page.save_revision()
    preview.goto(page.pk)
    preview.activate_inspect()

    block_ids = preview.page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-block-id]'))
                  .map((el) => el.dataset.blockId)
        """
    )
    assert len(block_ids) == len(set(block_ids)), f"Duplicate data-block-id values: {block_ids}"
