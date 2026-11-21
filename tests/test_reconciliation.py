import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from recipes.register import register
from records.intake import reconcile_trial
from records.reconcile_ledger import get_reconciliation_row
from records.traceback import get_reconciliation
from reports.workbench import (
    CENTER,
    SOURCE,
    initialize_workspace,
    load_reconciliation_sample,
    open_database,
)
from tests import edge, scenario, stores


RECONCILIATION_SAMPLE = (
    Path(__file__).resolve().parents[1] / 'samples' / 'reconciliation.json'
)


def load_cases():
    return json.loads(RECONCILIATION_SAMPLE.read_text(encoding='utf-8'))


class ReconciliationTests(unittest.TestCase):
    def test_sample_cases_restore_and_confirm(self):
        cases = load_cases()
        with stores() as (source, _):
            results = []
            for case in cases:
                revision_id = register(source, **case['spec'])
                result = reconcile_trial(
                    source,
                    case['trial_key'],
                    revision_id,
                    case['controller'],
                    case['crew'],
                )
                length = None if result['actions'] is None else len(result['actions'])
                self.assertEqual(length, case['expected']['shortest_length'])
                self.assertEqual(result['confirmed'], case['expected']['confirmed'])
                results.append(result)
            repeated, shared, tied, split, empty = results
            self.assertEqual(repeated['actions'], ['检', '检'])
            self.assertEqual(repeated['positions']['crew'], [1, 2])
            self.assertIn(repeated['positions']['controller'], ([1], [2]))
            self.assertEqual(repeated['confirmed'], [])
            self.assertEqual(shared['positions'], {'controller': [1], 'crew': [1]})
            self.assertEqual(shared['confirmed'], [[1, 1]])
            self.assertEqual(tied['confirmed'], [])
            self.assertIsNone(split['actions'])
            self.assertIsNone(split['positions'])
            self.assertEqual(split['confirmed'], [])
            self.assertEqual(empty['actions'], [])
            self.assertEqual(empty['positions'], {'controller': [], 'crew': []})
            scenario(
                'v9.reconcile',
                {'cases': [case['case'] for case in cases]},
                [case['expected'] for case in cases],
                [
                    {
                        'shortest_length': (
                            None if item['actions'] is None else len(item['actions'])
                        ),
                        'confirmed': item['confirmed'],
                    }
                    for item in results
                ],
                cases[0]['expected'],
                {'length': len(repeated['actions']), 'confirmed': repeated['confirmed']},
                ['records/reconcile.py', 'records/intake.py', 'records/reconcile_ledger.py'],
                'Two 检 records share no confirmed beat because the single controller entry may land on either position.',
            )

    def test_aligned_positions_are_legal_embeddings(self):
        with stores() as (source, _):
            cases = load_cases()
            for case in cases:
                revision_id = register(source, **case['spec'])
                result = reconcile_trial(
                    source,
                    case['trial_key'],
                    revision_id,
                    case['controller'],
                    case['crew'],
                )
                if result['actions'] is None:
                    continue
                word = result['actions']
                for name, record in (
                    ('controller', case['controller']['actions']),
                    ('crew', case['crew']['actions']),
                ):
                    positions = result['positions'][name]
                    self.assertEqual(len(positions), len(record))
                    self.assertEqual(positions, sorted(set(positions)))
                    self.assertTrue(all(1 <= position <= len(word) for position in positions))
                    self.assertEqual(
                        [word[position - 1] for position in positions], list(record)
                    )

    def test_omitted_actions_can_be_reconstructed(self):
        with stores() as (source, _):
            revision_id = register(
                source,
                '补检流程',
                ['检', '补'],
                ['s', 'm', 'f'],
                's',
                ['f'],
                [
                    edge('s', 'm', '检'),
                    edge('m', 'f', '补'),
                ],
            )
            result = reconcile_trial(
                source,
                'TX-301',
                revision_id,
                {'origin': '控制器片段-301', 'actions': ['补']},
                {'origin': '班组原页-301', 'actions': []},
            )
            self.assertEqual(result['actions'], ['检', '补'])
            self.assertEqual(result['positions'], {'controller': [2], 'crew': []})
            self.assertEqual(result['confirmed'], [])

    def test_coupled_ambiguous_alignment_still_confirms(self):
        # The only shortest completion is A A. Both sources must consume both
        # actions together, so even though no single item has a forced layer,
        # the two joint pairs are confirmed in every legal alignment.
        with stores() as (source, _):
            revision_id = register(
                source,
                '两次动作',
                ['A'],
                ['s', 'm', 'f'],
                's',
                ['f'],
                [edge('s', 'm', 'A'), edge('m', 'f', 'A')],
            )
            result = reconcile_trial(
                source,
                'TX-302',
                revision_id,
                {'origin': '控制器片段-302', 'actions': ['A', 'A']},
                {'origin': '班组原页-302', 'actions': ['A', 'A']},
            )
            self.assertEqual(result['actions'], ['A', 'A'])
            self.assertEqual(result['confirmed'], [[1, 1], [2, 2]])

    def test_decoupled_ambiguous_alignment_does_not_confirm(self):
        # Word A A; controller has one A, crew has two. The controller entry can
        # align with either crew entry, so no pair is confirmed.
        with stores() as (source, _):
            revision_id = register(
                source, '两次动作', ['A'], ['s', 'm', 'f'], 's', ['f'],
                [edge('s', 'm', 'A'), edge('m', 'f', 'A')],
            )
            result = reconcile_trial(
                source,
                'TX-303',
                revision_id,
                {'origin': '控制器片段-303', 'actions': ['A']},
                {'origin': '班组原页-303', 'actions': ['A', 'A']},
            )
            self.assertEqual(len(result['actions']), 2)
            self.assertEqual(result['confirmed'], [])

    def test_partner_switch_across_shortest_completions_not_confirmed(self):
        # Three distinct shortest words. In two of them controller item 2 shares
        # a beat with crew item 2, but in the third it pairs with crew item 1.
        # No double-source pair survives the intersection of all alignments.
        with stores() as (source, _):
            revision_id = register(
                source,
                '循环分道',
                ['A', 'B'],
                ['s0', 's1'],
                's0',
                ['s1'],
                [
                    edge('s0', 's1', 'B'),
                    edge('s1', 's0', 'A'),
                    edge('s0', 's1', None),
                ],
            )
            result = reconcile_trial(
                source,
                'TX-306',
                revision_id,
                {'origin': '控制器片段-306', 'actions': ['A', 'B', 'B']},
                {'origin': '班组原页-306', 'actions': ['B', 'B', 'A', 'A']},
            )
            self.assertEqual(len(result['actions']), 6)
            self.assertEqual(result['confirmed'], [])

    def test_repeated_item_alignments_keep_only_universal_pair(self):
        # The single shortest word A A A has three controller embeddings. Each
        # joint alignment yields different equal-position pairs, so their
        # intersection is empty even though every alignment shares two beats.
        with stores() as (source, _):
            revision_id = register(
                source,
                '三拍循环',
                ['A'],
                ['s0', 's1'],
                's0',
                ['s1'],
                [edge('s1', 's1', 'A'), edge('s0', 's1', 'A')],
            )
            result = reconcile_trial(
                source,
                'TX-307',
                revision_id,
                {'origin': '控制器片段-307', 'actions': ['A', 'A']},
                {'origin': '班组原页-307', 'actions': ['A', 'A', 'A']},
            )
            self.assertEqual(result['actions'], ['A', 'A', 'A'])
            self.assertEqual(result['confirmed'], [])

    def test_hidden_cycles_do_not_occupy_positions(self):
        with stores() as (source, _):
            revision_id = register(
                source,
                '免动作完结',
                [],
                ['s', 'h', 'f'],
                's',
                ['f'],
                [
                    edge('s', 'h', None),
                    edge('h', 's', None),
                    edge('h', 'f', None),
                ],
            )
            result = reconcile_trial(
                source,
                'TX-304',
                revision_id,
                {'origin': '控制器片段-304', 'actions': []},
                {'origin': '班组原页-304', 'actions': []},
            )
            self.assertEqual(result['actions'], [])
            self.assertEqual(result['positions'], {'controller': [], 'crew': []})

    def test_no_common_completion_still_keeps_both_sources(self):
        with stores() as (source, _):
            revision_id = register(
                source,
                '分道复验',
                ['复', '补', '检'],
                ['s', 'r', 'p', 'd', 'f'],
                's',
                ['f'],
                [
                    edge('s', 'r', '复'),
                    edge('r', 'f', '检'),
                    edge('s', 'p', '补'),
                    edge('p', 'f', '检'),
                    edge('s', 'd', None),
                    edge('d', 'd', '复'),
                    edge('d', 'd', '补'),
                    edge('d', 'd', '检'),
                ],
            )
            before = source.execute(
                'SELECT count(*) FROM trial_reconciliations'
            ).fetchone()[0]
            result = reconcile_trial(
                source,
                'TX-305',
                revision_id,
                {'origin': '控制器片段-305', 'actions': ['复']},
                {'origin': '班组原页-305', 'actions': ['补', '检']},
            )
            self.assertIsNone(result['actions'])
            self.assertIsNone(result['positions'])
            self.assertEqual(result['confirmed'], [])
            self.assertEqual(result['controller']['actions'], ['复'])
            self.assertEqual(result['crew']['actions'], ['补', '检'])
            self.assertEqual(
                source.execute('SELECT count(*) FROM trial_reconciliations').fetchone()[0],
                before + 1,
            )

    def test_invalid_inputs_raise_value_error_and_write_nothing(self):
        with stores() as (source, _):
            revision_id = register(source, **load_cases()[0]['spec'])
            good = {'origin': '控制器片段-X', 'actions': ['检']}
            bad_sources = [
                {'origin': '  ', 'actions': ['检']},
                {'actions': ['检']},
                {'origin': '控制器片段-X', 'actions': '检'},
                {'origin': '控制器片段-X', 'actions': ['外']},
                {'origin': '控制器片段-X', 'actions': (None,)},
                {'origin': '控制器片段-X', 'actions': ['检'], 'extra': 1},
                'not-a-dict',
            ]
            for bad in bad_sources:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    reconcile_trial(source, 'TX-400', revision_id, bad,
                                    {'origin': '班组原页-X', 'actions': []})
            for key in ('', '   '):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    reconcile_trial(source, key, revision_id, good,
                                    {'origin': '班组原页-X', 'actions': []})
            self.assertEqual(
                source.execute('SELECT count(*) FROM trial_reconciliations').fetchone()[0], 0
            )

    def test_unknown_revision_and_reconciliation_numbers(self):
        with stores() as (source, _):
            with self.assertRaises(LookupError):
                reconcile_trial(
                    source,
                    'TX-401',
                    999,
                    {'origin': '控制器片段-X', 'actions': []},
                    {'origin': '班组原页-X', 'actions': []},
                )
            for number in (0, -1, True, 1.5, '1'):
                with self.subTest(number=number), self.assertRaises(ValueError):
                    get_reconciliation(source, number)
            with self.assertRaises(LookupError):
                get_reconciliation(source, 404)

    def test_persistence_reopen_and_numbered_retrieval(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_workspace(root)
            case = load_cases()[1]
            with open_database(root / SOURCE) as source:
                revision_id = register(source, **case['spec'])
                signed = reconcile_trial(
                    source,
                    case['trial_key'],
                    revision_id,
                    case['controller'],
                    case['crew'],
                )
                reconciliation_id = signed['reconciliation_id']
                self.assertEqual(reconciliation_id, 1)
                self.assertEqual(signed['trial_key'], case['trial_key'])
                self.assertEqual(signed['revision_id'], revision_id)
                self.assertEqual(signed['controller'], case['controller'])
                self.assertEqual(signed['crew'], case['crew'])
                self.assertIsInstance(signed['controller']['actions'], list)
            with open_database(root / SOURCE) as source:
                retrieved = get_reconciliation(source, reconciliation_id)
                self.assertEqual(retrieved, signed)
            # Re-initializing an existing workspace keeps signed reconciliations.
            initialize_workspace(root)
            with open_database(root / SOURCE) as source:
                again = get_reconciliation(source, reconciliation_id)
                self.assertEqual(again, signed)
                next_case = load_cases()[2]
                next_revision = register(source, **next_case['spec'])
                next_result = reconcile_trial(
                    source,
                    next_case['trial_key'],
                    next_revision,
                    next_case['controller'],
                    next_case['crew'],
                )
                self.assertEqual(next_result['reconciliation_id'], reconciliation_id + 1)

    def test_failed_commit_adds_nothing_and_can_retry(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_workspace(root)
            case = load_cases()[1]
            with open_database(root / SOURCE) as source:
                revision_id = register(source, **case['spec'])
                source.execute(
                    'CREATE TABLE test_permitted_reconciliations '
                    '(reconciliation_id INTEGER PRIMARY KEY)'
                )
                source.execute('''CREATE TABLE test_reconciliation_gate (
                    reconciliation_id INTEGER REFERENCES test_permitted_reconciliations(reconciliation_id)
                        DEFERRABLE INITIALLY DEFERRED
                )''')
                source.execute('''CREATE TRIGGER test_block_reconciliation
                    AFTER INSERT ON trial_reconciliations BEGIN
                        INSERT INTO test_reconciliation_gate VALUES (NEW.reconciliation_id);
                    END''')
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
                    reconcile_trial(
                        source,
                        case['trial_key'],
                        revision_id,
                        case['controller'],
                        case['crew'],
                    )
                self.assertFalse(source.in_transaction)
                self.assertEqual(
                    source.execute('SELECT count(*) FROM trial_reconciliations').fetchone()[0], 0
                )
                self.assertEqual(
                    source.execute('SELECT count(*) FROM test_reconciliation_gate').fetchone()[0], 0
                )
                source.execute('DROP TRIGGER test_block_reconciliation')
                recovered = reconcile_trial(
                    source,
                    case['trial_key'],
                    revision_id,
                    case['controller'],
                    case['crew'],
                )
                self.assertEqual(recovered['reconciliation_id'], 1)
                self.assertEqual(get_reconciliation(source, 1), recovered)

    def test_tuple_actions_are_returned_as_lists_and_fidelity_kept(self):
        with stores() as (source, _):
            revision_id = register(source, **load_cases()[0]['spec'])
            result = reconcile_trial(
                source,
                'TX-402',
                revision_id,
                {'origin': '控制器片段-402', 'actions': ('检',)},
                {'origin': '班组原页-402', 'actions': ('检', '检')},
            )
            self.assertEqual(result['controller']['actions'], ['检'])
            self.assertEqual(result['crew']['actions'], ['检', '检'])
            row = get_reconciliation_row(source, result['reconciliation_id'])
            self.assertEqual(row[0], 'TX-402')
            self.assertEqual(row[2], '控制器片段-402')
            self.assertEqual(row[4], '班组原页-402')

    def test_old_revision_remains_reconcilable_after_correction(self):
        with stores() as (source, _):
            sample = load_cases()
            old_id = register(source, **sample[0]['spec'])
            new_id = register(source, **sample[1]['spec'])
            result = reconcile_trial(
                source,
                'TX-403',
                old_id,
                sample[0]['controller'],
                sample[0]['crew'],
            )
            self.assertEqual(result['revision_id'], old_id)
            self.assertNotEqual(old_id, new_id)
            self.assertEqual(len(result['actions']), 2)
