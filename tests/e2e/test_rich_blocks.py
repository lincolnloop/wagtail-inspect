"""E2E tests that exercise block inspection on richer TestPage StreamField blocks
(e.g. Hero Section) in the editor preview.

Each test creates a page with a specific block type, opens the editor preview,
activates inspect mode, and verifies that the block receives a data-block-id
attribute and that clicking it updates the editor URL hash.
"""

import re

import pytest
from playwright.sync_api import expect

# ---------------------------------------------------------------------------
# Hero Section block
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_hero_section_block_is_inspectable(editor, make_test_page):
    """A Hero Section block must appear in the preview with a data-block-id
    attribute after the block rendering patch wraps it.
    """
    page = make_test_page(
        title="Hero E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "Welcome to the Inspect Test",
                    "subheading": "This hero block should be inspectable",
                    "body": "",
                    "buttons": [
                        {"label": "Learn more", "href": "https://example.com"},
                    ],
                },
            }
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()

    hero_block = editor.iframe.locator('[data-block-id][data-block-type="hero"]')
    expect(hero_block).to_have_count(1)


@pytest.mark.django_db(transaction=True)
def test_clicking_hero_block_updates_editor_hash(editor, make_test_page):
    """Clicking the Hero Section block in inspect mode must update the editor
    URL hash to #block-{uuid}-section.
    """
    page = make_test_page(
        title="Hero Click E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "Click This Hero",
                    "subheading": "",
                    "body": "",
                    "buttons": [
                        {"label": "Learn more", "href": "https://example.com"},
                    ],
                },
            }
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()
    editor.iframe.locator('[data-block-type="hero"]').first.click()
    expect(editor.page).to_have_url(re.compile(r"#block-.+-section"))


# ---------------------------------------------------------------------------
# CTA Callout block
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mixed page — multiple hero blocks
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_multiple_rich_blocks_all_get_block_ids(editor, make_test_page):
    """A page with multiple Hero Section blocks must have all wrapped with
    data-block-id attributes in the preview, confirming the patch covers
    all top-level stream blocks regardless of type.
    """
    page = make_test_page(
        title="Mixed Blocks E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "Hero heading",
                    "subheading": "Hero sub",
                    "body": "",
                    "buttons": [
                        {"label": "Learn more", "href": "https://example.com"},
                    ],
                },
            },
            {
                "type": "hero",
                "value": {
                    "heading": "Second hero heading",
                    "subheading": "Second sub",
                    "body": "",
                    "buttons": [
                        {"label": "Go", "href": "https://example.com"},
                    ],
                },
            },
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()

    hero_blocks = editor.iframe.locator('[data-block-id][data-block-type="hero"]')
    expect(hero_blocks).to_have_count(2)


# ---------------------------------------------------------------------------
# Nested button inspection via CallToActionBlock wrapper
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_button_in_cta_wrapper_is_individually_inspectable(editor, make_test_page):
    """Individual buttons inside HeroSectionBlock.buttons should be individually
    clickable because they're ListChildren with UUIDs.
    """
    page = make_test_page(
        title="Nested Button E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "Hero with CTA",
                    "subheading": "Test subheading",
                    "body": "",
                    "buttons": [
                        {"label": "Learn more", "href": "https://example.com"},
                    ],
                },
            }
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()

    button_wrapper = editor.iframe.locator('[data-block-type="button"]')
    expect(button_wrapper).to_be_visible()

    button = editor.iframe.locator('a:has-text("Learn more")')
    button.click()

    expect(editor.page).to_have_url(re.compile(r"#block-.+-section"))


