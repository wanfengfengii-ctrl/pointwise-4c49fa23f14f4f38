import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from compare.admission import receive
from compare.inbox import get_received
from compare.pairing import compare_pair
from issue.archive import get_issue
from issue.freeze import freeze
from recipes.register import register
from recipes.repository import get_current_revision, get_revision
from records.intake import check_record
from records.traceback import get_trace
from reports.lookup import get_report
from reports.workbench import CENTER, SOURCE, initialize_workspace, load_sample, open_database
from tests import sample_issues


class InitializationTests(unittest.TestCase):
    def test_repeated_initialization_preserves_user_data(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_workspace(root)
            initialize_workspace(root)
            sample = load_sample()
            with open_database(root / SOURCE) as source:
                with self.assertRaises(LookupError):
                    get_current_revision(source, sample['old']['recipe'])
                old, new = sample_issues(source)
                extra_revision = register(source, **{**sample['new'], 'accepting': ['NEW-START', 'NEW-DONE']})
                extra = freeze(source, extra_revision)
                trace = check_record(source, extra_revision, [], '夜班人工补录')
                self.assertTrue(trace.supported)
                snapshot = get_revision(source, extra_revision)
            with open_database(root / CENTER) as center:
                self.assertIsNone(get_report(center, 1))
                first = receive(center, old.issue_id, old.wire)
                second = receive(center, new.issue_id, new.wire)
                third = receive(center, extra.issue_id, extra.wire)
                original = compare_pair(center, first, second)
                amended = compare_pair(center, second, third)
                self.assertEqual((amended.left_only, amended.right_only), (None, ()))
            initialize_workspace(root)
            initialize_workspace(root)
            with open_database(root / SOURCE) as source:
                self.assertEqual(get_current_revision(source, snapshot.recipe), snapshot)
                self.assertEqual(get_trace(source, trace.trace_id), trace)
                self.assertEqual(get_issue(source, old.issue_id).wire, old.wire)
                self.assertEqual(get_issue(source, extra.issue_id).wire, extra.wire)
                next_revision = register(source, **sample['old'])
                self.assertEqual(next_revision, extra_revision + 1)
            with open_database(root / CENTER) as center:
                self.assertEqual(get_received(center, third).fixed.wire, extra.wire)
                self.assertEqual(receive(center, old.issue_id, old.wire), first)
                self.assertEqual(get_report(center, original.report_id), original)
                self.assertEqual(get_report(center, amended.report_id), amended)
                next_report = compare_pair(center, third, second)
                self.assertEqual(next_report.report_id, amended.report_id + 1)
                self.assertEqual((next_report.left_only, next_report.right_only), ((), None))
