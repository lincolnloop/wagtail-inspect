import pytest
from django.apps import apps


@pytest.mark.django_db
def test_app_is_installed():
    assert apps.is_installed("wagtail_inspect")


def test_app_label():
    config = apps.get_app_config("wagtail_inspect")
    assert config.label == "wagtail_inspect"
    assert config.verbose_name == "Wagtail Inspect"
