import sqlite3

from recipes.repository import get_revision
from records.conformance import check_complete_trace
from records.ledger import save_trace
from records.traceback import TrialTrace
from records.validation import validate_trace_input


def check_record(
    db: sqlite3.Connection, revision_id: int, actions: list[str] | tuple[str, ...], crew: str
) -> TrialTrace:
    revision = get_revision(db, revision_id)
    trace = validate_trace_input(revision, actions, crew)
    supported = check_complete_trace(revision.graph, trace.actions)
    trace_id = save_trace(db, trace, supported)
    return TrialTrace(trace_id, trace.revision_id, trace.actions, trace.crew, supported)
