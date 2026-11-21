import sqlite3

from compare.inbox import store_received
from issue.evidence import verify_evidence


def receive(db: sqlite3.Connection, issue_id: int, wire: bytes) -> int:
    return store_received(db, verify_evidence(issue_id, wire))
