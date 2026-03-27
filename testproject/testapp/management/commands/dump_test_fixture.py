"""Dump the local development database to a JSON fixture for E2E tests.

Run from the repo root via ``just dump-fixture`` (or ``manage.py`` from
``testproject/``). Output defaults to ``tests/e2e/fixtures/test_data.json``.

The intended shape of the data is small: one staff/superuser, ``Site`` + root
``Page``, and usually one child page with rich ``StreamField`` content. Before
dumping, trim the dev database (or start from migrate + a single content page)
so the JSON stays small. Most E2E tests do not need this file at all — they
use ``make_test_page`` in ``tests/e2e/conftest.py`` instead.
"""

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


def _repo_root() -> Path:
    # testproject/testapp/management/commands/dump_test_fixture.py -> repo root
    return Path(__file__).resolve().parents[4]


class Command(BaseCommand):
    help = "Dump Wagtail-related data to tests/e2e/fixtures/test_data.json for Playwright / pytest E2E tests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Output path (default: <repo>/tests/e2e/fixtures/test_data.json)",
        )

    def handle(self, *args, **options):
        repo = _repo_root()
        out = Path(options["output"]) if options["output"] else None
        output_path = (
            out if out and out.is_absolute() else (repo / (out or Path("tests/e2e/fixtures/test_data.json")))
        ).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ``natural_foreign`` keeps FKs stable (e.g. users by username).
        # Avoid ``natural_primary`` for the whole dump: treebeard ``Collection``
        # (and similar) rows deserialize incorrectly without explicit primary keys.
        # Exclude noisy / environment-specific tables.
        # Dump ``auth.user`` only — not the full ``auth`` app (avoids thousands of
        # ``auth.permission`` rows and duplicate key errors on ``loaddata`` after
        # migrations have already created permissions).
        # Include ``testapp`` so concrete page types (e.g. ``TestPage``) are dumped;
        # without it, only ``wagtailcore.Page`` rows load and ``page.specific`` raises
        # ``TestPage.DoesNotExist`` for those pks.
        call_command(
            "dumpdata",
            "auth.user",
            "wagtailcore",
            "testapp",
            "wagtailimages",
            "wagtaildocs",
            "taggit",
            exclude=[
                "sessions",
                # testapp does not install django.contrib.admin — skip admin excludes.
                "wagtailcore.ModelLogEntry",
                # Audit rows can outlive deleted pages; dangling FKs break dumpdata.
                "wagtailcore.PageLogEntry",
                # Derived search of object references; omit and run
                # ``manage.py rebuild_references_index`` after loaddata if needed.
                "wagtailcore.ReferenceIndex",
                # Chunked-upload temp files (admin only; not needed to restore content).
                "wagtailcore.UploadedFile",
                # Editor notification subscriptions.
                "wagtailcore.PageSubscription",
                # Moderation threads (omit unless E2E tests cover comments).
                "wagtailcore.Comment",
                "wagtailcore.CommentReply",
                # Moderation workflow state (pages + revisions stay valid without it).
                "wagtailcore.TaskState",
                "wagtailcore.WorkflowState",
                "wagtailcore.WorkflowPage",
                "wagtailcore.WorkflowTask",
                "wagtailcore.WorkflowContentType",
                "wagtailcore.GroupApprovalTask",
                "wagtailcore.Task",
                "wagtailcore.Workflow",
                "wagtailcore.GroupCollectionPermission",
                # Superuser E2E does not need group → page/site permission rows.
                "wagtailcore.GroupPagePermission",
                "wagtailcore.GroupSitePermission",
                "wagtailcore.CollectionViewRestriction",
                "wagtailcore.PageViewRestriction",
                # Thumbnails/resizes; rebuilt when images are first served.
                "wagtailimages.Rendition",
            ],
            natural_foreign=True,
            natural_primary=False,
            indent=2,
            output=str(output_path),
        )

        self.stdout.write(self.style.SUCCESS(f"Wrote fixture to {output_path}"))
