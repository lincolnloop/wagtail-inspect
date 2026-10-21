"""Inspect's patches. Block marking itself is tested in wagtail-block-ids.

- make_preview_request renders inside a wrapping marking scope, forwards arguments,
  snapshots the block map, and always closes the scope
- the live-page marker accepts editors only, and respects WAGTAIL_INSPECT_LIVE_PAGES
- apply_patches() is idempotent and registers the live-page marker once
"""

from types import SimpleNamespace

import pytest
from wagtail_block_ids import is_marking
from wagtail_block_ids import marks as block_ids_marks

import wagtail_inspect.patches as patches_module
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


def test_make_preview_request_snapshots_block_map_into_preview_maps(monkeypatch):
    """After make_preview_request returns, _preview_block_maps[pk] holds the
    flat map from flat_block_map_for_instance(self).
    """
    import wagtail_inspect

    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]
    fake_map = {"snap-uuid": {"type": "hero", "label": "Hero", "children": []}}

    class FakePage:
        pk = 4242

    monkeypatch.setattr(
        "wagtail_inspect.block_map.flat_block_map_for_instance",
        lambda page: fake_map,
    )
    patches_module._originals[key] = lambda self, *a, **kw: "ok-response"
    try:
        out = patched_make_preview_request(FakePage())
        assert out == "ok-response"
        assert wagtail_inspect._preview_block_maps[4242] is fake_map
    finally:
        patches_module._originals[key] = saved
        wagtail_inspect._preview_block_maps.pop(4242, None)


def test_make_preview_request_skips_snapshot_when_no_pk(monkeypatch):
    """Objects without .pk must not write to _preview_block_maps."""
    import wagtail_inspect

    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]
    called = []

    monkeypatch.setattr(
        "wagtail_inspect.block_map.flat_block_map_for_instance",
        lambda page: called.append(page) or {},
    )
    patches_module._originals[key] = lambda self, *a, **kw: None
    try:
        before = dict(wagtail_inspect._preview_block_maps)
        patched_make_preview_request(object())
        assert called == []
        assert dict(wagtail_inspect._preview_block_maps) == before
    finally:
        patches_module._originals[key] = saved


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
