import json
import sqlite3
from dataclasses import dataclass

from records.ledger import get_trace_row
from records.reconcile_ledger import get_reconciliation_row


@dataclass(frozen=True, slots=True)
class TrialTrace:
    trace_id: int
    revision_id: int
    actions: tuple[str, ...]
    crew: str
    supported: bool


def get_trace(db: sqlite3.Connection, trace_id: int) -> TrialTrace:
    revision_id, crew, actions, supported = get_trace_row(db, trace_id)
    return TrialTrace(trace_id, revision_id, tuple(json.loads(actions)), crew, bool(supported))


def get_reconciliation(db: sqlite3.Connection, reconciliation_id: int) -> dict:
    row = get_reconciliation_row(db, reconciliation_id)
    (
        trial_key,
        revision_id,
        controller_origin,
        controller_actions,
        crew_origin,
        crew_actions,
        restored_actions,
        controller_positions,
        crew_positions,
        confirmed,
    ) = row
    actions = json.loads(restored_actions)
    positions = None
    if actions is not None:
        positions = {
            'controller': json.loads(controller_positions),
            'crew': json.loads(crew_positions),
        }
    return {
        'reconciliation_id': reconciliation_id,
        'trial_key': trial_key,
        'revision_id': revision_id,
        'controller': {
            'origin': controller_origin,
            'actions': json.loads(controller_actions),
        },
        'crew': {
            'origin': crew_origin,
            'actions': json.loads(crew_actions),
        },
        'actions': actions,
        'positions': positions,
        'confirmed': json.loads(confirmed),
    }
