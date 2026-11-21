from collections import deque
from dataclasses import dataclass

from recipes.topology import StepGraph


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    actions: tuple[str, ...] | None
    controller_positions: tuple[int, ...] | None
    crew_positions: tuple[int, ...] | None
    confirmed: tuple[tuple[int, int], ...]


ProductState = tuple[int, int, int]


def _confirmed_pairs(
    shortest_states: set[ProductState],
    forward: dict[ProductState, int],
    hidden_forward: list[frozenset[int]],
    indexed_edges: list[list[tuple[int, str | None]]],
    controller: tuple[str, ...],
    crew: tuple[str, ...],
    initial: ProductState,
    shortest_length: int,
) -> tuple[tuple[int, int], ...]:
    """Intersection of equal-position pairs over every shortest alignment.

    A forward dynamic program over the shortest DAG stores, per state, the set
    of (controller item, crew item) pairs that share a public beat on every
    shortest path reaching that state. A public move contributes the pair when
    both sources consume it; distinct predecessor paths merge with an
    intersection, so a pair missing from any shortest path is dropped.
    """
    controller_total, crew_total = len(controller), len(crew)

    # Build the explicit shortest DAG: a public move after hidden closure that
    # stays inside shortest_states and raises the distance by exactly one.
    incoming: dict[ProductState, list[tuple[ProductState, bool, bool]]] = {}
    for predecessor in shortest_states:
        previous_step, previous_i, previous_j = predecessor
        base = forward[predecessor]
        for hidden_step in hidden_forward[previous_step]:
            for target, code in indexed_edges[hidden_step]:
                if code is None:
                    continue
                consume_i = previous_i < controller_total and controller[previous_i] == code
                consume_j = previous_j < crew_total and crew[previous_j] == code
                options = ((previous_i, previous_j, False, False),)
                if consume_i:
                    options += ((previous_i + 1, previous_j, True, False),)
                if consume_j:
                    options += ((previous_i, previous_j + 1, False, True),)
                if consume_i and consume_j:
                    options += ((previous_i + 1, previous_j + 1, True, True),)
                for next_i, next_j, used_i, used_j in options:
                    successor = (target, next_i, next_j)
                    if successor in shortest_states and forward.get(successor) == base + 1:
                        incoming.setdefault(successor, []).append(
                            (predecessor, used_i, used_j)
                        )

    feasible: dict[ProductState, frozenset[tuple[int, int]]] = {initial: frozenset()}
    for state in sorted(shortest_states, key=lambda item: forward[item]):
        if state == initial:
            continue
        merged: frozenset[tuple[int, int]] | None = None
        for predecessor, used_i, used_j in incoming.get(state, ()):
            prefix = feasible.get(predecessor)
            if prefix is None:
                continue
            added = (
                frozenset({(predecessor[1], predecessor[2])})
                if used_i and used_j
                else frozenset()
            )
            candidate = prefix | added
            merged = candidate if merged is None else (merged & candidate)
        if merged is not None:
            feasible[state] = merged

    goal_sets = [
        feasible[state]
        for state in shortest_states
        if forward[state] == shortest_length
        and state[1] == controller_total
        and state[2] == crew_total
        and state in feasible
    ]
    if not goal_sets:
        return ()
    result = goal_sets[0]
    for candidate in goal_sets[1:]:
        result = result & candidate
    return tuple(sorted((controller_index + 1, crew_index + 1)
                        for controller_index, crew_index in result))


