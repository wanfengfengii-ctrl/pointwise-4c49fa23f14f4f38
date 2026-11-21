import json
import sqlite3
from dataclasses import dataclass

from reports.receipt import SuccessReceipt, initialize_receipt_store, write_receipt


@dataclass(frozen=True, slots=True)
class ReportParent:
    received_id: int
    issue_id: int
    revision_id: int
    digest: str


@dataclass(frozen=True, slots=True)
class SignedReport:
    report_id: int
    left_only: tuple[str, ...] | None
    right_only: tuple[str, ...] | None
    parents: tuple[ReportParent, ReportParent]
    receipt: SuccessReceipt


def initialize_report_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS signed_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        left_only TEXT NOT NULL,
        right_only TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS report_parents (
        report_id INTEGER NOT NULL REFERENCES signed_reports(report_id),
        position INTEGER NOT NULL CHECK (position IN (0, 1)),
        received_id INTEGER NOT NULL REFERENCES received_evidence(received_id),
        issue_id INTEGER NOT NULL,
        revision_id INTEGER NOT NULL,
        digest TEXT NOT NULL,
        PRIMARY KEY (report_id, position)
    )''')
    initialize_receipt_store(db)


def publish_report(
    db: sqlite3.Connection,
    parents: tuple[ReportParent, ReportParent],
    left_only: tuple[str, ...] | None,
    right_only: tuple[str, ...] | None,
) -> SignedReport:
    if len(parents) != 2:
        raise ValueError('a report requires two ordered parents')
    db.execute('BEGIN IMMEDIATE')
    with db:
        report_id = db.execute(
            'INSERT INTO signed_reports (left_only, right_only) VALUES (?, ?)',
            (json.dumps(left_only), json.dumps(right_only)),
        ).lastrowid
        for position, parent in enumerate(parents):
            inserted = db.execute('''INSERT INTO report_parents
                (report_id, position, received_id, issue_id, revision_id, digest)
                SELECT ?, ?, received_id, issue_id, revision_id, digest FROM received_evidence
                WHERE received_id = ? AND issue_id = ? AND revision_id = ? AND digest = ?''',
                (report_id, position, parent.received_id, parent.issue_id, parent.revision_id, parent.digest),
            )
            if inserted.rowcount != 1:
                raise ValueError(f'parent snapshot does not match received evidence {parent.received_id}')
        receipt = write_receipt(db, report_id)
    return SignedReport(report_id, left_only, right_only, parents, receipt)
