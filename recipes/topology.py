from dataclasses import dataclass

from recipes.actions import ActionCatalog, require_text


@dataclass(frozen=True, slots=True)
class StepEdge:
    source: str
    target: str
    code: str | None
    note: str = ''


@dataclass(frozen=True, slots=True)
class StepGraph:
    steps: tuple[str, ...]
    start: str
    accepting: frozenset[str]
    edges: tuple[StepEdge, ...]

    def outgoing(self) -> dict[str, list[StepEdge]]:
        index: dict[str, list[StepEdge]] = {step: [] for step in self.steps}
        for edge in self.edges:
            index[edge.source].append(edge)
        return index


def _step_names(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f'{field} must be an array')
    names = tuple(require_text(value, field) for value in values)
    if len(set(names)) != len(names):
        raise ValueError(f'duplicate name in {field}')
    return names


def build_step_graph(
    catalog: ActionCatalog,
    steps: object,
    start: object,
    accepting: object,
    edges: object,
) -> StepGraph:
    names = _step_names(steps, 'steps')
    known = set(names)
    initial = require_text(start, 'start')
    finals = frozenset(_step_names(accepting, 'accepting'))
    if initial not in known or not finals <= known:
        raise ValueError('start and accepting states must be declared steps')
    if not isinstance(edges, (list, tuple)):
        raise ValueError('edges must be an array')
    validated = []
    required = {'source', 'target', 'code'}
    for edge in edges:
        if not isinstance(edge, dict) or not required <= edge.keys() <= required | {'note'}:
            raise ValueError('edge requires source, target and code, with an optional note')
        source = require_text(edge['source'], 'edge source')
        target = require_text(edge['target'], 'edge target')
        if source not in known or target not in known:
            raise ValueError(f'undeclared step in edge {source!r} to {target!r}')
        code = edge['code']
        if code is not None and (not isinstance(code, str) or not catalog.contains(code)):
            raise ValueError(f'unknown public action code {code!r}')
        note = edge.get('note', '')
        if not isinstance(note, str):
            raise ValueError('note must be text')
        validated.append(StepEdge(source, target, code, note))
    return StepGraph(names, initial, finals, tuple(validated))
