import sqlite3

from issue.archive import store_issue
from issue.disclosure import build_public_evidence
from issue.evidence import FrozenEvidence
from recipes.repository import get_revision


def freeze(db: sqlite3.Connection, revision_id: int) -> FrozenEvidence:
    revision = get_revision(db, revision_id)
    return store_issue(db, revision.revision_id, build_public_evidence(revision))
