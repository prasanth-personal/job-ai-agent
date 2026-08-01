from config.settings import MAX_SEARCHES
from db.query_rotation import get_next_queries_for_family
from db.expanded_queries import get_queries_grouped_by_family
from graph.phase3.state import TopLevelState
from utils.logger import get_logger

log = get_logger()


def planner_node(state: TopLevelState) -> dict:
    """Top-level planner — deterministic round-robin, but now split
    EVENLY ACROSS ROLE FAMILIES (Salesforce, GenAI Engineer, etc.)
    instead of one flat pool. This guarantees both tracks get searched
    most runs, instead of one family dominating by chance the way a
    single shared cursor allowed.

    MAX_SEARCHES is distributed as evenly as possible across families —
    e.g. MAX_SEARCHES=2 with 2 families = 1 query per family. Any
    remainder (if MAX_SEARCHES doesn't divide evenly) goes to the
    families earliest in the dict, in order."""
    grouped = get_queries_grouped_by_family()
    families = list(grouped.keys())
    num_families = len(families)

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