def _layer_distances(
    indexed_edges,
    step_count: int,
    controller: tuple[str, ...],
    crew: tuple[str, ...],
    seeds: list[ProductState],
    reverse: bool,
) -> dict[ProductState, int]:
    """Shortest public-action distance to every reachable product state.

    The search expands one public-action layer at a time. Hidden edges are
    weight zero, so all states reachable through hidden moves from a layer are
    folded into that same layer before public successors are computed. Every
    state enters the distance map once at its minimum layer. Reversing swaps
    public edge direction and turns consuming an action into un-consuming it.
    """
    if reverse:
        adjacency: list[list[tuple[int, str | None]]] = [[] for _ in range(step_count)]
        for source, edges in enumerate(indexed_edges):
            for target, code in edges:
                adjacency[target].append((source, code))
    else:
        adjacency = indexed_edges

    # Hidden reachability per step (same relation in either traversal direction
    # is not assumed: compute it directly from the edges actually followed).
    hidden_forward = _hidden_relations(indexed_edges, reverse=False)
    hidden_backward = _hidden_relations(indexed_edges, reverse=True)
    hidden = hidden_backward if reverse else hidden_forward
    controller_total, crew_total = len(controller), len(crew)

    distances: dict[ProductState, int] = {}
    frontier: set[ProductState] = set()

    def admit(state: ProductState, distance: int) -> None:
        """Register a public successor and every step in its hidden closure at
        the same layer. All of them join the next frontier so their public edges
        are expanded in the following iteration."""
        step, offsets_i, offsets_j = state
        for hidden_step in hidden[step]:
            hidden_state = (hidden_step, offsets_i, offsets_j)
            if hidden_state not in distances:
                distances[hidden_state] = distance
                next_frontier.add(hidden_state)

    for step, offsets_i, offsets_j in seeds:
        for hidden_step in hidden[step]:
            state = (hidden_step, offsets_i, offsets_j)
            if state not in distances:
                distances[state] = 0
                frontier.add(state)
    layer = 0
    while frontier:
        next_frontier: set[ProductState] = set()
        for state in frontier:
            step, offsets_i, offsets_j = state
            for hidden_step in hidden[step]:
                for target, code in adjacency[hidden_step]:
                    if code is None:
                        continue
                    if reverse:
                        un_i = offsets_i > 0 and controller[offsets_i - 1] == code
                        un_j = offsets_j > 0 and crew[offsets_j - 1] == code
                        admit((target, offsets_i, offsets_j), layer + 1)
                        if un_i:
                            admit((target, offsets_i - 1, offsets_j), layer + 1)
                        if un_j:
                            admit((target, offsets_i, offsets_j - 1), layer + 1)
                        if un_i and un_j:
                            admit((target, offsets_i - 1, offsets_j - 1), layer + 1)
                    else:
                        consume_i = offsets_i < controller_total and controller[offsets_i] == code
                        consume_j = offsets_j < crew_total and crew[offsets_j] == code
                        admit((target, offsets_i, offsets_j), layer + 1)
                        if consume_i:
                            admit((target, offsets_i + 1, offsets_j), layer + 1)
                        if consume_j:
                            admit((target, offsets_i, offsets_j + 1), layer + 1)
                        if consume_i and consume_j:
                            admit((target, offsets_i + 1, offsets_j + 1), layer + 1)
        frontier = next_frontier
        layer += 1
    return distances


def _hidden_relations(indexed_edges, reverse: bool) -> list[frozenset[int]]:
    step_count = len(indexed_edges)
    relations: list[set[int]] = [set() for _ in range(step_count)]
    for source, edges in enumerate(indexed_edges):
        for target, code in edges:
            if code is None:
                if reverse:
                    relations[target].add(source)
                else:
                    relations[source].add(target)
    closures: list[frozenset[int]] = []
    for origin in range(step_count):
        reachable = {origin}
        pending = [origin]
        while pending:
            current = pending.pop()
            for nxt in relations[current]:
                if nxt not in reachable:
                    reachable.add(nxt)
                    pending.append(nxt)
        closures.append(frozenset(reachable))
    return closures


