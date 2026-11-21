import unittest
from copy import deepcopy

from recipes.register import register
from recipes.repository import get_current_revision, get_revision
from records.intake import check_record
from reports.workbench import load_sample
from tests import edge, scenario, stores


class RecipeTests(unittest.TestCase):
    def test_invalid_correction_preserves_current(self):
        with stores() as (source, _):
            sample = load_sample()
            old_id = register(source, **sample['old'])
            before = get_revision(source, old_id)
            correction = deepcopy(sample['new'])
            dangling = edge('NEW-START', 'missing-step', '补')
            correction['edges'].append(dangling)
            accepted = True
            try:
                register(source, **correction)
            except ValueError:
                accepted = False
            self.assertFalse(accepted)
            self.assertEqual(get_current_revision(source, before.recipe), before)
            self.assertEqual(get_revision(source, old_id), before)
            count = source.execute('SELECT count(*) FROM recipe_revisions').fetchone()[0]
            self.assertEqual(count, 1)
            replay = check_record(source, old_id, ['补', '检'], '日班乙组')
            self.assertTrue(replay.supported)
            scenario('v2', {'edge': dangling, 'current': old_id}, False, accepted,
                     {'revisions': 1, 'replay_supported': True},
                     {'revisions': count, 'replay_supported': replay.supported},
                     ['recipes/topology.py', 'recipes/register.py', 'recipes/repository.py', 'records/intake.py'],
                     'The target is absent from the steps. The old supplemental inspection reaches its final step.')

    def test_invalid_action_catalog_and_endpoints(self):
        with stores() as (source, _):
            old = load_sample()['old']
            variants = [
                {'codes': ['检', '检']},
                {'codes': ['检', ' ']},
                {'start': 'missing'},
                {'accepting': ['missing']},
                {'edges': [edge(old['start'], old['accepting'][0], '外')]},
            ]
            for change in variants:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    register(source, **{**old, **change})
            self.assertEqual(source.execute('SELECT count(*) FROM recipe_revisions').fetchone()[0], 0)
            self.assertEqual(source.execute('SELECT count(*) FROM current_revisions').fetchone()[0], 0)
            self.assertEqual(register(source, **old), 1)
