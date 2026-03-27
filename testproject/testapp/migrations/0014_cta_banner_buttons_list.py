import uuid

from django.db import migrations


def _extract_button_value(raw):
    """Extract the ButtonBlock dict from either a plain dict or a ListBlock item dict."""
    if isinstance(raw, dict) and "value" in raw and isinstance(raw["value"], dict):
        return raw["value"]
    if isinstance(raw, dict):
        return raw
    return None


def _make_list_item(button_dict):
    """Wrap a ButtonBlock dict as a Wagtail ListBlock item."""
    return {
        "type": "item",
        "id": str(uuid.uuid4()),
        "value": button_dict,
    }


def cta_banner_to_buttons_list_forwards(apps, schema_editor):
    TestPage = apps.get_model("testapp", "TestPage")
    for page in TestPage.objects.all().iterator():
        stream = page.body
        if stream is None:
            continue
        raw = getattr(stream, "raw_data", None)
        if raw is None:
            continue
        new_blocks = []
        any_changed = False
        for block in raw:
            if not isinstance(block, dict) or block.get("type") != "cta_banner":
                new_blocks.append(block)
                continue
            val = block.get("value")
            if not isinstance(val, dict):
                new_blocks.append(block)
                continue
            if "primary_cta" not in val and "secondary_cta" not in val:
                new_blocks.append(block)
                continue
            buttons = []
            primary = _extract_button_value(val.get("primary_cta"))
            if primary:
                buttons.append(_make_list_item(primary))
            secondary = _extract_button_value(val.get("secondary_cta"))
            if secondary:
                buttons.append(_make_list_item(secondary))
            new_val = {k: v for k, v in val.items() if k not in ("primary_cta", "secondary_cta")}
            new_val["buttons"] = buttons
            new_blocks.append({**block, "value": new_val})
            any_changed = True
        if not any_changed:
            continue
        page.body = new_blocks
        page.save(update_fields=["body"])


def cta_banner_to_buttons_list_backwards(apps, schema_editor):
    TestPage = apps.get_model("testapp", "TestPage")
    for page in TestPage.objects.all().iterator():
        stream = page.body
        if stream is None:
            continue
        raw = getattr(stream, "raw_data", None)
        if raw is None:
            continue
        new_blocks = []
        any_changed = False
        for block in raw:
            if not isinstance(block, dict) or block.get("type") != "cta_banner":
                new_blocks.append(block)
                continue
            val = block.get("value")
            if not isinstance(val, dict) or "buttons" not in val:
                new_blocks.append(block)
                continue
            buttons = val["buttons"]
            new_val = {k: v for k, v in val.items() if k != "buttons"}
            primary = _extract_button_value(buttons[0]) if len(buttons) > 0 else None
            secondary = _extract_button_value(buttons[1]) if len(buttons) > 1 else None
            if primary:
                new_val["primary_cta"] = primary
            if secondary:
                new_val["secondary_cta"] = secondary
            new_blocks.append({**block, "value": new_val})
            any_changed = True
        if not any_changed:
            continue
        page.body = new_blocks
        page.save(update_fields=["body"])


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0013_merge_button_block"),
    ]

    operations = [
        migrations.RunPython(
            cta_banner_to_buttons_list_forwards,
            cta_banner_to_buttons_list_backwards,
        ),
    ]
