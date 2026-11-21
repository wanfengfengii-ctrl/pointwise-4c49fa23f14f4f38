import sqlite3
from dataclasses import dataclass

from issue.evidence import FrozenEvidence, decode_evidence


@dataclass(frozen=True, slots=True)
class ReceivedEvidence:
    received_id: int
    fixed: FrozenEvidence


def initialize_inbox(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS received_evidence (
        received_id INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id INTEGER NOT NULL UNIQUE,
        revision_id INTEGER NOT NULL,
        digest TEXT NOT NULL,
        wire BLOB NOT NULL
    )''')


def store_received(db: sqlite3.Connection, fixed: FrozenEvidence) -> int:
    db.execute('BEGIN IMMEDIATE')
    with db:
        existing = db.execute(
            'SELECT received_id, wire FROM received_evidence WHERE issue_id = ?',
            (fixed.issue_id,),
        ).fetchone()
        if existing is not None:
            if existing[1] != fixed.wire:
                raise ValueError(f'conflicting evidence for issue {fixed.issue_id}')
            return existing[0]
        received_id = db.execute('''INSERT INTO received_evidence
            (issue_id, revision_id, digest, wire) VALUES (?, ?, ?, ?)''',
            (fixed.issue_id, fixed.revision_id, fixed.digest, fixed.wire),
        ).lastrowid
    return received_id


def get_received(db: sqlite3.Connection, received_id: int) -> ReceivedEvidence:
    if type(received_id) is not int or not 0 < received_id < 2**63:
        raise ValueError('invalid received number')
    row = db.execute(
        'SELECT wire FROM received_evidence WHERE received_id = ?', (received_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'unknown received evidence {received_id}')
    return ReceivedEvidence(received_id, decode_evidence(row[0]))
