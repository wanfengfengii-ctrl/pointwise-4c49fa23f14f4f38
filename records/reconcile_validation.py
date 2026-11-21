from dataclasses import dataclass

from recipes.actions import require_text
from recipes.revisions import Revision


@dataclass(frozen=True, slots=True)
class ReconcileInput:
    revision_id: int
    trial_key: str
    controller_origin: str
    controller_actions: tuple[str, ...]
    crew_origin: str
    crew_actions: tuple[str, ...]


def _validate_source(source: object, name: str, revision: Revision) -> tuple[str, tuple[str, ...]]:
    if not isinstance(source, dict) or set(source.keys()) != {'origin', 'actions'}:
        raise ValueError(f'{name} source requires origin and actions')
    origin = require_text(source['origin'], f'{name} origin')
    actions = source['actions']
    if not isinstance(actions, (list, tuple)):
        raise ValueError(f'{name} actions must be an ordered array')
    for code in actions:
        if not isinstance(code, str) or not revision.catalog.contains(code):
            raise ValueError(
                f'unknown public action code {code!r} for revision {revision.revision_id}'
            )
    return origin, tuple(actions)


def validate_reconcile_input(
    revision: Revision, trial_key: object, controller: object, crew: object
) -> ReconcileInput:
    key = require_text(trial_key, 'trial key')
    controller_origin, controller_actions = _validate_source(controller, 'controller', revision)
    crew_origin, crew_actions = _validate_source(crew, 'crew', revision)
    return ReconcileInput(
        revision.revision_id,
        key,
        controller_origin,
        controller_actions,
        crew_origin,
        crew_actions,
    )
