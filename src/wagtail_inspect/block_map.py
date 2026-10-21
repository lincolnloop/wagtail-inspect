"""Flat block map from StreamField trees for the inspect API and JS augment.

The walk itself (``blocks_for_field``, ``resolve_block_type``, ``resolve_block_label``)
lives in wagtail-block-ids; it is re-exported here.
"""

from wagtail.fields import StreamField
from wagtail_block_ids import blocks_for_field, resolve_block_label, resolve_block_type

__all__ = ["blocks_for_field", "flat_block_map_for_instance", "resolve_block_label", "resolve_block_type"]


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
