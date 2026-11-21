import hashlib
import json
import unittest
from dataclasses import replace

from compare.admission import receive
from compare.inbox import get_received
from issue.archive import get_issue
from issue.evidence import seal_evidence
from issue.freeze import freeze
from recipes.register import register
from records.intake import check_record
from reports.workbench import load_sample
from tests import edge, scenario, stores


def accepts_public(evidence, actions):
    states = {evidence.start}
    for action in actions:
        states = {target for start, code, target in evidence.transitions
                  if start in states and code == action}
    return bool(states.intersection(evidence.accepting))


def wire_for(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')


class HandoffTests(unittest.TestCase):
    def test_frozen_identity_language_and_disclosure(self):
        with stores() as (source, center):
            sample = load_sample()
            old_id = register(source, **sample['old'])
            old = freeze(source, old_id)
            check_record(source, old_id, ['补', '检'], '班组-PRIVATE-17')
            new_id = register(source, **sample['new'])
            new = freeze(source, new_id)
            self.assertNotEqual(old_id, new_id)
            self.assertNotEqual(old.issue_id, new.issue_id)
            self.assertEqual(get_issue(source, old.issue_id).wire, old.wire)
            self.assertEqual(get_issue(source, new.issue_id).wire, new.wire)
            received_new = receive(center, new.issue_id, new.wire)
            received_old = receive(center, old.issue_id, old.wire)
            source.close()
            next_old = get_received(center, received_old).fixed
            next_new = get_received(center, received_new).fixed
            self.assertEqual((next_old.revision_id, next_new.revision_id), (old_id, new_id))
            self.assertEqual((next_old.wire, next_new.wire), (old.wire, new.wire))
            text = json.dumps(json.loads(next_old.wire), ensure_ascii=False)
            self.assertNotIn('INTERNAL-', text)
            self.assertNotIn('台架私有备注', text)
            self.assertNotIn('班组-PRIVATE-17', text)
            actions = [['检'], ['补', '检'], ['复', '检'], [], ['复', '复', '检']]
            expected = [[True, True, False, False, False], [True, False, True, False, True]]
            actual = [[accepts_public(item.evidence, trace) for trace in actions]
                      for item in (next_old, next_new)]
            self.assertEqual(actual, expected)
            scenario('v3', {'old_revision': old_id, 'new_revision': new_id, 'traces': actions},
                     expected, actual, [old_id, new_id], [next_old.revision_id, next_new.revision_id],
                     ['issue/disclosure.py', 'issue/archive.py', 'issue/evidence.py', 'compare/admission.py', 'compare/inbox.py'],
                     'Trace the two original graphs by hand, then replay the fixed public relations independently of comparison.')

    def test_hidden_empty_and_multiple_same_code_targets(self):
        with stores() as (source, center):
            revision = register(source, '分支', ['检', '补'], ['s', 'a', 'b', 'h', 'f'], 's', ['f'], [
                edge('s', 'h', None), edge('h', 's', None), edge('h', 'f', None),
                edge('s', 'a', '检'), edge('s', 'b', '检'),
                edge('a', 'f', '检'), edge('b', 'f', '补'),
            ])
            fixed = freeze(source, revision)
            item = get_received(center, receive(center, fixed.issue_id, fixed.wire)).fixed.evidence
            for trace in [(), ('检', '检'), ('检', '补')]:
                self.assertTrue(accepts_public(item, trace), trace)
            self.assertFalse(accepts_public(item, ('检',)))

    def test_missing_revision_does_not_issue(self):
        with stores() as (source, _):
            with self.assertRaises(LookupError):
                freeze(source, 1)
            self.assertEqual(source.execute('SELECT count(*) FROM issued_evidence').fetchone()[0], 0)

    def test_replay_and_conflict_preserve_first_received_bytes(self):
        with stores() as (source, center):
            old = freeze(source, register(source, **load_sample()['old']))
            first = receive(center, old.issue_id, old.wire)
            self.assertEqual(receive(center, old.issue_id, bytes(bytearray(old.wire))), first)
            changed = replace(old.evidence, accepting=(old.evidence.start,))
            conflict = seal_evidence(old.issue_id, old.revision_id, changed)
            with self.assertRaisesRegex(ValueError, 'conflicting evidence'):
                receive(center, conflict.issue_id, conflict.wire)
            self.assertEqual(get_received(center, first).fixed.wire, old.wire)
            self.assertEqual(center.execute('SELECT count(*) FROM received_evidence').fetchone()[0], 1)

    def test_corrupt_body_wrong_identity_and_invalid_structure(self):
        with stores() as (source, center):
            fixed = freeze(source, register(source, **load_sample()['old']))
            changed = json.loads(fixed.wire)
            changed['body']['accepting'] = [changed['body']['start']]
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                receive(center, fixed.issue_id, wire_for(changed))
            with self.assertRaisesRegex(ValueError, 'supplied issue number'):
                receive(center, fixed.issue_id + 1, fixed.wire)
            malformed = json.loads(fixed.wire)
            malformed.pop('digest')
            malformed['body']['transitions'][0][2] = malformed['body']['state_count']
            malformed['digest'] = hashlib.sha256(wire_for(malformed)).hexdigest()
            with self.assertRaisesRegex(ValueError, 'transition endpoint'):
                receive(center, fixed.issue_id, wire_for(malformed))
            count = center.execute('SELECT count(*) FROM received_evidence').fetchone()[0]
            self.assertEqual(count, 0)
            received = receive(center, fixed.issue_id, fixed.wire)
            self.assertEqual(received, 1)
            self.assertEqual(get_received(center, received).fixed.wire, fixed.wire)
            scenario('v4', {'issue': fixed.issue_id, 'change': 'accepting states with original digest'},
                     0, count, 1, received,
                     ['issue/evidence.py', 'compare/admission.py', 'compare/inbox.py'],
                     'Changing the accepting list changes the hashed payload. The original bytes can still be admitted as the first item.')
