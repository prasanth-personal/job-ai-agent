from db.repository import init_db
from db.applications import init_applications_table
from db.api_usage import init_usage_table, get_usage_today, RPD_LIMIT, TPD_LIMIT
from graph.phase3.build import build_phase3_pipeline
from graph.phase3.state import initial_top_state, resume_top_state
from reports.summary import print_real_summary
from reports.excel_export import export_to_excel
from reports.skill_gap_export import export_skill_gaps
from notifications.email_sender import send_daily_report
from config.settings import SEARCH_QUERIES
from utils.logger import get_logger
from collections import Counter
from datetime import date
from db.query_rotation import init_query_rotation_table
from db.expanded_queries import init_expanded_queries_table, refresh_expanded_queries
from db.checkpoints import init_checkpoint_table, load_checkpoint, clear_checkpoint, next_stage
from db.embeddings import init_embeddings_table
from db.query_performance import init_query_performance_table
from db.resume_chunks import init_resume_chunks_table
from db.search_usage import init_search_usage_table, get_usage_summary

log = get_logger()


def main():
    init_db()
    init_applications_table()
    init_usage_table()
    init_query_rotation_table()
    init_expanded_queries_table()
    init_checkpoint_table()
    init_query_performance_table()
    init_resume_chunks_table()
    init_embeddings_table()
    refresh_expanded_queries()
    init_search_usage_table()
    

    today = date.today()
    checkpoint = load_checkpoint(today)

    if checkpoint:
        resume_stage = next_stage(checkpoint["stage"])
        log.info(f"Found incomplete run for {today} (last completed: {checkpoint['stage']}) — resuming at '{resume_stage}'")
        start_state = resume_top_state(checkpoint["state"], resume_stage)
    else:
        start_state = initial_top_state(SEARCH_QUERIES)

    pipeline = build_phase3_pipeline()

    log.info(f"Starting Phase 3 pipeline — {len(SEARCH_QUERIES)} queries configured, planner will pick one")

    try:
        result = pipeline.invoke(start_state)
        clear_checkpoint(today)
    except Exception as e:
        log.error(f"Phase 3 pipeline failed entirely: {e}")
        result = {"queries": [], "found_jobs": [], "scored_jobs": [], "skill_gaps": {}, "skill_research": {}, "final_summary": "Pipeline failed to complete."}

    log.info(f"Query used: {result['queries']}")
    log.info(f"Jobs found: {len(result['found_jobs'])}")
    log.info(f"Jobs scored: {len(result['scored_jobs'])}")

    print("\n--- SKILL GAP REPORT (this run) ---")
    if result["skill_gaps"]:
        for skill, count in sorted(result["skill_gaps"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {skill}: missing in {count} job(s)")
    else:
        print("  No missing skills recorded.")

    print("\n--- SKILL RESEARCH ---")
    for skill, note in result["skill_research"].items():
        print(f"\n{skill}:\n{note}")

    print("\n--- FINAL SUMMARY ---")
    print(result["final_summary"])

    print_real_summary()
    jobs_file = export_to_excel()
    skill_gap_file = export_skill_gaps(Counter(result["skill_gaps"]))

    usage_today = get_usage_today()
    search_usage = get_usage_summary()
    summary_text = (
        f"Job Search Agent run complete (Phase 3 — multi-agent).\n\n"
        f"Query used: {result['queries']}\n"
        f"Jobs found: {len(result['found_jobs'])}\n"
        f"Jobs scored: {len(result['scored_jobs'])}\n"
        f"Groq usage today: {usage_today['requests']} requests, {usage_today['tokens']} tokens "
        f"(limits: {RPD_LIMIT} req/day, {TPD_LIMIT} tokens/day)\n\n"
        f"JSearch usage this month: {search_usage['jsearch']['month']}/{search_usage['jsearch']['limit']}\n"
        f"Adzuna usage this month: {search_usage['adzuna']['month']}/{search_usage['adzuna']['limit']}\n\n"
        f"See attached: jobs_today.xlsx, skill_gap_report.xlsx, job_agent.log\n"
    )
    send_daily_report(
        summary_text,
        excel_path=jobs_file or f"jobs_report_{date.today().isoformat()}.xlsx",
        skill_gap_path=skill_gap_file or f"skill_gaps_{date.today().isoformat()}.xlsx",
    )


if __name__ == "__main__":
    main()