from dataclasses import dataclass
from typing import Mapping


CandidatePair = tuple[frozenset[int], frozenset[int]]


@dataclass(frozen=True, slots=True)
class WitnessLink:
    previous: CandidatePair
    code: str


def ordered_public_codes(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(left).union(right)))


def reconstruct_witness(
    endpoint: CandidatePair, predecessors: Mapping[CandidatePair, WitnessLink | None]
) -> tuple[str, ...]:
    actions = []
    link = predecessors[endpoint]
    while link is not None:
        actions.append(link.code)
        link = predecessors[link.previous]
    return tuple(reversed(actions))
