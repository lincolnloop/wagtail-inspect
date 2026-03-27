"""Wagtail admin hooks and userbar item for inspect."""

from django.http import HttpRequest
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from wagtail import hooks
from wagtail.admin.userbar import BaseItem
from wagtail.models import Page


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
        '<script>window.wagtailInspectConfig={{"apiBase":"{}","augmentScriptUrl":"{}"}};</script>',
        api_base,
        static("wagtail_inspect/js/inspect-augment.js"),
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

    def __init__(self, page: Page) -> None:
        self.page = page

    def get_context_data(self, parent_context) -> dict:
        context = super().get_context_data(parent_context)
        context["inspect_preview_context"] = {
            "pageId": self.page.pk,
            "editUrl": reverse("wagtailadmin_pages:edit", args=[self.page.pk]),
            "apiUrl": reverse("wagtail_inspect_page_api", args=[self.page.pk]),
        }
        context["css_url"] = static("wagtail_inspect/css/preview-inspect.css")
        context["core_js_url"] = static("wagtail_inspect/js/inspect-core.js")
        context["augment_js_url"] = static("wagtail_inspect/js/inspect-augment.js")
        context["userbar_js_url"] = static("wagtail_inspect/js/userbar-inspect.js")
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
    if not page or not page.id:
        return

    if not getattr(request, "is_preview", False):
        return

    items.append(InspectBlocksUserbarItem(page))
