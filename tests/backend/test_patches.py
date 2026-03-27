"""Tests for the highest-risk behaviours in patches.py:

- _wrap_if_preview injects data-* attrs onto the root element when active with id
- _wrap_if_preview falls back to display:contents wrapper for text-only output
- _wrap_if_preview passes through when active but block has no id (plain BoundBlock)
- _wrap_if_preview passes through when preview is inactive
- _inject_attrs_into_root injects into the first element of the output
- apply_patches() is idempotent — calling twice does not lose the original method
- preview_active ContextVar is always reset, even when the original raises
- patched_list_value_iter yields plain values when preview is inactive
- patched ListValue.__iter__ yields _ListChildProxy with ids when preview is active
- ListValue.__iter__ is replaced after apply_patches()
"""

import pytest
from wagtail import blocks
from wagtail.blocks import BoundBlock
from wagtail.blocks.list_block import ListValue

import wagtail_inspect.patches as patches_module
from wagtail_inspect import preview_active
from wagtail_inspect.patches import (
    _inject_attrs_into_root,
    _is_multi_root_fragment,
    _ListChildProxy,
    _wrap_if_preview,
    apply_patches,
    patched_bound_block_render,
    patched_list_value_iter,
    patched_make_preview_request,
)

# ---------------------------------------------------------------------------
# Minimal stand-ins for BoundBlock subclasses
# ---------------------------------------------------------------------------


class _MockBlock:
    name = "text"
    label = "Text"


class _BoundBlockWithId:
    """Mimics StreamChild / ListChild — has a UUID."""

    id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    block_type = "text"
    block = _MockBlock()


class _BoundBlockWithoutId:
    """Mimics a plain BoundBlock — no UUID, must never be wrapped."""

    id = None
    block = _MockBlock()


# ---------------------------------------------------------------------------
# _wrap_if_preview
# ---------------------------------------------------------------------------


def test_wrap_if_preview_injects_into_root_element():
    """When the block output has an HTML element, the data-* attributes are
    injected directly onto it — no wrapper div and no display:contents.
    """
    token = preview_active.set(True)
    try:
        result = str(_wrap_if_preview(_BoundBlockWithId(), "<section>hello</section>"))
        assert result.startswith('<section data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"')
        assert 'data-block-type="text"' in result
        assert 'data-block-label="Text"' in result
        assert "hello" in result
        assert 'style="display:contents"' not in result
        assert "<div" not in result
    finally:
        preview_active.reset(token)


def test_wrap_if_preview_fallback_for_text_only_output():
    """When the block output is plain text (no HTML element), the display:contents
    wrapper is used as a fallback so the block remains queryable.
    """
    token = preview_active.set(True)
    try:
        result = str(_wrap_if_preview(_BoundBlockWithId(), "hello"))
        assert 'data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"' in result
        assert 'data-block-type="text"' in result
        assert 'style="display:contents"' in result
        assert "hello" in result
    finally:
        preview_active.reset(token)


def test_wrap_if_preview_multi_root_fragment_uses_display_contents_wrapper():
    """Markdown-style output with several top-level siblings must wrap the whole
    fragment so data-block-* is not applied only to the first <p>.
    """
    token = preview_active.set(True)
    try:
        fragment = "<p>first</p><p>second</p>"
        result = str(_wrap_if_preview(_BoundBlockWithId(), fragment))
        assert 'style="display:contents"' in result
        assert 'data-block-id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"' in result
        assert "first" in result and "second" in result
        assert "data-block-id" not in fragment  # inner HTML unchanged
        assert result.count("data-block-id=") == 1
        assert "<p" in result
        assert "data-block-id" not in result.split("<p", 1)[1].split(">", 1)[0]
    finally:
        preview_active.reset(token)


def test_wrap_if_preview_leading_comment_single_root_still_injects():
    """A leading HTML comment does not force multi-root wrapping."""
    token = preview_active.set(True)
    try:
        result = str(
            _wrap_if_preview(
                _BoundBlockWithId(),
                "<!-- note --><p>only</p>",
            )
        )
        assert 'style="display:contents"' not in result
        assert result.startswith("<!-- note --><p data-block-id=")
        assert "only" in result
    finally:
        preview_active.reset(token)


def test_fragment_needs_wrapper_text_before_element():
    assert _is_multi_root_fragment("intro<p>x</p>") is True


