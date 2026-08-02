import json
from db.connection import get_connection

STAGE_ORDER = ["planner", "search", "resume", "skill", "recommend"]


def next_stage(stage: str) -> str:
    idx = STAGE_ORDER.index(stage)
    return STAGE_ORDER[idx + 1] if idx + 1 < len(STAGE_ORDER) else "recommend"


def init_checkpoint_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
            run_date DATE PRIMARY KEY,
            stage TEXT,
            state TEXT,
            updated_at TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_checkpoint(run_date, stage: str, state: dict):
    """Persist progress after a pipeline stage completes, so a crash
    mid-run can resume from here instead of starting over."""
    clean_state = {k: v for k, v in state.items() if not k.startswith("_")}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pipeline_checkpoints (run_date, stage, state, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (run_date) DO UPDATE SET
            stage = EXCLUDED.stage,
            state = EXCLUDED.state,
            updated_at = EXCLUDED.updated_at
    """, (run_date, stage, json.dumps(clean_state)))
    conn.commit()
    cur.close()
    conn.close()


def load_checkpoint(run_date) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT stage, state FROM pipeline_checkpoints WHERE run_date = %s",
        (run_date,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return None
    stage, state_json = row
    return {"stage": stage, "state": json.loads(state_json)}


def clear_checkpoint(run_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pipeline_checkpoints WHERE run_date = %s", (run_date,))
    conn.commit()
    cur.close()
    conn.close()