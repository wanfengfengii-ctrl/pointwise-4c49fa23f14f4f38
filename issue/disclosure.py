from collections import deque

from issue.evidence import PublicEvidence
from recipes.revisions import Revision
from recipes.topology import StepEdge


def _hidden_reach(start: str, outgoing: dict[str, list[StepEdge]]) -> set[str]:
    reachable = {start}
    pending = [start]
    while pending:
        step = pending.pop()
        for edge in outgoing[step]:
            if edge.code is None and edge.target not in reachable:
                reachable.add(edge.target)
                pending.append(edge.target)
    return reachable


def build_public_evidence(revision: Revision) -> PublicEvidence:
    graph = revision.graph
    outgoing = graph.outgoing()
    order = {step: position for position, step in enumerate(graph.steps)}
    public_id = {graph.start: 0}
    pending = deque([graph.start])
    accepting = []
    transitions = []
    while pending:
        step = pending.popleft()
        source_id = public_id[step]
        reachable = _hidden_reach(step, outgoing)
        if not graph.accepting.isdisjoint(reachable):
            accepting.append(source_id)

        # Each post-action target accounts for its own hidden steps when expanded.
        choices = {
            (edge.code, edge.target)
            for hidden_step in reachable
            for edge in outgoing[hidden_step]
            if edge.code is not None
        }
        for code, target in sorted(choices, key=lambda choice: (choice[0], order[choice[1]])):
            if target not in public_id:
                public_id[target] = len(public_id)
                pending.append(target)
            transitions.append((source_id, code, public_id[target]))

    return PublicEvidence(
        revision.catalog.codes, len(public_id), 0, tuple(accepting), tuple(transitions)
    )
