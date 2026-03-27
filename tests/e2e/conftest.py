"""E2E test infrastructure for wagtail-inspect.

All fixtures are function-scoped so pytest-django's database access control
is satisfied without scope conflicts between the session-scoped playwright
fixtures and the function-scoped transactional_db fixture.

The live server serves the Django app in a thread.  Using `transactional_db`
(instead of `db`) ensures data is committed and visible to that thread.
A file-based SQLite database (configured in tests/e2e/settings.py) is used
so the live server thread can open the same file as the test thread —
`:memory:` databases are per-connection and invisible across threads.
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from playwright.sync_api import expect
from testapp.models import TestPage
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

_E2E_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "test_data.json"

# ---------------------------------------------------------------------------
# Django DB fixtures (function-scoped, transactional so live server sees data)
# ---------------------------------------------------------------------------


# Multi-block StreamField body for one “kitchen sink” page without maintaining
# test_data.json — same mental model as dump-fixture (root + one rich child),
# but built in code. Pass as ``make_test_page(blocks=COMPLETE_E2E_PAGE_BLOCKS)``.
COMPLETE_E2E_PAGE_BLOCKS = [
    {"type": "text", "value": "E2E complete page — text block."},
    {
        "type": "rich_text",
        "value": "<p>E2E complete page — <strong>rich text</strong>.</p>",
    },
    {
        "type": "hero",
        "value": {
            "heading": "Complete E2E hero",
            "subheading": "One page with several block types",
            "body": "",
            "buttons": [{"label": "Learn more", "href": "https://example.com"}],
        },
    },
    {
        "type": "stats_section",
        "value": {
            "badge": "Stats",
            "headline": "Numbers",
            "stats": [
                {"value": "99%", "label": "Ready"},
                {"value": "1", "label": "Page"},
            ],
            "background": "default",
        },
    },
]


@pytest.fixture
def loaded_fixture_data(transactional_db):
    """Load ``tests/e2e/fixtures/test_data.json`` (from ``just dump-fixture``).

    pytest-django flushes the database between E2E tests, so this fixture is
    function-scoped: each test that requests it gets a fresh ``loaddata``.

    Default E2E tests use ``superuser`` + ``wagtail_site`` + ``make_test_page``
    (one user, site/root, one child page) and do not need this file. Use
    ``loaddata`` only when you must mirror a specific CMS export; keep the
    source database trimmed to that user and one content page if you want a
    small JSON file.
    """
    if not _E2E_FIXTURE_PATH.is_file():
        pytest.skip(f"Missing E2E fixture at {_E2E_FIXTURE_PATH}; run `just dump-fixture`")
    raw = _E2E_FIXTURE_PATH.read_text().strip()
    if raw in ("", "[]"):
        return
    call_command("loaddata", str(_E2E_FIXTURE_PATH))


@pytest.fixture
def superuser(transactional_db):
    user, _ = User.objects.get_or_create(
        username="admin",
        defaults={"email": "admin@example.com", "is_superuser": True, "is_staff": True},
    )
    user.set_password("password")
    user.save()
    return user


@pytest.fixture
def default_locale(transactional_db):
    """Wagtail's post-migrate signal creates an initial Locale row, but
    transactional_db teardown flushes all rows between tests (including that
    Locale). Recreate it so Page.add_root() and other Wagtail operations that
    depend on a default Locale succeed in every test.
    """
    # Wagtail resolves the language code via get_supported_content_language_variant
    # (e.g. 'en-us' → 'en') before looking up or creating the Locale, so we
    # must use the resolved variant to avoid a Locale.DoesNotExist on page save.
    language_code = get_supported_content_language_variant(settings.LANGUAGE_CODE)
    locale, _ = Locale.objects.get_or_create(language_code=language_code)
    return locale


@pytest.fixture
def root_page(transactional_db, default_locale):
    return Page.add_root(title="Root", slug="root")


@pytest.fixture
def wagtail_site(transactional_db, root_page, live_server):
    port = int(live_server.url.split(":")[-1])
    return Site.objects.create(
        hostname="localhost",
        port=port,
        root_page=root_page,
        is_default_site=True,
    )


@pytest.fixture
def make_test_page(transactional_db, root_page, wagtail_site):
    """Factory fixture. Returns a callable that creates a published TestPage under
    ``root_page`` (sibling to the live server's site root — same idea as
    “root + one content page”).

    Usage::

        def test_something(make_test_page):
            page = make_test_page(blocks=[{"type": "text", "value": "Hello"}])


        def test_kitchen_sink(make_test_page):
            page = make_test_page(
                title="Kitchen sink",
                blocks=COMPLETE_E2E_PAGE_BLOCKS,
            )
    """

    def _make(title="E2E Page", blocks=None):
        blocks = blocks or [{"type": "text", "value": "E2E_INSPECT_TARGET"}]
        return root_page.add_child(
            instance=TestPage(
                title=title,
                slug=title.lower().replace(" ", "-"),
                body=blocks,
                live=True,
            )
        )

    return _make


# ---------------------------------------------------------------------------
# Playwright context — base_url
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, live_server):
    """Set base_url once for all tests so page.goto("/cms/") works everywhere.

    The 1920x1080 viewport ensures the Wagtail editor renders in its wide-screen
    split-view layout where the preview panel (and our injected inspect button)
    is visible. At the default 1280×720 the panel can be below Wagtail's
    responsive breakpoint and the button stays hidden.
    """
    return {
        **browser_context_args,
        "base_url": live_server.url,
        "viewport": {"width": 1920, "height": 1080},
    }


# ---------------------------------------------------------------------------
# Authenticated Playwright page (logs in per test)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_page(page, live_server, superuser, wagtail_site):
    """A Playwright Page authenticated as the Wagtail admin superuser.

    Depends on ``wagtail_site`` (and thus the tree ``root_page``) so the
    post-login redirect to ``/cms/`` always runs against a non-empty page tree.
    Without that, Wagtail's dashboard can call ``wagtailadmin_explore`` with an
    empty parent id (``root_page`` is None in the site summary), raising
    ``NoReverseMatch``.

    Logs in on every test. Session-scoped caching via storage_state can be
    added later once all tests are green.
    """
    page.goto(f"{live_server.url}/cms/login/")
    page.fill('[name="username"]', "admin")
    page.fill('[name="password"]', "password")
    page.click('[type="submit"]')
    page.wait_for_url("**/cms/")
    return page


# ---------------------------------------------------------------------------
# Page Object Model
# ---------------------------------------------------------------------------


class EditorPreviewPage:
    """Wraps interactions with the Wagtail editor page (/cms/pages/{id}/edit/).

    The preview panel renders the page inside an <iframe>. The crosshairs
    (Inspect) button is injected into the preview toolbar by
    preview-inspect-controller.js with the attribute [data-preview-inspect-button].
    """

    def __init__(self, page):
        self.page = page
        self.iframe = page.frame_locator('[data-w-preview-target="iframe"]').first

    def goto(self, page_id):
        self.page.goto(f"/cms/pages/{page_id}/edit/")
        # The preview side panel is collapsed by default. Open it.
        self.page.locator('[data-side-panel-toggle="preview"]').click()
        # Wait for the iframe to appear inside the now-open panel.
        self.page.wait_for_selector('[data-w-preview-target="iframe"]', state="attached")
        # Our JS (preview-inspect-controller.js) injects the button once connected.
        self.page.wait_for_selector("[data-preview-inspect-button]")

    def wait_for_preview_block_elements(self, timeout: float = 30_000) -> None:
        """Wait until the preview iframe contains at least one annotated block.

        The toolbar and iframe shell can appear before preview HTML (and
        ``data-block-id``) finishes rendering.
        """
        expect(self.iframe.locator("[data-block-id]").first).to_be_attached(timeout=timeout)

    def activate_inspect(self):
        self.page.locator("[data-preview-inspect-button]").click()
        # The overlay starts with display:none and only becomes visible on block
        # hover. Wait for it to be attached (created) to confirm activate() ran.
        self.iframe.locator("#wagtail-inspect-overlay").wait_for(state="attached")

    def click_first_block(self):
        self.iframe.locator("[data-block-id]").first.click()

    def press_escape(self):
        self.page.keyboard.press("Escape")


class StandalonePreviewPage:
    """Wraps interactions with the standalone Wagtail preview page
    (/cms/pages/{id}/preview/).

    Wagtail's PreviewOnEdit view requires a prior POST to store preview data
    in the session before a GET can render the page. Without the POST, the GET
    returns a "preview unavailable" error page instead of the actual content.

    The editor's w-preview Stimulus controller performs that POST automatically
    when the preview panel opens. `goto()` therefore visits the editor first,
    opens the panel to trigger the POST, then navigates to the preview URL
    directly — which now has session data and renders the page with
    is_preview=True, allowing the wagtail-userbar to appear.

    Playwright's pierce/ CSS selector engine is used to reach elements
    inside the userbar shadow DOM without manually traversing shadowRoot.
    """

    def __init__(self, page):
        self.page = page

    def goto(self, page_id):
        # 1. Open the editor — the w-preview Stimulus controller connects and
        #    automatically POSTs the page form data to set up the preview session.
        self.page.goto(f"/cms/pages/{page_id}/edit/")
        self.page.wait_for_url(f"**/cms/pages/{page_id}/edit/**")

        # 2. Open the preview side panel so the panel renders and its
        #    "Preview in new tab" link is available.
        self.page.locator('[data-side-panel-toggle="preview"]').click()
        self.page.wait_for_selector('[data-w-preview-target="iframe"]', state="attached")

        # 3. Wait for network idle so the w-preview POST has completed and the
        #    preview session is stored before we open the new tab.
        self.page.wait_for_load_state("networkidle")

        # 4. Click "Preview in new tab" and capture the popup.
        #    Wagtail manages the session and URL — we don't need to know the URL.
        #    The popup is a real browser tab with is_preview=True and the userbar.
        with self.page.expect_popup() as popup_info:
            self.page.locator('[data-w-preview-target="newTab"]').click()
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded")

        # Replace self.page with the popup so all subsequent locator calls
        # operate on the standalone preview tab.
        self.page = popup
        # The userbar custom element is in the DOM but may be considered
        # "hidden" by Playwright until its internal CSS animation completes.
        # Wait for it to be attached, then interact via pierce/ selector.
        self.page.wait_for_selector("wagtail-userbar", state="attached")

    def open_userbar_menu(self):
        """Open the Wagtail userbar menu (collapsed by default).

        Playwright's CSS locator already pierces open shadow DOM, so no
        special prefix is needed to reach elements inside <wagtail-userbar>.
        """
        self.page.locator("#wagtail-userbar-trigger").click()

    def activate_inspect(self):
        # Open the Wagtail userbar menu, then click our "Inspect blocks" button.
        self.open_userbar_menu()
        self.page.locator("#inspect-blocks-trigger").click()
        # The overlay starts hidden; wait for it to be attached (created).
        self.page.locator("#wagtail-inspect-overlay").wait_for(state="attached")

    def click_first_block(self):
        self.page.locator("[data-block-id]").first.click()

    def click_nth_block(self, n: int) -> str:
        """Scroll the nth [data-block-id] element into view, click it, and
        return its block UUID so callers can assert the editor state.
        """
        block = self.page.locator("[data-block-id]").nth(n)
        block_id = block.get_attribute("data-block-id")
        block.scroll_into_view_if_needed()
        block.click()
        return block_id

    def press_escape(self):
        self.page.keyboard.press("Escape")


@pytest.fixture
def editor(auth_page):
    """EditorPreviewPage POM backed by an authenticated Playwright page."""
    return EditorPreviewPage(auth_page)


@pytest.fixture
def preview(auth_page):
    """StandalonePreviewPage POM backed by an authenticated Playwright page."""
    return StandalonePreviewPage(auth_page)
