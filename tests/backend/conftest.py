import pytest
from wagtail.models import Locale, Page

# pytest-django reads DJANGO_SETTINGS_MODULE from pyproject.toml [tool.pytest.ini_options]


@pytest.fixture
def root_page(db):
    """A Wagtail root page, required as the parent for any TestPage instances."""
    Locale.objects.get_or_create(language_code="en")
    return Page.add_root(title="Root", slug="root")
