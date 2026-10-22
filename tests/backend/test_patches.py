"""Inspect's patches. Block marking itself is tested in wagtail-block-ids.

- make_preview_request renders inside a wrapping marking scope, forwards arguments,
  snapshots the block map, and always closes the scope
- the live-page marker accepts editors only, and respects WAGTAIL_INSPECT_LIVE_PAGES
- apply_patches() is idempotent and registers the live-page marker once
"""

import json
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from wagtail_block_ids import is_marking
from wagtail_block_ids import marks as block_ids_marks

import wagtail_inspect.patches as patches_module
from wagtail_inspect.block_map import block_map_for
from wagtail_inspect.patches import apply_patches, mark_live_page, patched_make_preview_request


def test_make_preview_request_renders_inside_a_wrapping_scope():
    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]
    seen = []
    patches_module._originals[key] = lambda self, *a, **kw: seen.append(block_ids_marks._scope.get())
    try:
        patched_make_preview_request(object())
    finally:
        patches_module._originals[key] = saved

    assert seen[0] is not None
    assert seen[0].wrap is True
    assert not is_marking()


def test_patched_make_preview_request_forwards_unknown_kwargs():
    """Future Wagtail versions may add parameters to make_preview_request.
    The patch must forward them rather than silently dropping them.
    """
    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]
    captured = {}

    def _capturing(self_arg, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    patches_module._originals[key] = _capturing
    try:
        patched_make_preview_request(
            object(),
            "positional_request",
            preview_mode="edit",
            extra_new_param="surprise",
        )
        assert captured["args"] == ("positional_request",)
        assert captured["kwargs"] == {
            "preview_mode": "edit",
            "extra_new_param": "surprise",
        }
        assert not is_marking()
    finally:
        patches_module._originals[key] = saved


@pytest.fixture
def preview_original():
    """Swap in a no-op original ``make_preview_request`` for the test."""
    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]
    patches_module._originals[key] = lambda self, *a, **kw: "ok-response"
    yield
    patches_module._originals[key] = saved
    cache.clear()


@pytest.mark.django_db
@pytest.mark.parametrize("by_keyword", [False, True])
def test_make_preview_request_remembers_the_editors_preview(preview_original, root_page, django_user_model, by_keyword):
    """The preview map is kept for the editor in ``original_request``, however it is passed."""
    from testapp.models import TestPage

    page = root_page.add_child(instance=TestPage(title="Saved", slug="saved"))
    editor = django_user_model.objects.create_user(username="editor")
    request = SimpleNamespace(user=editor)
    preview = TestPage(pk=page.pk, body=json.dumps([{"type": "text", "id": "unsaved", "value": "x"}]))

    args, kwargs = ((), {"original_request": request}) if by_keyword else ((request,), {})
    assert patched_make_preview_request(preview, *args, **kwargs) == "ok-response"

    assert list(block_map_for(page, editor)) == ["unsaved"]


def test_make_preview_request_without_a_request_remembers_nothing(preview_original, monkeypatch):
    """Previews rendered outside an editor's request (no user) are not kept."""
    calls = []
    monkeypatch.setattr(patches_module, "remember_preview", lambda obj, user: calls.append(user))

    patched_make_preview_request(SimpleNamespace(pk=1))

    assert calls == [None]


def test_marking_always_closed_when_original_raises():
    """The marking scope around make_preview_request closes even when the
    underlying request handler raises. Otherwise every later request would be marked.
    """
    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]

    def _raising(*args, **kwargs):
        raise RuntimeError("simulated failure")

    patches_module._originals[key] = _raising
    try:
        with pytest.raises(RuntimeError):
            patched_make_preview_request(object(), original_request=None)
        assert not is_marking()
    finally:
        patches_module._originals[key] = saved


# ---------------------------------------------------------------------------
# Live-page marker
# ---------------------------------------------------------------------------


class _ServePage:
    def __init__(self, *, editable):
        self.pk = 1
        self._editable = editable

    def permissions_for_user(self, user):
        editable = self._editable
        return type("P", (), {"can_edit": lambda self: editable})()


def _serve_request(*, authenticated=True):
    return SimpleNamespace(user=SimpleNamespace(is_authenticated=authenticated))


def test_live_page_marker_accepts_editors():
    assert mark_live_page(_ServePage(editable=True), _serve_request()) is True


@pytest.mark.parametrize(
    ("page", "request_kwargs"),
    [
        (_ServePage(editable=True), {"authenticated": False}),
        (_ServePage(editable=False), {}),
    ],
    ids=["anonymous", "non-editor"],
)
def test_live_page_marker_leaves_other_visitors_untouched(page, request_kwargs):
    assert mark_live_page(page, _serve_request(**request_kwargs)) is False


def test_live_page_marker_respects_live_pages_setting(settings):
    settings.WAGTAIL_INSPECT_LIVE_PAGES = False

    assert mark_live_page(_ServePage(editable=True), _serve_request()) is False


def test_apply_patches_registers_the_wrapping_live_marker_once():
    apply_patches()
    apply_patches()

    registered = [marker for marker in block_ids_marks._markers if marker.should_mark is mark_live_page]
    assert len(registered) == 1
    assert registered[0].wrap is True


def test_apply_patches_is_idempotent():
    from wagtail_inspect.patches import PreviewableMixin

    original_before = patches_module._originals["PreviewableMixin.make_preview_request"]
    apply_patches()
    assert patches_module._originals["PreviewableMixin.make_preview_request"] is original_before
    assert PreviewableMixin.make_preview_request is patched_make_preview_request
