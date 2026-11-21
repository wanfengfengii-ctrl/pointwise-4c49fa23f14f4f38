import json
import sqlite3

from records.reconcile_validation import ReconcileInput
from records.reconcile import ReconciliationOutcome


def initialize_reconciliation_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS trial_reconciliations (
        reconciliation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trial_key TEXT NOT NULL,
        revision_id INTEGER NOT NULL REFERENCES recipe_revisions(revision_id),
        controller_origin TEXT NOT NULL,
        controller_actions TEXT NOT NULL,
        crew_origin TEXT NOT NULL,
        crew_actions TEXT NOT NULL,
        restored_actions TEXT NOT NULL,
        controller_positions TEXT NOT NULL,
        crew_positions TEXT NOT NULL,
        confirmed TEXT NOT NULL
    )''')


def save_reconciliation(
    db: sqlite3.Connection,
    source: ReconcileInput,
    outcome: ReconciliationOutcome,
) -> int:
    db.execute('BEGIN IMMEDIATE')
    with db:
        reconciliation_id = db.execute('''INSERT INTO trial_reconciliations
            (trial_key, revision_id, controller_origin, controller_actions,
             crew_origin, crew_actions, restored_actions, controller_positions,
             crew_positions, confirmed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            source.trial_key,
            source.revision_id,
            source.controller_origin,
            json.dumps(source.controller_actions),
            source.crew_origin,
            json.dumps(source.crew_actions),
            json.dumps(None if outcome.actions is None else list(outcome.actions)),
            json.dumps(None if outcome.controller_positions is None
                       else list(outcome.controller_positions)),
            json.dumps(None if outcome.crew_positions is None
                       else list(outcome.crew_positions)),
            json.dumps([list(pair) for pair in outcome.confirmed]),
        )).lastrowid
    return reconciliation_id


def get_reconciliation_row(db: sqlite3.Connection, reconciliation_id: int) -> tuple:
    if type(reconciliation_id) is not int or not 0 < reconciliation_id < 2**63:
        raise ValueError('invalid reconciliation number')
    row = db.execute('''SELECT trial_key, revision_id, controller_origin, controller_actions,
        crew_origin, crew_actions, restored_actions, controller_positions, crew_positions, confirmed
        FROM trial_reconciliations WHERE reconciliation_id = ?''',
        (reconciliation_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown reconciliation {reconciliation_id}')
    return row
