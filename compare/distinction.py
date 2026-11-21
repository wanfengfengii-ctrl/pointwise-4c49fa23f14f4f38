from collections import defaultdict, deque
from dataclasses import dataclass

from compare.witness import CandidatePair, WitnessLink, ordered_public_codes, reconstruct_witness
from issue.evidence import PublicEvidence


@dataclass(frozen=True, slots=True)
class DirectionalDifferences:
    left_only: tuple[str, ...] | None
    right_only: tuple[str, ...] | None


def _index(evidence: PublicEvidence) -> dict[tuple[int, str], set[int]]:
    edges = defaultdict(set)
    for source, code, target in evidence.transitions:
        edges[source, code].add(target)
    return edges


def _advance(
    states: frozenset[int], code: str, edges: dict[tuple[int, str], set[int]]
) -> frozenset[int]:
    return frozenset(target for state in states for target in edges.get((state, code), ()))


def find_distinctions(left: PublicEvidence, right: PublicEvidence) -> DirectionalDifferences:
    left_edges, right_edges = _index(left), _index(right)
    left_finals, right_finals = frozenset(left.accepting), frozenset(right.accepting)
    codes = ordered_public_codes(left.codes, right.codes)
    start = (frozenset({left.start}), frozenset({right.start}))
    predecessors: dict[CandidatePair, WitnessLink | None] = {start: None}
    pending = deque([start])
    left_only = right_only = None

    while pending:
        pair = pending.popleft()
        left_states, right_states = pair
        left_complete = not left_finals.isdisjoint(left_states)
        right_complete = not right_finals.isdisjoint(right_states)
        if left_complete and not right_complete and left_only is None:
            left_only = reconstruct_witness(pair, predecessors)
        if right_complete and not left_complete and right_only is None:
            right_only = reconstruct_witness(pair, predecessors)
        if left_only is not None and right_only is not None:
            break

        for code in codes:
            successor = (
                _advance(left_states, code, left_edges),
                _advance(right_states, code, right_edges),
            )
            if any(successor) and successor not in predecessors:
                predecessors[successor] = WitnessLink(pair, code)
                pending.append(successor)

    return DirectionalDifferences(left_only, right_only)
