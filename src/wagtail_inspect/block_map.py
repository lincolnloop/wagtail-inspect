"""Flat block map from StreamField trees for the inspect API and JS augment.

The walk itself (``blocks_for_field``, ``resolve_block_type``, ``resolve_block_label``)
lives in wagtail-block-ids; it is re-exported here.
"""

from wagtail_block_ids import blocks_for_field, resolve_block_label, resolve_block_type, stream_values

__all__ = ["blocks_for_field", "flat_block_map_for_instance", "resolve_block_label", "resolve_block_type"]


def flat_block_map_for_instance(page):
    """``{uuid: {type, label, children}}`` for all StreamFields on *page*."""
    entries = [info for _name, value in stream_values(page) for info in blocks_for_field(value) if info.id]
    result = {str(info.id): {"type": info.type, "label": info.label, "children": []} for info in entries}
    for info in entries:
        parent = result.get(str(info.parent_id)) if info.parent_id else None
        if parent is not None:
            parent["children"].append(str(info.id))
    return result