def test_fragment_needs_wrapper_false_for_single_div():
    assert _is_multi_root_fragment('<div class="md"><p>a</p></div>') is False


def test_fragment_needs_wrapper_false_for_void_img_only():
    """A lone void element is still a single top-level root."""
    assert _is_multi_root_fragment('<img src="/x.png" alt="">') is False


def test_fragment_needs_wrapper_true_for_void_img_followed_by_block_element():
    assert _is_multi_root_fragment("<img><p>a</p>") is True


def test_fragment_needs_wrapper_false_for_br_inside_single_p():
    """Void tags inside a non-void wrapper do not create extra top-level roots."""
    assert _is_multi_root_fragment("<p>line<br>break</p>") is False


def test_list_child_proxy_len_and_bool():
    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    token = preview_active.set(True)
    try:
        proxies = list(patched_list_value_iter(list_value))
    finally:
        preview_active.reset(token)

    assert len(proxies[0]) == 1
    assert bool(proxies[0]) is True
    assert len(proxies[1]) == 1
    assert bool(proxies[1]) is True


def test_list_child_proxy_bool_false_for_empty_string_char_child():
    list_block = blocks.ListBlock(blocks.CharBlock())
    list_value = list_block.to_python([""])

    token = preview_active.set(True)
    try:
        proxy = list(patched_list_value_iter(list_value))[0]
    finally:
        preview_active.reset(token)

    assert bool(proxy) is False


def test_inject_attrs_into_root_injects_before_existing_attrs():
    """Attributes are injected after the tag name, before any existing attrs."""
    output, ok = _inject_attrs_into_root('<div class="hero">content</div>', "id1", "hero", "Hero")
    assert ok
    assert output.startswith('<div data-block-id="id1"')
    assert 'class="hero"' in output
    assert "content" in output


def test_inject_attrs_into_root_handles_leading_whitespace():
    """Leading whitespace before the first tag is tolerated (common in Django templates)."""
    output, ok = _inject_attrs_into_root("\n  <a href='/'>link</a>", "id2", "cta", "CTA")
    assert ok
    assert 'data-block-id="id2"' in output
    assert "href='/'>" in output


def test_inject_attrs_into_root_returns_false_for_plain_text():
    """Plain text with no HTML element returns (original, False)."""
    original = "just text"
    output, ok = _inject_attrs_into_root(original, "id3", "text", "Text")
    assert not ok
    assert output == original


def test_inject_attrs_into_root_escapes_label():
    """Block labels with HTML special characters are escaped in the attribute value."""
    output, ok = _inject_attrs_into_root("<span>x</span>", "id4", "t", 'Say "hello" & more')
    assert ok
    assert 'data-block-label="Say &quot;hello&quot; &amp; more"' in output


def test_wrap_if_preview_skips_block_without_id_even_when_active():
    """Plain BoundBlock instances (no .id) must never be wrapped."""
    token = preview_active.set(True)
    try:
        result = _wrap_if_preview(_BoundBlockWithoutId(), "hello")
        assert result == "hello"
    finally:
        preview_active.reset(token)


def test_wrap_if_preview_skips_when_preview_is_inactive():
    """Outside of a preview request nothing should be wrapped."""
    assert preview_active.get() is False
    result = _wrap_if_preview(_BoundBlockWithId(), "hello")
    assert result == "hello"


# ---------------------------------------------------------------------------
# apply_patches() idempotency
# ---------------------------------------------------------------------------


def test_apply_patches_is_idempotent():
    """apply_patches() is already called once by AppConfig.ready().
    Calling it again must not overwrite the stored original — if it did,
    _originals["BoundBlock.render"] would point to the patched version,
    causing infinite recursion on every block render.
    """
    original_before = patches_module._originals["BoundBlock.render"]
    apply_patches()
    assert patches_module._originals["BoundBlock.render"] is original_before
    assert BoundBlock.render is patched_bound_block_render


# ---------------------------------------------------------------------------
# ContextVar reset
# ---------------------------------------------------------------------------


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
        assert preview_active.get() is False
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


