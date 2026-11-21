import unittest

from recipes.register import register
from recipes.repository import get_current_revision
from records.intake import check_record
from records.traceback import get_trace
from reports.workbench import load_sample
from tests import edge, scenario, stores


class RecordTests(unittest.TestCase):
    def test_complete_support_original_order_and_origin(self):
        with stores() as (source, _):
            sample = load_sample()
            old_id = register(source, **sample['old'])
            trials = [check_record(source, old_id, **trial) for trial in sample['trials']]
            expected = [True, True, False]
            actual = [trial.supported for trial in trials]
            self.assertEqual(actual, expected)
            saved = [get_trace(source, trial.trace_id) for trial in trials]
            self.assertEqual(saved, trials)
            supplemental = saved[1]
            self.assertEqual(supplemental.actions, ('补', '检'))
            self.assertEqual(supplemental.crew, '日班乙组')
            self.assertEqual(supplemental.revision_id, old_id)
            replay = check_record(source, supplemental.revision_id, supplemental.actions, supplemental.crew)
            self.assertTrue(replay.supported)
            scenario('v1', {'revision': old_id, 'trials': sample['trials']}, expected, actual,
                     {'actions': ['补', '检'], 'crew': '日班乙组', 'replay': True},
                     {'actions': list(supplemental.actions), 'crew': supplemental.crew,
                      'replay': replay.supported},
                     ['records/intake.py', 'records/conformance.py', 'records/ledger.py', 'records/traceback.py'],
                     'Follow the two accepting hidden branches by hand. The branch reading only 复 stops before a final state.')

    def test_explicit_old_revision_after_correction(self):
        with stores() as (source, _):
            sample = load_sample()
            old_id = register(source, **sample['old'])
            new_id = register(source, **sample['new'])
            self.assertEqual(get_current_revision(source, sample['old']['recipe']).revision_id, new_id)
            old_trial = check_record(source, old_id, ['补', '检'], '日班乙组')
            new_trial = check_record(source, new_id, ['补', '检'], '日班乙组')
            self.assertEqual((old_trial.revision_id, old_trial.supported), (old_id, True))
            self.assertEqual((new_trial.revision_id, new_trial.supported), (new_id, False))
            self.assertEqual(get_trace(source, old_trial.trace_id), old_trial)

    def test_invalid_trace_writes_nothing(self):
        with stores() as (source, _):
            revision = register(source, **load_sample()['old'])
            for actions, crew in [(['外'], '甲组'), ('检', '甲组'), (['检'], ' '), ([None], '甲组')]:
                with self.subTest(actions=actions, crew=crew), self.assertRaises(ValueError):
                    check_record(source, revision, actions, crew)
            with self.assertRaises(LookupError):
                check_record(source, revision + 1, ['检'], '甲组')
            self.assertEqual(source.execute('SELECT count(*) FROM trial_traces').fetchone()[0], 0)
            self.assertEqual(check_record(source, revision, ['检'], '甲组').trace_id, 1)

    def test_hidden_cycle_and_empty_source_trace(self):
        with stores() as (source, _):
            revision = register(source, '待压', [], ['s', 'h', 'f'], 's', ['f'],
                                [edge('s', 'h', None), edge('h', 's', None), edge('h', 'f', None)])
            trace = check_record(source, revision, [], '日班甲组')
            self.assertEqual(trace.actions, ())
            self.assertTrue(trace.supported)
            self.assertEqual(get_trace(source, trace.trace_id), trace)
