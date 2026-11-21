from dataclasses import dataclass

from recipes.actions import require_text
from recipes.revisions import Revision


@dataclass(frozen=True, slots=True)
class TraceInput:
    revision_id: int
    actions: tuple[str, ...]
    crew: str


def validate_trace_input(revision: Revision, actions: object, crew: object) -> TraceInput:
    origin = require_text(crew, 'crew')
    if not isinstance(actions, (list, tuple)):
        raise ValueError('actions must be an ordered array')
    for code in actions:
        if not isinstance(code, str) or not revision.catalog.contains(code):
            raise ValueError(f'unknown public action code {code!r} for revision {revision.revision_id}')
    return TraceInput(revision.revision_id, tuple(actions), origin)
