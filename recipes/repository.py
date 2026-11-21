import json
import sqlite3

from recipes.actions import ActionCatalog, require_text
from recipes.revisions import Revision, revision_from_data, revision_to_data
from recipes.topology import StepGraph


def initialize_recipe_store(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS recipe_revisions (
        revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe TEXT NOT NULL,
        definition TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS current_revisions (
        recipe TEXT PRIMARY KEY,
        revision_id INTEGER NOT NULL REFERENCES recipe_revisions(revision_id)
    )''')


def save_revision(
    db: sqlite3.Connection, recipe: str, catalog: ActionCatalog, graph: StepGraph
) -> int:
    definition = json.dumps(revision_to_data(recipe, catalog, graph))
    db.execute('BEGIN IMMEDIATE')
    with db:
        revision_id = db.execute(
            'INSERT INTO recipe_revisions (recipe, definition) VALUES (?, ?)',
            (recipe, definition),
        ).lastrowid
        db.execute('''INSERT INTO current_revisions (recipe, revision_id) VALUES (?, ?)
            ON CONFLICT(recipe) DO UPDATE SET revision_id = excluded.revision_id''',
            (recipe, revision_id),
        )
    return revision_id


def get_revision(db: sqlite3.Connection, revision_id: int) -> Revision:
    if type(revision_id) is not int or not 0 < revision_id < 2**63:
        raise ValueError('invalid revision number')
    row = db.execute(
        'SELECT definition FROM recipe_revisions WHERE revision_id = ?', (revision_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f'unknown revision {revision_id}')
    return revision_from_data(revision_id, json.loads(row[0]))


def get_current_revision(db: sqlite3.Connection, recipe: str) -> Revision:
    recipe = require_text(recipe, 'recipe')
    row = db.execute('''SELECT r.revision_id, r.definition
        FROM current_revisions AS c JOIN recipe_revisions AS r USING (revision_id)
        WHERE c.recipe = ?''', (recipe,)).fetchone()
    if row is None:
        raise LookupError(f'unknown recipe {recipe!r}')
    return revision_from_data(row[0], json.loads(row[1]))
