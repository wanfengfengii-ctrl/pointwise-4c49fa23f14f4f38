import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SuccessReceipt:
    receipt_id: int
    report_id: int


def initialize_receipt_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS report_receipts (
        receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL UNIQUE REFERENCES signed_reports(report_id)
    )''')


def write_receipt(db: sqlite3.Connection, report_id: int) -> SuccessReceipt:
    if not db.in_transaction:
        raise ValueError('a receipt requires the report publication transaction')
    receipt_id = db.execute(
        'INSERT INTO report_receipts (report_id) VALUES (?)', (report_id,)
    ).lastrowid
    return SuccessReceipt(receipt_id, report_id)


def get_receipt(db: sqlite3.Connection, report_id: int) -> SuccessReceipt:
    row = db.execute(
        'SELECT receipt_id FROM report_receipts WHERE report_id = ?', (report_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'report {report_id} has no success receipt')
    return SuccessReceipt(row[0], report_id)
