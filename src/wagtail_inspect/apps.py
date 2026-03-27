from django.apps import AppConfig


class WagtailInspectConfig(AppConfig):
    """Django app configuration for Wagtail Inspect."""

    name = "wagtail_inspect"
    label = "wagtail_inspect"
    verbose_name = "Wagtail Inspect"
    default_auto_field = "django.db.models.AutoField"

    def ready(self) -> None:
        from . import patches

        patches.apply_patches()
