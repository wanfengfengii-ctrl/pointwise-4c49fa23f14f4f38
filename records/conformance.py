from collections import deque

from recipes.topology import StepGraph


def check_complete_trace(graph: StepGraph, actions: tuple[str, ...]) -> bool:
    outgoing = graph.outgoing()
    initial = (graph.start, 0)
    pending = deque([initial])
    seen = {initial}
    while pending:
        step, offset = pending.popleft()
        if offset == len(actions) and step in graph.accepting:
            return True
        for edge in outgoing[step]:
            if edge.code is None:
                next_offset = offset
            elif offset < len(actions) and edge.code == actions[offset]:
                next_offset = offset + 1
            else:
                continue
            successor = (edge.target, next_offset)
            if successor not in seen:
                seen.add(successor)
                pending.append(successor)
    return False
