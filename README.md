# Job Search AI Agent

An autonomous, LangGraph-based agent that searches multiple job boards, scores postings against your resume using an LLM, tracks applications, flags real skill gaps from live market data, and emails you a daily report — built as a real production system, not a tutorial project.

## Why this exists

Most "AI job search" projects are thin wrappers around a single API call. This one is designed to actually be used daily, and to double as a learning vehicle for agentic AI engineering (LangChain, LangGraph, tool-calling, guardrails, persistence) — not a toy demo, a working tool with the reliability concerns a real system needs.

## What it does

1. **Searches** two independent job sources (JSearch via RapidAPI, Adzuna) across a configurable list of target roles
2. **Filters** out spam listings and untrustworthy apply links before anything reaches the LLM
3. **Scores** each remaining job against your actual resume text using an LLM, returning a match level (High/Medium/Low), score, matched skills, and missing skills
4. **Refuses to trust its own LLM blindly** — a fabrication guard rejects any job the model tries to score that wasn't actually returned by a real search call, preventing hallucinated jobs from ever being saved
5. **Persists everything** to SQLite — scored jobs, application status, and daily API usage — so nothing gets rescored or re-applied-to twice
6. **Tracks applications** — mark a job as applied, update its status (Interview/Rejected/Offer), and the exported report reflects it
7. **Aggregates skill gaps** across every job scored, giving real, evidence-based signal on what to learn next — not a generic roadmap
8. **Exports and emails** a daily report: an Excel sheet of all scored jobs (color-coded by match, with application status), a skill gap report, and the full run log, all in one email

## Architecture

Built as a single LangGraph agent with tool-calling, not a chain of hardcoded steps — the LLM decides when to search, when to score, and when to search again with broader terms if results are weak, bounded by a hard guardrail so it can never loop indefinitely or exhaust the API budget on its own.

```
job-ai-agent/
├── main.py                    # Orchestration only — no business logic
├── config/
│   ├── settings.py             # Env vars, constants, trusted/spam board lists
│   └── prompts.py              # LLM prompt templates, isolated from logic code
├── db/
│   ├── repository.py           # Scored-jobs persistence + caching
│   ├── applications.py         # Application status tracking
│   └── api_usage.py            # Real Groq token/request usage tracking + pre-call budget guard
├── tools/
│   ├── search.py                # JSearch tool + credibility filtering + fabrication-guard registry
│   ├── search_adzuna.py         # Adzuna tool (second, independent source, shares the same guards)
│   └── scorer.py                 # Resume-matching tool, with the fabrication guard enforced
├── graph/
│   ├── nodes.py                  # Agent decision node, routing logic, guardrail node
│   └── build.py                  # LangGraph assembly and compilation
├── utils/
│   ├── retry.py                  # Rate-limit-aware retry with fail-fast on unrecoverable limits
│   └── logger.py                 # Single, non-duplicated logging to console + rotating file
├── reports/
│   ├── summary.py                 # Database-grounded summary (never trusts the LLM's own chat output as fact)
│   ├── excel_export.py            # Full scored-jobs Excel export, joined with application status
│   └── skill_gap_export.py        # Skill gap Excel export
└── notifications/
    └── email_sender.py             # Daily email with all three reports attached
```

### Design decisions worth knowing

- **Fabrication guard**: the single most important safety mechanism in this system. LLMs will occasionally invent plausible-sounding jobs (fake companies, fake titles) when asked to summarize with no real results in hand. Every job passed to the scoring tool is checked against a registry of jobs a real search call actually returned in that session; anything else is rejected and logged, never saved.
- **Database as source of truth, not the LLM's chat message**: the final report is built by querying SQLite directly, not by trusting whatever the agent's last message says — this is what makes the fabrication guard actually matter end-to-end.
- **Credibility filtering happens before the LLM ever sees a job** — spam keywords and untrustworthy apply-link domains are filtered at the source, so no tokens are spent scoring junk.
- **Real API usage tracking with a pre-call guard**: every LLM call's actual token usage (from `response_metadata`) is recorded, and a budget check runs *before* each call using Groq's published rate limits (RPM/RPD/TPM/TPD), so the system can reason about its own remaining budget rather than just reacting to 429s after the fact.
- **Per-query crash isolation**: if one search query's entire run fails (rate limit exhaustion, malformed tool call, etc.), the failure is logged and the loop continues to the next query rather than losing all prior progress.

## Setup

1. Clone the repo, `cd` into the project root
2. `pip install -r requirements.txt` (langchain, langchain-groq, langgraph, requests, python-dotenv, pandas, openpyxl)
3. Create a `.env` file with:
   ```
   RAPIDAPI_KEY=...
   GROQ_API_KEY=...
   GMAIL_FROM=...
   GMAIL_APP_PASSWORD=...
   ADZUNA_APP_ID=...
   ADZUNA_APP_KEY=...
   ```
4. Add your resume as plain text to `my_resume.txt` in the project root
5. Edit `SEARCH_QUERIES` in `config/settings.py` to your actual target roles
6. `python main.py`

## Marking an application

```
python mark_applied.py "Employer Name" "Job Title" [apply_link]
```

## Current status: Phase 1 complete

- ✅ Dual-source search (JSearch + Adzuna) with shared credibility filtering
- ✅ Resume-based LLM scoring with a proven, tested fabrication guard
- ✅ Rate-limit resilience with fail-fast on unrecoverable (daily) limits
- ✅ Application tracking
- ✅ Real Groq API usage tracking with a pre-call budget guard
- ✅ Excel + skill gap export + email delivery, verified end-to-end
- ✅ Full multi-query run tested under real-world partial failures (rate limits, malformed tool calls) without crashing

## Roadmap

**Near-term**
- Windows Task Scheduler integration for genuinely unattended daily runs
- Smarter token estimation in the pre-call guard (based on actual conversation size, not a flat estimate)
- Evaluate switching the scoring model to a higher-daily-quota model for more headroom

**Phase 2 (planned)**
Break the single agent's decision loop into fixed graph stages — Planner → Search → Score → Skill Gap → Recommend — so only the steps that genuinely need LLM judgment (query planning, final summarization) use the LLM, cutting redundant token usage from re-sending full conversation history on every loop turn.

**Phase 3 (planned, longer-term)**
Decompose into genuinely separate sub-agents (Search Agent, Resume Agent, Skill Agent) coordinated by a top-level planner — real multi-agent orchestration, once Phase 2's single-graph pipeline is proven stable.

**Explicitly deferred**
LangSmith tracing/observability, cloud deployment (AWS EC2/RDS) — valuable, but treated as separate, deliberate learning projects rather than something to rush into the current build.

## Built with

Python, LangChain, LangGraph, Groq (Llama 3.3 70B), SQLite, pandas, JSearch API, Adzuna API, Gmail SMTP