def reconcile_records(
    graph: StepGraph,
    controller: tuple[str, ...],
    crew: tuple[str, ...],
) -> ReconciliationOutcome:
    steps = graph.steps
    step_count = len(steps)
    step_index = {step: position for position, step in enumerate(steps)}
    outgoing = graph.outgoing()
    start = step_index[graph.start]
    accepting = {step_index[step] for step in graph.accepting}
    indexed_edges: list[list[tuple[int, str | None]]] = [
        [(step_index[edge.target], edge.code) for edge in outgoing[step]]
        for step in steps
    ]
    hidden_forward = _hidden_relations(indexed_edges, reverse=False)

    initial: ProductState = (start, 0, 0)
    forward = _layer_distances(
        indexed_edges, step_count, controller, crew, [initial], reverse=False
    )
    goals = [
        (step, len(controller), len(crew))
        for step in accepting
        if (step, len(controller), len(crew)) in forward
    ]
    if not goals:
        return ReconciliationOutcome(None, None, None, ())
    shortest_length = min(forward[state] for state in goals)
    backward = _layer_distances(
        indexed_edges, step_count, controller, crew, goals, reverse=True
    )

    def on_shortest(state: ProductState) -> bool:
        return state in backward and forward[state] + backward[state] == shortest_length

    shortest_states = {state for state in forward if on_shortest(state)}

    # Representative shortest completion: BFS over shortest states where a move
    # is one public action after any number of free hidden moves. The parent map
    # prevents loops and distances rise by exactly one per move.
    actions: list[str] = []
    controller_positions: list[int] = []
    crew_positions: list[int] = []
    if shortest_length > 0:
        parents: dict[ProductState, ProductState | None] = {initial: None}
        chosen_code: dict[ProductState, str] = {}
        queue: deque[ProductState] = deque([initial])
        endpoint = None
        while queue and endpoint is None:
            state = queue.popleft()
            step, offsets_i, offsets_j = state
            for hidden_step in hidden_forward[step]:
                for target, code in indexed_edges[hidden_step]:
                    if code is None:
                        continue
                    consume_i = offsets_i < len(controller) and controller[offsets_i] == code
                    consume_j = offsets_j < len(crew) and crew[offsets_j] == code
                    candidates = ((target, offsets_i, offsets_j),)
                    if consume_i:
                        candidates += ((target, offsets_i + 1, offsets_j),)
                    if consume_j:
                        candidates += ((target, offsets_i, offsets_j + 1),)
                    if consume_i and consume_j:
                        candidates += ((target, offsets_i + 1, offsets_j + 1),)
                    for successor in candidates:
                        if successor in shortest_states and successor not in parents and forward[successor] == forward[state] + 1:
                            parents[successor] = state
                            chosen_code[successor] = code
                            queue.append(successor)
                            if forward[successor] == shortest_length and any(
                                hidden in accepting for hidden in hidden_forward[successor[0]]
                            ):
                                endpoint = successor
                                break
                if endpoint is not None:
                    break
        if endpoint is None:
            raise ValueError('shortest reconstruction cannot reach an accepting state')

        chain: list[tuple[ProductState, ProductState]] = []
        cursor = endpoint
        while cursor != initial:
            previous = parents[cursor]
            if previous is None:
                raise ValueError('shortest reconstruction lost its predecessor chain')
            chain.append((previous, cursor))
            cursor = previous
        chain.reverse()

        for previous, current in chain:
            position = len(actions) + 1
            actions.append(chosen_code[current])
            if current[1] == previous[1] + 1:
                controller_positions.append(position)
            if current[2] == previous[2] + 1:
                crew_positions.append(position)

    # Confirmed same-beat pairs must share one public move on every shortest
    # completion and every legal alignment. Compute this exactly with a dynamic
    # program over the shortest DAG (edges that stay inside shortest_states and
    # raise the distance by exactly one). Each state carries the feasible-pair
    # set of its prefix: union along one path's edges, intersection at
    # confluences where distinct shortest paths merge. A pair produced by one
    # path but not another is removed by the intersection, matching the rule
    # that any shortest completion or alignment placing the two items apart
    # disqualifies the pair.
    confirmed = _confirmed_pairs(
        shortest_states,
        forward,
        hidden_forward,
        indexed_edges,
        controller,
        crew,
        initial,
        shortest_length,
    )

    return ReconciliationOutcome(
        tuple(actions),
        tuple(controller_positions),
        tuple(crew_positions),
        confirmed,
    )
