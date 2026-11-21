import sqlite3

from compare.distinction import find_distinctions
from compare.inbox import ReceivedEvidence, get_received
from reports.publish import ReportParent, SignedReport, publish_report


def resolve_pair(
    db: sqlite3.Connection, left_id: int, right_id: int
) -> tuple[ReceivedEvidence, ReceivedEvidence]:
    return get_received(db, left_id), get_received(db, right_id)


def _parent(received: ReceivedEvidence) -> ReportParent:
    fixed = received.fixed
    return ReportParent(received.received_id, fixed.issue_id, fixed.revision_id, fixed.digest)


def compare_pair(db: sqlite3.Connection, left_id: int, right_id: int) -> SignedReport:
    left, right = resolve_pair(db, left_id, right_id)
    differences = find_distinctions(left.fixed.evidence, right.fixed.evidence)
    return publish_report(
        db, (_parent(left), _parent(right)), differences.left_only, differences.right_only
    )
