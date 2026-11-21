import sqlite3

from recipes.actions import build_action_catalog, require_text
from recipes.repository import save_revision
from recipes.topology import build_step_graph


def register(
    db: sqlite3.Connection,
    recipe: str,
    codes: list[str],
    steps: list[str],
    start: str,
    accepting: list[str],
    edges: list[dict],
) -> int:
    recipe = require_text(recipe, 'recipe')
    catalog = build_action_catalog(codes)
    graph = build_step_graph(catalog, steps, start, accepting, edges)
    return save_revision(db, recipe, catalog, graph)
