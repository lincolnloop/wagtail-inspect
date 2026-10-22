"""Wagtail admin hooks and userbar item for inspect."""

from django.forms import Media
from django.http import HttpRequest
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.admin.userbar import BaseItem
from wagtail.models import Page

from . import inspect_live_pages_enabled, user_can_inspect

# Wagtail 7.3 made userbar items components: ``template_name``, ``media`` and
# ``render_html``. Older userbars ignore ``media``, so the item could only load its
# scripts inline, which a strict script-src CSP blocks. There, inspect stays in the
# editor's preview panel and the userbar item is left out.
USERBAR_ITEMS_ARE_COMPONENTS = issubclass(BaseItem, Component)


@hooks.register("insert_global_admin_css")
def global_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("wagtail_inspect/css/preview-inspect.css"),
    )


@hooks.register("insert_global_admin_js")
def global_admin_js():
    sample_url = reverse("wagtail_inspect_page_api", args=[0])
    api_base = sample_url[: sample_url.rfind("/0/")] + "/"

    config_script = format_html(
        '<script>window.wagtailInspectConfig={{"apiBase":"{}","augmentScriptUrl":"{}","cssUrl":"{}"}};</script>',
        api_base,
        static("wagtail_inspect/js/inspect-augment.js"),
        static("wagtail_inspect/css/preview-inspect.css"),
    )

    js_files = [
        "wagtail_inspect/js/inspect-core.js",
        "wagtail_inspect/js/preview-inspect-helpers.js",
        "wagtail_inspect/js/preview-inspect-controller.js",
    ]
    scripts = format_html_join(
        "\n",
        '<script src="{}"></script>',
        ((static(f),) for f in js_files),
    )
    return config_script + scripts


class InspectBlocksUserbarItem(BaseItem):
    template_name = "wagtail_inspect/userbar/item_inspect_preview.html"

    def __init__(self, page: Page, *, live: bool = False) -> None:
        super().__init__()
        self.page = page
        # Live (published) page rather than a preview: the block map must come from
        # the live page, not the latest draft, so ids match what is rendered.
        self.live = live

    @property
    def media(self) -> Media:
        # Wagtail puts ``media.css`` in the userbar shadow root and ``media.js``
        # after ``<wagtail-userbar>`` as external scripts, so a strict
        # ``script-src`` CSP (nonce, no ``'unsafe-inline'``) still allows them.
        # Order matters: core → augment → userbar.
        return Media(
            css={"all": ["wagtail_inspect/css/preview-inspect.css"]},
            js=[
                "wagtail_inspect/js/inspect-core.js",
                "wagtail_inspect/js/inspect-augment.js",
                "wagtail_inspect/js/userbar-inspect.js",
            ],
        )

    def get_context_data(self, parent_context) -> dict:
        context = super().get_context_data(parent_context)
        context["inspect_preview_context"] = {
            "pageId": self.page.pk,
            "editUrl": reverse("wagtailadmin_pages:edit", args=[self.page.pk]),
            "apiUrl": reverse("wagtail_inspect_page_api", args=[self.page.pk]) + ("?source=live" if self.live else ""),
            # The overlay lives in the page, outside the userbar shadow root where
            # ``media.css`` lands, so inspect-core links this into the page itself.
            "cssUrl": static("wagtail_inspect/css/preview-inspect.css"),
        }
        return context


@hooks.register("register_admin_urls")
def register_inspect_api_url():
    from .views import PageInspectView

    return [
        path(
            "wagtail-inspect/api/page/<int:page_id>/",
            PageInspectView.as_view(),
            name="wagtail_inspect_page_api",
        ),
    ]


@hooks.register("construct_wagtail_userbar")
def add_inspect_blocks_item(request: HttpRequest, items: list, page: Page) -> None:
    if not USERBAR_ITEMS_ARE_COMPONENTS:
        return

    if not page or not page.id:
        return

    # The editor preview panel hides the userbar; preview-inspect-controller.js
    # drives inspect there from the admin side instead.
    if getattr(request, "in_preview_panel", False):
        return

    is_preview = bool(getattr(request, "is_preview", False))
    if not is_preview and not inspect_live_pages_enabled():
        return

    if not user_can_inspect(page, getattr(request, "user", None)):
        return

    items.append(InspectBlocksUserbarItem(page, live=not is_preview))
