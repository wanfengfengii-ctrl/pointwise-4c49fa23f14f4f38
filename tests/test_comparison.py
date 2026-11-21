import json
import unittest

from compare.admission import receive
from compare.pairing import compare_pair
from issue.freeze import freeze
from recipes.register import register
from reports.export import export_report
from reports.lookup import get_report
from tests import edge, sample_issues, scenario, stores


def freeze_graph(source, name, codes, steps, start, finals, edges):
    return freeze(source, register(source, name, codes, steps, start, finals, edges))


def offline_pair(source, center, left, right):
    source.close()
    return receive(center, left.issue_id, left.wire), receive(center, right.issue_id, right.wire)


class ComparisonTests(unittest.TestCase):
    def test_offline_revision_change(self):
        with stores() as (source, center):
            old, new = sample_issues(source)
            left, right = offline_pair(source, center, old, new)
            signed = compare_pair(center, left, right)
            expected = (('补', '检'), ('复', '检'))
            actual = (signed.left_only, signed.right_only)
            self.assertEqual(actual, expected, 'TRACE_DIFF_MISMATCH')
            parent_ids = [(p.received_id, p.issue_id, p.revision_id, p.digest) for p in signed.parents]
            expected_ids = [(left, old.issue_id, old.revision_id, old.digest),
                            (right, new.issue_id, new.revision_id, new.digest)]
            self.assertEqual(parent_ids, expected_ids)
            self.assertEqual(get_report(center, signed.report_id), signed)
            scenario('v5', {'left_issue': old.issue_id, 'right_issue': new.issue_id,
                            'shared_shortest_record': ['检']}, expected, actual,
                     expected_ids, parent_ids,
                     ['issue/disclosure.py', 'compare/pairing.py', 'compare/distinction.py', 'reports/publish.py'],
                     'Only 检 is supported at length one by either graph. At length two the supplemental and repeated inspection paths give one exclusive record each.')

    def test_order_reverses_witnesses_and_parents(self):
        with stores() as (source, center):
            old, new = sample_issues(source)
            left, right = offline_pair(source, center, old, new)
            forward = compare_pair(center, left, right)
            reverse = compare_pair(center, right, left)
            self.assertEqual((reverse.left_only, reverse.right_only), (('复', '检'), ('补', '检')))
            self.assertEqual(reverse.parents, tuple(reversed(forward.parents)))
            self.assertNotEqual(reverse.receipt.receipt_id, forward.receipt.receipt_id)
            same = compare_pair(center, left, left)
            self.assertEqual((same.left_only, same.right_only), (None, None))
            self.assertEqual([p.received_id for p in same.parents], [left, left])

    def test_tied_shortest_uses_action_code_order(self):
        with stores() as (source, center):
            left = freeze_graph(source, '合格', ['补', '检'], ['s', 'f'], 's', ['f'],
                                [edge('s', 'f', '补'), edge('s', 'f', '检')])
            right = freeze_graph(source, '停用', [], ['s'], 's', [], [])
            report = compare_pair(center, *offline_pair(source, center, left, right))
            self.assertEqual((report.left_only, report.right_only), (('检',), None))

    def test_equivalent_loops_have_no_witness(self):
        with stores() as (source, center):
            left = freeze_graph(source, '直达复测', ['复', '检'], ['s', 'f'], 's', ['f'],
                                [edge('s', 's', '复'), edge('s', 'f', '检')])
            right = freeze_graph(source, '隐藏循环复测', ['检', '复', '补'],
                                 ['a', 'b', 'c', 'dead', 'f', 'done'], 'a', ['done'], [
                                     edge('a', 'b', None), edge('b', 'a', None),
                                     edge('b', 'c', '复'), edge('b', 'dead', '复'),
                                     edge('c', 'a', None), edge('b', 'f', '检'),
                                     edge('f', 'done', None), edge('dead', 'dead', '补'),
                                 ])
            report = compare_pair(center, *offline_pair(source, center, left, right))
            actual = (report.left_only, report.right_only)
            self.assertEqual(actual, (None, None))
            persisted = json.loads(export_report(get_report(center, report.report_id)))
            downstream = [persisted['left_only'], persisted['right_only']]
            self.assertEqual(downstream, [None, None])
            scenario('v6', {'left': 'direct loop', 'right': 'hidden loop plus dead branch'},
                     [None, None], actual, [None, None], downstream,
                     ['issue/disclosure.py', 'compare/distinction.py', 'reports/lookup.py', 'reports/export.py'],
                     'Each graph accepts exactly zero or more 复 followed by 检. The extra branch cannot reach an accepting state.')

    def test_late_difference_after_one_side_revisits(self):
        with stores() as (source, center):
            left = freeze_graph(source, '单次复测', ['复', '检'], ['s', 'r', 'f'], 's', ['f'],
                                [edge('s', 'r', '复'), edge('s', 'f', '检'), edge('r', 'f', '检')])
            right = freeze_graph(source, '多次复测', ['复', '检'], ['s', 'f'], 's', ['f'],
                                 [edge('s', 's', '复'), edge('s', 'f', '检')])
            report = compare_pair(center, *offline_pair(source, center, left, right))
            self.assertEqual((report.left_only, report.right_only), (None, ('复', '复', '检')))

    def test_hidden_empty_witness_survives_storage_and_export(self):
        with stores() as (source, center):
            left = freeze_graph(source, '空班单可完结', [], ['s', 'h', 'f'], 's', ['f'],
                                [edge('s', 'h', None), edge('h', 's', None), edge('h', 'f', None)])
            right = freeze_graph(source, '空班单不能完结', [], ['s'], 's', [], [])
            report = compare_pair(center, *offline_pair(source, center, left, right))
            self.assertEqual((report.left_only, report.right_only), ((), None))
            delivered = get_report(center, report.report_id)
            self.assertEqual(delivered, report)
            data = json.loads(export_report(delivered))
            self.assertEqual((data['left_only'], data['right_only']), ([], None))
