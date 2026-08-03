from config.settings import MAX_SEARCHES
from db.query_rotation import get_next_queries_for_family
from db.expanded_queries import get_queries_grouped_by_family
from graph.phase3.state import TopLevelState
from utils.logger import get_logger

log = get_logger()


def planner_node(state: TopLevelState) -> dict:
    """Top-level planner — weighted selection split evenly across role
    families. Also serves as the mid-run REPLAN step: if the graph loops
    back here (zero results, or chasing a high-yield query), only ONE
    new query is added — from whichever family the replan counter points
    at — excluding anything already tried this run."""
    already_tried = set(state.get("queries", []))
    is_replan = len(already_tried) > 0

    grouped = get_queries_grouped_by_family()
    families = list(grouped.keys())
    num_families = len(families)

    if is_replan:
        replan_count = state.get("replan_count", 0) + 1
        family = families[(replan_count - 1) % num_families]
        family_queries = [q for q in grouped[family] if q not in already_tried]
        if not family_queries:
            log.info(f"Phase3 planner REPLAN #{replan_count}: no untried queries left in '{family}' — nothing new to add")
            return {"queries": list(already_tried), "replan_count": replan_count}
        picked = get_next_queries_for_family(family, family_queries, 1)
        log.info(f"Phase3 planner REPLAN #{replan_count}: added 1 query from '{family}': {picked}")
        return {"queries": list(already_tried) + picked, "replan_count": replan_count}

    base_per_family = MAX_SEARCHES // num_families
    remainder = MAX_SEARCHES % num_families

    chosen = []
    for i, family in enumerate(families):
        count = base_per_family + (1 if i < remainder else 0)
        if count == 0:
            continue
        family_queries = grouped[family]
        picked = get_next_queries_for_family(family, family_queries, count)
        chosen.extend(picked)
        log.info(f"Phase3 planner: picked {len(picked)} from '{family}' (pool size {len(family_queries)}): {picked}")

    log.info(f"Phase3 planner selected {len(chosen)} queries total across {num_families} families: {chosen}")
    return {"queries": chosen}