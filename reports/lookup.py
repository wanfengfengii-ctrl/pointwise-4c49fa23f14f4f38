import json
import sqlite3

from reports.publish import ReportParent, SignedReport
from reports.receipt import get_receipt


def _read_witness(encoded: str) -> tuple[str, ...] | None:
    value = json.loads(encoded)
    return None if value is None else tuple(value)


def get_report(db: sqlite3.Connection, report_id: int) -> SignedReport | None:
    if type(report_id) is not int or not 0 < report_id < 2**63:
        raise ValueError('invalid report number')
    result = db.execute('SELECT left_only, right_only FROM signed_reports WHERE report_id = ?',
                        (report_id,)).fetchone()
    if result is None:
        return None
    rows = db.execute('''SELECT received_id, issue_id, revision_id, digest
        FROM report_parents WHERE report_id = ? ORDER BY position''', (report_id,)).fetchall()
    if len(rows) != 2:
        raise ValueError(f'report {report_id} has incomplete parent snapshots')
    return SignedReport(
        report_id,
        _read_witness(result[0]),
        _read_witness(result[1]),
        (ReportParent(*rows[0]), ReportParent(*rows[1])),
        get_receipt(db, report_id),
    )
