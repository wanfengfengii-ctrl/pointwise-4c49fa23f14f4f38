import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from compare.admission import receive
from compare.pairing import compare_pair
from recipes.register import register
from reports.export import export_report
from reports.lookup import get_report
from reports.workbench import CENTER, SOURCE, initialize_workspace, load_sample, open_database
from tests import sample_issues, scenario, stores


def counts(db):
    return tuple(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                 for table in ('signed_reports', 'report_parents', 'report_receipts'))


class ReportingTests(unittest.TestCase):
    def test_missing_and_invalid_parent_do_not_publish(self):
        with stores() as (source, center):
            fixed, _ = sample_issues(source)
            left = receive(center, fixed.issue_id, fixed.wire)
            with self.assertRaises(LookupError):
                compare_pair(center, left, left + 1)
            with self.assertRaises(LookupError):
                compare_pair(center, left + 1, left)
            with self.assertRaises(ValueError):
                compare_pair(center, left, True)
            actual = counts(center)
            self.assertEqual(actual, (0, 0, 0))
            self.assertIsNone(get_report(center, 1))
            scenario('v7', {'left_received': left, 'missing_received': left + 1},
                     [0, 0, 0], actual, None, get_report(center, 1),
                     ['compare/inbox.py', 'compare/pairing.py', 'reports/publish.py', 'reports/lookup.py'],
                     'The physical inbox contains only the first item, so there can be no completed publication for the requested pair.')

    def test_commit_failure_rolls_back_and_history_retains_its_own_receipt(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_workspace(root)
            with open_database(root / SOURCE) as source:
                old, new = sample_issues(source)
            with open_database(root / CENTER) as center:
                left = receive(center, old.issue_id, old.wire)
                right = receive(center, new.issue_id, new.wire)
                first = compare_pair(center, left, right)
                center.execute('CREATE TABLE test_permitted_reports (report_id INTEGER PRIMARY KEY)')
                center.execute('''CREATE TABLE test_commit_gate (
                    report_id INTEGER REFERENCES test_permitted_reports(report_id)
                        DEFERRABLE INITIALLY DEFERRED
                )''')
                center.execute('''CREATE TRIGGER test_defer_report_failure
                    AFTER INSERT ON report_receipts BEGIN
                    INSERT INTO test_commit_gate VALUES (NEW.report_id);
                END''')
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
                    compare_pair(center, right, left)
                self.assertFalse(center.in_transaction)
            with open_database(root / CENTER) as center:
                after_failure = counts(center)
                self.assertEqual(after_failure, (1, 2, 1))
                self.assertEqual(center.execute('SELECT count(*) FROM test_commit_gate').fetchone()[0], 0)
                self.assertEqual(get_report(center, first.report_id), first)
                self.assertIsNone(get_report(center, first.report_id + 1))
                center.execute('DROP TRIGGER test_defer_report_failure')
                second = compare_pair(center, right, left)
                self.assertEqual(counts(center), (2, 4, 2))
                self.assertEqual(second.receipt.report_id, second.report_id)
                self.assertNotEqual(second.receipt.receipt_id, first.receipt.receipt_id)
                self.assertEqual((second.left_only, second.right_only), (('复', '检'), ('补', '检')))
                self.assertEqual(second.parents, tuple(reversed(first.parents)))
            with open_database(root / SOURCE) as source:
                corrected = register(source, **load_sample()['old'])
                self.assertGreater(corrected, new.revision_id)
            with open_database(root / CENTER) as center:
                recovered_first = get_report(center, first.report_id)
                recovered_second = get_report(center, second.report_id)
                self.assertEqual(recovered_first, first)
                self.assertEqual(recovered_second, second)
                self.assertEqual(export_report(recovered_first), export_report(first))
                self.assertIsNone(get_report(center, second.report_id + 1))
                self.assertEqual((first.left_only, first.right_only), (('补', '检'), ('复', '检')))
                receipt_ids = [recovered_first.receipt.report_id, recovered_second.receipt.report_id]
                self.assertEqual(receipt_ids, [first.report_id, second.report_id])
                scenario('v8', {'failed_pair': [right, left], 'existing_report': first.report_id},
                         [1, 2, 1], after_failure, [first.report_id, second.report_id], receipt_ids,
                         ['compare/pairing.py', 'reports/publish.py', 'reports/receipt.py', 'reports/lookup.py'],
                         'A deferred foreign key fails the commit after the receipt insert. The previous report contributes exactly one report, two parent rows and one receipt.')
