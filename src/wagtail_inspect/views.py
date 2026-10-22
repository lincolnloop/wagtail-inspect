"""JSON block map API for inspect augment (GET …/page/<id>/)."""

from django.http import HttpResponse, JsonResponse
from django.views import View
from wagtail.models import Page

from .block_map import block_map_for


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

        # Userbar on a live page asks for the published body it rendered.
        live = request.GET.get("source") == "live"
        return JsonResponse({"blocks": block_map_for(page, request.user, live=live)})
