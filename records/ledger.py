import json
import sqlite3

from records.validation import TraceInput


def initialize_trace_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS trial_traces (
        trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
        revision_id INTEGER NOT NULL REFERENCES recipe_revisions(revision_id),
        crew TEXT NOT NULL,
        actions TEXT NOT NULL,
        supported INTEGER NOT NULL CHECK (supported IN (0, 1))
    )''')


def save_trace(db: sqlite3.Connection, trace: TraceInput, supported: bool) -> int:
    db.execute('BEGIN IMMEDIATE')
    with db:
        trace_id = db.execute('''INSERT INTO trial_traces
            (revision_id, crew, actions, supported) VALUES (?, ?, ?, ?)''',
            (trace.revision_id, trace.crew, json.dumps(trace.actions), int(supported)),
        ).lastrowid
    return trace_id


def get_trace_row(db: sqlite3.Connection, trace_id: int) -> tuple:
    if type(trace_id) is not int or not 0 < trace_id < 2**63:
        raise ValueError('invalid trace number')
    row = db.execute('''SELECT revision_id, crew, actions, supported
        FROM trial_traces WHERE trace_id = ?''', (trace_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown trace {trace_id}')
    return row
