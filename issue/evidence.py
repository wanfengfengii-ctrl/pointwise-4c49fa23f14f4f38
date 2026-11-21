import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicEvidence:
    codes: tuple[str, ...]
    state_count: int
    start: int
    accepting: tuple[int, ...]
    transitions: tuple[tuple[int, str, int], ...]


@dataclass(frozen=True, slots=True)
class FrozenEvidence:
    issue_id: int
    revision_id: int
    digest: str
    evidence: PublicEvidence
    wire: bytes


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def _identifier(value: object) -> bool:
    return type(value) is int and 0 < value < 2**63


def _valid_code(code: object) -> bool:
    return (
        isinstance(code, str)
        and bool(code.strip())
        and all(not 0xD800 <= ord(character) <= 0xDFFF for character in code)
    )


def _read_public(body: object) -> PublicEvidence:
    expected = {'codes', 'state_count', 'start', 'accepting', 'transitions'}
    if not isinstance(body, dict) or body.keys() != expected:
        raise ValueError('invalid public evidence fields')
    count = body['state_count']
    if type(count) is not int or count < 1:
        raise ValueError('invalid public state count')

    def is_state(value: object) -> bool:
        return type(value) is int and 0 <= value < count

    start, accepting = body['start'], body['accepting']
    if not is_state(start) or not isinstance(accepting, list) or not all(map(is_state, accepting)):
        raise ValueError('invalid public start or accepting state')
    if len(set(accepting)) != len(accepting):
        raise ValueError('duplicate public accepting state')

    codes = body['codes']
    if not isinstance(codes, list) or not all(map(_valid_code, codes)):
        raise ValueError('invalid public code catalog')
    known = set(codes)
    if len(known) != len(codes):
        raise ValueError('duplicate public code')

    transitions = body['transitions']
    if not isinstance(transitions, list):
        raise ValueError('public transitions must be an array')
    edges = []
    for edge in transitions:
        if not isinstance(edge, list) or len(edge) != 3:
            raise ValueError('invalid public transition')
        source, code, target = edge
        if not is_state(source) or not is_state(target):
            raise ValueError('invalid public transition endpoint')
        if not isinstance(code, str) or code not in known:
            raise ValueError('undeclared public transition code')
        edges.append((source, code, target))
    if len(set(edges)) != len(edges):
        raise ValueError('duplicate public transition')
    return PublicEvidence(tuple(codes), count, start, tuple(accepting), tuple(edges))


def _read_envelope(wire: bytes) -> dict:
    if type(wire) is not bytes:
        raise ValueError('fixed evidence must be bytes')
    try:
        data = json.loads(wire.decode('utf-8'))
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid evidence JSON') from exc
    keys = {'version', 'issue_id', 'revision_id', 'body', 'digest'}
    if not isinstance(data, dict) or data.keys() != keys:
        raise ValueError('invalid evidence envelope fields')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('unsupported evidence version')
    if not _identifier(data['issue_id']) or not _identifier(data['revision_id']):
        raise ValueError('invalid evidence identity')
    digest = data['digest']
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid evidence digest encoding')
    return data


def decode_evidence(wire: bytes) -> FrozenEvidence:
    data = _read_envelope(wire)
    evidence = _read_public(data['body'])
    if _canonical(data) != wire:
        raise ValueError('fixed evidence is not canonically encoded')
    return FrozenEvidence(data['issue_id'], data['revision_id'], data['digest'], evidence, wire)


def seal_evidence(issue_id: int, revision_id: int, evidence: PublicEvidence) -> FrozenEvidence:
    payload = {
        'version': 1,
        'issue_id': issue_id,
        'revision_id': revision_id,
        'body': {
            'codes': evidence.codes,
            'state_count': evidence.state_count,
            'start': evidence.start,
            'accepting': evidence.accepting,
            'transitions': evidence.transitions,
        },
    }
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    return decode_evidence(_canonical({**payload, 'digest': digest}))


def verify_evidence(expected_issue_id: int, wire: bytes) -> FrozenEvidence:
    fixed = decode_evidence(wire)
    if not _identifier(expected_issue_id) or fixed.issue_id != expected_issue_id:
        raise ValueError('fixed evidence does not match the supplied issue number')
    payload = json.loads(wire)
    payload.pop('digest')
    if hashlib.sha256(_canonical(payload)).hexdigest() != fixed.digest:
        raise ValueError('fixed evidence digest mismatch')
    return fixed
