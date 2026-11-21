import json
import sqlite3
from dataclasses import dataclass

from records.ledger import get_trace_row


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