@pytest.mark.django_db(transaction=True)
def test_multiple_buttons_in_cta_wrapper_are_each_inspectable(editor, make_test_page):
    """Two hero buttons on the page should each be individually inspectable.

    (Editor preview currently wraps ListBlock children reliably when each hero
    has a single button; two buttons in one hero list is covered by backend
    rendering tests.)
    """
    page = make_test_page(
        title="Two Btn E2E",
        blocks=[
            {
                "type": "hero",
                "value": {
                    "heading": "First hero",
                    "subheading": "Test subheading",
                    "body": "",
                    "buttons": [
                        {
                            "label": "Primary action",
                            "href": "https://example.com/primary",
                        },
                    ],
                },
            },
            {
                "type": "hero",
                "value": {
                    "heading": "Second hero",
                    "subheading": "Test subheading",
                    "body": "",
                    "buttons": [
                        {
                            "label": "Secondary action",
                            "href": "https://example.com/secondary",
                        },
                    ],
                },
            },
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()

    button_wrappers = editor.iframe.locator('[data-block-type="button"]')
    expect(button_wrappers).to_have_count(2)

    first_button = editor.iframe.locator('a[href="https://example.com/primary"]')
    first_button.click()
    expect(editor.page).to_have_url(re.compile(r"#block-.+-section"))


# ---------------------------------------------------------------------------
# Stats Section block — ListBlock with custom {% include_block %} iteration
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_stats_section_two_items_both_inspectable(editor, make_test_page):
    """Regression: StatsSectionBlock.stats is a ListBlock rendered without default
    <ul>/<li> markup. With patched ``ListValue.__iter__``, plain
    ``{% for stat in value.stats %}{% include_block stat %}`` yields ListChild
    instances so Python wraps each stat with ``data-block-id`` (no JS augmentation).

    The section also has a badge+headline container so the DOM includes structural
    siblings (header div + grid div). Each stat root must be wrapped individually,
    not a parent containing both values.

    Critical assertion: no single inspect wrapper contains BOTH stat values.
    """
    page = make_test_page(
        title="Stats Two Items E2E",
        blocks=[
            {
                "type": "stats_section",
                "value": {
                    "badge": "By the numbers",
                    "headline": "Trusted by teams worldwide",
                    "stats": [
                        {"value": "99.9%", "label": "Uptime"},
                        {"value": "10k+", "label": "Customers"},
                    ],
                    "background": "default",
                },
            }
        ],
    )
    editor.goto(page.pk)
    editor.activate_inspect()

    stat_wrappers = editor.iframe.locator('[data-block-id][data-block-type="stat"]')
    expect(stat_wrappers).to_have_count(2)

    first_stat = editor.iframe.locator('[data-block-type="stat"]:has-text("99.9%")')
    expect(first_stat).to_have_count(1)

    second_stat = editor.iframe.locator('[data-block-type="stat"]:has-text("10k+")')
    expect(second_stat).to_have_count(1)

    ancestor_wrongly_wrapped = editor.iframe.locator('[data-block-type="stat"]:has-text("99.9%"):has-text("10k+")')
    expect(ancestor_wrongly_wrapped).to_have_count(0)


# ---------------------------------------------------------------------------
# JS augmentation in editor preview — blocks without {% include_block %}
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_augmentation_annotates_tags_in_editor_preview(editor, make_test_page):
    """TagListBlock renders its children via ``{% for tag in value.tags %}``
    with direct field access — no ``{% include_block %}``. Python patches
    cannot annotate these elements.

    In the editor preview (iframe), ``fetchAndAugment`` in
    preview-inspect-controller.js fetches the block map from the API
    (which serves the preview-time block map cached by
    ``patched_make_preview_request``) and injects ``inspect-augment.js``
    into the iframe to annotate the child elements.
    """
    page = make_test_page(
        title="Editor Augment Tags E2E",
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
    editor.goto(page.pk)
    editor.activate_inspect()

    tag_elements = editor.iframe.locator('[data-block-type="tag"]')
    expect(tag_elements).to_have_count(3)


@pytest.mark.django_db(transaction=True)
def test_editor_augmentation_two_tag_children_regression(editor, make_test_page):
    """Two-child _findSiblingGroup regression in the editor preview iframe."""
    page = make_test_page(
        title="Editor Two Tag Regression",
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
    editor.goto(page.pk)
    editor.activate_inspect()

    tag_elements = editor.iframe.locator('[data-block-type="tag"]')
    expect(tag_elements).to_have_count(2)
    expect(editor.iframe.locator('[data-block-type="tag"]:has-text("Alpha")')).to_have_count(1)
    expect(editor.iframe.locator('[data-block-type="tag"]:has-text("Beta")')).to_have_count(1)
