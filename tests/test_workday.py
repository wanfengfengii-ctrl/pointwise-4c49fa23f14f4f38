import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from reports.workbench import main
from tests import scenario


class WorkdayTests(unittest.TestCase):
    def test_terminal_demo_runs_full_workday_and_reopens_report(self):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(['demo'])
        self.assertEqual(exit_code, 0)
        day = json.loads(output.getvalue())
        trials = day['trials']
        self.assertEqual([trial['actions'] for trial in trials], [['检'], ['补', '检'], ['复']])
        self.assertEqual([trial['supported'] for trial in trials], [True, True, False])
        self.assertEqual([trial['crew'] for trial in trials], ['日班甲组', '日班乙组', '日班丙组'])
        self.assertEqual([trial['revision_id'] for trial in trials], [day['revisions'][0]] * 3)
        self.assertNotEqual(*day['revisions'])
        signed, delivered = day['signed'], day['delivered']
        expected = [['补', '检'], ['复', '检']]
        actual = [signed['left_only'], signed['right_only']]
        self.assertEqual(actual, expected)
        self.assertEqual([p['revision_id'] for p in signed['parents']], day['revisions'])
        self.assertEqual(signed['receipt']['report_id'], signed['report_id'])
        self.assertEqual(delivered, signed)
        after_reopen = [delivered['left_only'], delivered['right_only']]
        self.assertEqual(after_reopen, expected)
        scenario('v8.workday', {'traces': [trial['actions'] for trial in trials],
                               'revision_pair': day['revisions']}, expected, actual, expected, after_reopen,
                 ['reports/workbench.py', 'records/intake.py', 'issue/freeze.py', 'compare/distinction.py',
                  'reports/publish.py', 'reports/lookup.py'],
                 'Enumerate the two-process sample through two actions. The direct inspection is shared, and the two exclusive paths are finished and minimal.')
