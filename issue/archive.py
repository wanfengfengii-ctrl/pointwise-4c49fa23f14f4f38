import sqlite3

from issue.evidence import FrozenEvidence, PublicEvidence, decode_evidence, seal_evidence


def initialize_issue_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS issued_evidence (
        issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        revision_id INTEGER NOT NULL REFERENCES recipe_revisions(revision_id),
        wire BLOB NOT NULL
    )''')


def store_issue(db: sqlite3.Connection, revision_id: int, evidence: PublicEvidence) -> FrozenEvidence:
    db.execute('BEGIN IMMEDIATE')
    with db:
        issue_id = db.execute(
            "INSERT INTO issued_evidence (revision_id, wire) VALUES (?, X'')", (revision_id,)
        ).lastrowid
        fixed = seal_evidence(issue_id, revision_id, evidence)
        db.execute('UPDATE issued_evidence SET wire = ? WHERE issue_id = ?', (fixed.wire, issue_id))
    return fixed


def get_issue(db: sqlite3.Connection, issue_id: int) -> FrozenEvidence:
    if type(issue_id) is not int or not 0 < issue_id < 2**63:
        raise ValueError('invalid issue number')
    row = db.execute('SELECT wire FROM issued_evidence WHERE issue_id = ?', (issue_id,)).fetchone()
    if row is None:
        raise LookupError(f'unknown issue {issue_id}')
    return decode_evidence(row[0])
