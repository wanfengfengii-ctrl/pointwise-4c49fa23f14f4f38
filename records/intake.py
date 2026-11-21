import sqlite3

from recipes.repository import get_revision
from records.conformance import check_complete_trace
from records.ledger import save_trace
from records.reconcile import reconcile_records
from records.reconcile_ledger import save_reconciliation
from records.reconcile_validation import validate_reconcile_input
from records.traceback import TrialTrace, get_reconciliation
from records.validation import validate_trace_input


def check_record(
    db: sqlite3.Connection, revision_id: int, actions: list[str] | tuple[str, ...], crew: str
) -> TrialTrace:
    revision = get_revision(db, revision_id)
    trace = validate_trace_input(revision, actions, crew)
    supported = check_complete_trace(revision.graph, trace.actions)
    trace_id = save_trace(db, trace, supported)
    return TrialTrace(trace_id, trace.revision_id, trace.actions, trace.crew, supported)


def reconcile_trial(
    db: sqlite3.Connection,
    trial_key: str,
    revision_id: int,
    controller: dict,
    crew: dict,
) -> dict:
    revision = get_revision(db, revision_id)
    source = validate_reconcile_input(revision, trial_key, controller, crew)
    outcome = reconcile_records(revision.graph, source.controller_actions, source.crew_actions)
    reconciliation_id = save_reconciliation(db, source, outcome)
    return get_reconciliation(db, reconciliation_id)
