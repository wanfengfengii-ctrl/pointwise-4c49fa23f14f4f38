from dataclasses import asdict, dataclass

from recipes.actions import ActionCatalog, build_action_catalog
from recipes.topology import StepGraph, build_step_graph


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: int
    recipe: str
    catalog: ActionCatalog
    graph: StepGraph


def revision_to_data(recipe: str, catalog: ActionCatalog, graph: StepGraph) -> dict:
    return {
        'recipe': recipe,
        'codes': list(catalog.codes),
        'steps': list(graph.steps),
        'start': graph.start,
        'accepting': sorted(graph.accepting),
        'edges': [asdict(edge) for edge in graph.edges],
    }


def revision_from_data(revision_id: int, data: dict) -> Revision:
    catalog = build_action_catalog(data['codes'])
    graph = build_step_graph(
        catalog, data['steps'], data['start'], data['accepting'], data['edges']
    )
    return Revision(revision_id, data['recipe'], catalog, graph)
