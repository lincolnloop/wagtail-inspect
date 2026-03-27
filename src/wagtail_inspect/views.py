"""JSON block map API for inspect augment (GET …/page/<id>/)."""

from django.http import HttpResponse, JsonResponse
from django.views import View
from wagtail.models import Page

from .block_map import flat_block_map_for_instance


class PageInspectView(View):
    def get(self, request, page_id):
        if not request.user.is_authenticated:
            return HttpResponse(status=401)

        try:
            page = Page.objects.get(pk=page_id).specific
        except Page.DoesNotExist:
            return HttpResponse(status=404)

        if not page.permissions_for_user(request.user).can_edit():
            return HttpResponse(status=403)

        from . import _preview_block_maps

        if page.pk in _preview_block_maps:
            return JsonResponse({"blocks": _preview_block_maps[page.pk]})

        revision = page.get_latest_revision()
        instance = revision.as_object() if revision else page

        return JsonResponse({"blocks": flat_block_map_for_instance(instance)})