def test_preview_active_always_reset_when_original_raises():
    """The `finally` block in patched_make_preview_request guarantees that
    preview_active is reset even when the underlying request handler raises.
    Without it every subsequent request would have blocks wrapped.
    """
    key = "PreviewableMixin.make_preview_request"
    saved = patches_module._originals[key]

    def _raising(*args, **kwargs):
        raise RuntimeError("simulated failure")

    patches_module._originals[key] = _raising
    try:
        with pytest.raises(RuntimeError):
            patched_make_preview_request(object(), original_request=None)
        assert preview_active.get() is False
    finally:
        patches_module._originals[key] = saved


# ---------------------------------------------------------------------------
# ListValue.__iter__ patch (preview-gated)
# ---------------------------------------------------------------------------


def test_patched_list_value_iter_yields_plain_values_when_preview_inactive():
    """Outside preview, iteration matches stock Wagtail (plain child values)."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    assert preview_active.get() is False
    iterated = list(patched_list_value_iter(list_value))
    assert len(iterated) == 2
    assert iterated[0] is list_value.bound_blocks[0].value
    assert iterated[1] is list_value.bound_blocks[1].value


def test_patched_list_value_iter_preview_yields_proxies_with_bound_block_face():
    """During preview, each item is a _ListChildProxy: .id and render_as_block
    for inspect, while .value matches the underlying ListChild.value.
    """

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "a"}, {"title": "b"}])

    token = preview_active.set(True)
    try:
        iterated = list(patched_list_value_iter(list_value))
    finally:
        preview_active.reset(token)

    assert len(iterated) == 2
    for i, proxy in enumerate(iterated):
        assert isinstance(proxy, _ListChildProxy)
        assert proxy.id == list_value.bound_blocks[i].id
        assert proxy.value is list_value.bound_blocks[i].value
        assert hasattr(proxy, "render_as_block")


def test_patched_list_value_iter_preview_proxy_delegates_struct_fields():
    """Dot and key access resolve like the plain StructValue (mapping tried first)."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "nested"}])

    token = preview_active.set(True)
    try:
        proxy = list(patched_list_value_iter(list_value))[0]
    finally:
        preview_active.reset(token)

    assert proxy.title == "nested"
    assert proxy["title"] == "nested"


def test_patched_list_value_iter_preview_proxy_iterates_stream_value():
    """``for block in item`` in templates maps to iter(proxy.value) for StreamValue children."""
    stream_block = blocks.StreamBlock([("text", blocks.CharBlock())])
    list_block = blocks.ListBlock(stream_block)
    # One list item = one stream (list of block dicts)
    list_value = list_block.to_python([[{"type": "text", "value": "hello"}]])

    token = preview_active.set(True)
    try:
        proxy = list(patched_list_value_iter(list_value))[0]
    finally:
        preview_active.reset(token)

    inner = list(proxy)
    assert len(inner) == 1
    assert inner[0].value == "hello"


def test_patched_list_value_iter_preview_proxy_str_uses_plain_value():
    """``{{ item }}`` should stringify the child value, not BoundBlock HTML."""
    list_block = blocks.ListBlock(blocks.CharBlock())
    list_value = list_block.to_python(["plain"])

    token = preview_active.set(True)
    try:
        proxy = list(patched_list_value_iter(list_value))[0]
    finally:
        preview_active.reset(token)

    assert str(proxy) == "plain"


def test_list_value_iteration_uses_patched_iter_on_class_non_preview():
    """``list(ListValue)`` with preview off yields plain values."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "x"}])

    assert preview_active.get() is False
    iterated = list(list_value)
    assert len(iterated) == 1
    assert iterated[0] is list_value.bound_blocks[0].value


def test_list_value_iteration_uses_patched_iter_on_class_preview():
    """``list(ListValue)`` with preview on yields _ListChildProxy instances."""

    class _Item(blocks.StructBlock):
        title = blocks.CharBlock()

        class Meta:
            label = "Item"

    list_block = blocks.ListBlock(_Item())
    list_value = list_block.to_python([{"title": "x"}])

    token = preview_active.set(True)
    try:
        iterated = list(list_value)
    finally:
        preview_active.reset(token)

    assert len(iterated) == 1
    assert isinstance(iterated[0], _ListChildProxy)
    assert iterated[0].value is list_value.bound_blocks[0].value


def test_list_value_iter_patch_applied_at_startup():
    """apply_patches() installs ListValue.__iter__ replacement exactly once."""
    assert "ListValue.__iter__" in patches_module._originals
    assert ListValue.__dict__.get("__iter__") is patched_list_value_iter
