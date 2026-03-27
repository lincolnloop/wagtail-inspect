"""Flat block map from StreamField trees for the inspect API and JS augment."""

import re

from django.utils.text import capfirst
from wagtail.blocks import StreamValue
from wagtail.blocks.list_block import ListValue
from wagtail.fields import StreamField


def _label_from_class_name(block):
    """Label from class name for user blocks; wagtail.* classes → ``Item``."""
    cls = type(block)
    if (cls.__module__ or "").startswith("wagtail."):
        return "Item"
    name = cls.__name__
    if name.endswith("Block"):
        name = name[: -len("Block")]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name) or "Item"


def _singularize_name(name):
    """Strip trailing ``s`` for list field names (naive)."""
    if name and name.endswith("s"):
        return name[:-1]
    return name


def _parent_label_from_list_block(list_block):
    """Singular list child label from the ListBlock's ``name``."""
    name = getattr(list_block, "name", "") or ""
    if not name:
        return ""
    singular = _singularize_name(name)
    return capfirst(singular.replace("_", " "))


def resolve_block_type(block_holder, parent_label=""):
    """Type slug for StreamChild / ListChild / BoundBlock-like holders."""
    block = getattr(block_holder, "block", None)
    block_type = getattr(block_holder, "block_type", None)

    if not block_type and block:
        label = block.name or block.label or _label_from_class_name(block)
        if label != "Item":
            block_type = label

    if not block_type:
        block_type = parent_label or "item"

    return block_type.lower().replace(" ", "_")


def resolve_block_label(block_holder, parent_label=""):
    """Human label for block holders; falls back to *parent_label* or ``Item``."""
    block = getattr(block_holder, "block", None)
    if block:
        label = block.label or _label_from_class_name(block)
        if label != "Item":
            return label
    return parent_label or "Item"


def blocks_for_field(stream_value, parent_id=None):
    """Yield ``(uuid, block_type, block_label, parent_id)`` for stream/list nesting."""
    for child in stream_value:
        block_type = resolve_block_type(child)
        block_label = resolve_block_label(child)
        yield child.id, block_type, block_label, parent_id
        yield from _recurse_value(child.value, parent_id=child.id)


def _recurse_value(value, parent_id=None):
    if isinstance(value, StreamValue):
        yield from blocks_for_field(value, parent_id=parent_id)
    elif isinstance(value, ListValue):
        list_block = getattr(value, "list_block", None)
        parent_label = _parent_label_from_list_block(list_block) if list_block else ""
        for child in value.bound_blocks:
            if isinstance(child, str):
                continue

            block_type = resolve_block_type(child, parent_label)
            block_label = resolve_block_label(child, parent_label)
            yield child.id, block_type, block_label, parent_id
            yield from _recurse_value(child.value, parent_id=child.id)
    elif isinstance(value, dict):
        for field_value in value.values():
            yield from _recurse_value(field_value, parent_id=parent_id)


def flat_block_map_for_instance(page):
    """``{uuid: {type, label, children}}`` for all StreamFields on *page*."""
    entries = []
    for field in page._meta.get_fields():
        if not isinstance(field, StreamField):
            continue
        sv = getattr(page, field.name, None)
        if not sv:
            continue
        entries.extend(blocks_for_field(sv))

    result = {}

    for uuid, block_type, block_label, _parent_id in entries:
        if not uuid:
            continue
        result[str(uuid)] = {
            "type": block_type,
            "label": block_label,
            "children": [],
        }

    for uuid, _block_type, _block_label, parent_id in entries:
        if uuid and parent_id:
            str_parent = str(parent_id)
            str_uuid = str(uuid)
            if str_parent in result and str_uuid in result:
                result[str_parent]["children"].append(str_uuid)

    return result
