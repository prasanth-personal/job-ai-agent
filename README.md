# Job Search AI Agent

A multi-agent AI system that autonomously discovers, evaluates, and reports on job opportunities matched against a candidate's real resume — built as a production-grade portfolio project demonstrating applied agentic AI engineering.

## 1. Problem Statement

Job searching at a senior/specialist level is inefficient in three specific ways:

- **Discovery is manual and repetitive.** Searching multiple job boards daily for the same set of role variations is time-consuming and easy to neglect.
- **Relevance is hard to judge at scale.** A human can't read 50+ full job descriptions a day and accurately judge fit against their own resume, especially across ambiguous or non-standard titles.
- **Market signal is invisible.** Candidates rarely have a systematic, evidence-based view of which specific skills are actually being requested across current job postings for their target roles — most "what should I learn next" decisions are guesswork.

This project addresses all three with one system: it searches, it judges fit against a real resume using an LLM, and it aggregates the evidence into a concrete skill-gap report — while tracking applications so nothing is duplicated or lost.

## 2. Business Case

| Without this system | With this system |
|---|---|
| Manually search 5-7 job boards/queries daily | One scheduled run covers multiple sources and target roles |
| Read full job descriptions to judge fit | LLM-scored match level, matched/missing skills, per job |
| No memory of what's already been seen or applied to | Persistent, deduplicated history across every run — exact-match AND semantic (embedding-based) |
| Generic "learn Python" type advice | Skill gaps derived from real, current job postings, with concrete first steps |
| No visibility into application status | A single tracked, exportable, always-current pipeline |
| A crash mid-run means starting over from scratch | Checkpointed — resumes from the last completed stage, no wasted API calls |
| Same query re-run blindly, whether or not it ever worked | Query selection is weighted toward queries with a proven track record of High matches |
| One plan, run blind to what happens mid-run | Planner re-consults mid-run if a query dead-ends or over-performs, within a bounded cap |
| Resume matching is a fixed, truncated blob for every job | Retrieval-augmented: only the resume sections relevant to this job are used per prompt |

The system is designed to be genuinely used daily, not a demo — every design decision (persistence, deduplication, crash isolation, cost control, observability, adaptivity) reflects that.

## 3. Architecture

![Architecture Diagram](./docs/job_agent_architecture.png)

A top-level planner coordinates three independent, specialized sub-agents. Each sub-agent is a fully self-contained LangGraph graph with its own internal state and reasoning, built and verified in isolation before being wired together.

Design principle throughout: state is explicitly translated at each agent boundary, not shared as one global object. Each agent receives only what it needs and returns only its result — the outer graph has no visibility into how, for example, Search Agent internally decided it had "enough" results.

The top-level graph itself is resumable: after every stage (planner → search → resume → skill → recommend), progress is checkpointed to Postgres. If the process crashes or is killed mid-run, the next invocation picks up at the next incomplete stage instead of re-running everything — including re-spending search API calls and LLM tokens that already succeeded.

**Reactive replanning.** The graph is not a strict straight line — it includes two conditional loop-backs to the planner, bounded by a hard cap (`MAX_REPLANS`, currently 2 total across both triggers) so it can never loop indefinitely:

- **After Search:** if a query returns zero new jobs, the planner is re-invoked to pick one different, untried query from the pool rather than letting the rest of the pipeline run on nothing.
- **After Resume:** if an unusually high proportion of scored jobs come back as High matches (≥ configurable threshold), the planner is re-invoked to search further in that direction, since the current queries appear to be hitting a strong seam.

Each replan pass adds exactly one new query, excludes anything already tried this run, and accumulates results (jobs, scored jobs) rather than overwriting them — verified via forced-trigger testing to confirm both loop-backs route correctly, respect the replan cap, and never re-select an already-searched query.

## 4. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Orchestration | LangGraph | Multi-agent graph definition, state management, conditional routing (including reactive replan loops), checkpointed resumability |
| LLM tooling | LangChain, langchain-groq | Tool-calling, prompt templating, LLM client abstraction |
| LLM inference | Groq (Llama 3.3 70B) | Resume-job matching, resume tailoring, skill research, query planning |
| Embeddings | Gemini Developer API (gemini-embedding-001) | Semantic dedup and resume-chunk retrieval |
| Job data | JSearch API (RapidAPI), Adzuna API | Two independent job search sources, with monthly-quota tracking against each |
| Persistence | PostgreSQL (AWS RDS) | Scored jobs, application tracking, API usage history, checkpoints, embeddings, query performance |
| Observability | LangSmith | Full trace of every graph run — per-node timing, token usage, and cost |
| Data export | pandas, openpyxl | Excel report generation |
| Notification | Gmail SMTP | Daily automated report delivery |
| Language | Python 3.11+ | — |

## 5. AI Engineering Concepts Applied

Each capability below exists because of a specific problem a naive single-agent implementation would have had.

| Problem | Why a naive approach fails | Solution applied |
|---|---|---|
| One agent trying to search, score, and research skills at once becomes an unmanageable god-object as complexity grows | A single monolithic prompt/loop has no clean boundaries — debugging or improving one capability risks breaking the others | **Multi-agent orchestration** — independent sub-agents (Search, Resume, Skill) with their own state, composed via a top-level graph |
| The LLM needs to search job boards and score listings, not just talk about them | A chat-only LLM can describe what it would search for, but can't actually execute a real API call | **Tool calling** — `@tool`-decorated functions (`search_jobs`, `search_jobs_adzuna`, `score_job`) the LLM invokes with self-generated arguments |
| An agent deciding for itself "keep searching until satisfied" can loop indefinitely or burn unbounded API calls | LLM judgment about "enough results" isn't a reliable stopping condition on its own | **Agentic loop with a hard guardrail** — Search Agent's retry loop is capped at a fixed attempt limit regardless of what the LLM thinks |
| Planning happens once, upfront — the pipeline runs blind afterward even if a query dead-ends or over-performs | A single static plan can't react to what actually happens mid-run, wasting the rest of the run on a bad early decision | **Reactive replanning with bounded loop-backs** — the graph conditionally routes back to the planner after Search (on zero results) or after Resume (on a high-yield streak), capped by a hard replan counter to prevent runaway loops |
| Given no real results, an LLM asked to "summarize the best matches" will confidently invent plausible-sounding fake job listings | LLMs pattern-match to "what a good summary looks like," with or without real grounding data | **Grounded generation** — the Recommendation step is fed real scored data directly in its prompt, structurally preventing fabrication rather than just instructing the model not to |
| Nothing stops the LLM from scoring or emailing a job that was never actually returned by a real search | Tool-calling LLMs can reference plausible-looking arguments that don't correspond to anything real | **Fabrication guard** — every job the LLM attempts to score is checked against a registry of jobs a real search call actually returned this session; anything else is rejected and logged |
| The same fixed, truncated resume excerpt was used for every job — an AI-engineering role and a Salesforce-admin role got identical resume context, and anything past the first ~2000 characters was invisible to every score, forever | A single hardcoded truncation can't be relevant to every job at once, and silently drops real information | **Resume-chunk RAG** — the resume is split into chunks, embedded, and only the top-k chunks most relevant to that specific job's description are retrieved per prompt |
| The same job reposted with a slightly reworded title (a staffing agency repost, a "Sr." vs "Senior" variant) was treated as a brand-new listing and rescored from scratch | Exact string-key matching only catches identical titles, not paraphrases | **Semantic deduplication** — job listings are deduplicated on embedding similarity, catching reworded near-duplicates a naive key comparison misses |
| The planner picked search queries in pure round-robin order, with zero memory of which queries actually produced good matches versus wasted API calls | A fixed rotation treats a query that's found 5 High matches identically to one that's found none | **Adaptive, outcome-aware query selection** — each query's historical High-match rate is tracked and weighted into future selection, with a floor so every query still gets occasional exploration |
| A crash partway through a run (API failure, network drop) meant re-running the entire pipeline from scratch the next time — re-spending search calls and LLM tokens that had already succeeded | No persisted progress between pipeline stages | **Checkpointed resumability** — full pipeline state is saved to Postgres after every stage; a crash resumes at the next incomplete stage instead of starting over |
| Free-tier LLM usage (30 RPM / 1K RPD / 12K TPM / 100K TPD on Groq) is easy to blow through with unthrottled testing, and a 429 error only tells you after it's already failed | Reactive error-handling alone means discovering the problem only once it's already occurred | **Proactive budget guarding** — real per-call token usage is recorded and checked against all four limits with a safety margin before the next call fires |
| Search-API quotas (JSearch, Adzuna) were being consumed with zero visibility into how close to the monthly cap the account actually was | Silent consumption means a sudden failure is the first sign of a problem | **Search-API usage tracking** — every real network call is counted and surfaced against its monthly limit in every run's summary |
| With no view into what a multi-agent run was actually doing, debugging or explaining the system's behavior meant re-reading logs line by line | Plain logging shows that something happened, not the full nested structure of why, with timing and cost attached | **Observability (LangSmith)** — every graph run and underlying LLM call is traced end-to-end: per-node timing, token usage, and real dollar cost, with no code changes beyond configuration |
| A prompt engineered once and left as an inline string scattered through the codebase is hard to test, version, or reuse consistently | Freeform prompt strings buried in logic make prompts hard to audit or improve independently of the code around them | **Prompt engineering** — structured, constrained prompts (explicit JSON schema requests, "reply ONLY with..." patterns) isolated into a dedicated prompts module |
| Re-scoring a job already scored in a previous run wastes both LLM tokens and money for a result that won't change | Nothing about a job's fit changes between runs unless the resume itself changes | **Caching for cost control** — previously-scored jobs are never re-sent to the LLM; resume-chunk embeddings are only recomputed when the resume file's content actually changes |
| Applying expensive operations (resume tailoring, skill research) to every single result scales cost with result volume, not with actual value | Not every scored job is worth the extra LLM spend | **Cost-bounded expensive operations** — tailoring and research are restricted to only the highest-value subset (High matches, top-N gaps) |
| A single Groq rate-limit response doesn't tell you whether retrying will help or is guaranteed to fail again | Treating all rate-limit errors the same wastes time retrying an unrecoverable daily cap | **Rate-limit-aware resilience** — retry logic distinguishes recoverable (short, per-minute) delays from unrecoverable (long, daily-cap) ones and fails fast on the latter |

## 6. Problems Encountered During Development (and Resolutions)

| Problem | Root Cause | Resolution |
|---|---|---|
| LLM invented plausible-sounding fake job listings when given no real results to summarize | LLMs pattern-match to "what a summary looks like" even with no grounding data | Fabrication guard: reject and log any scored job not present in that session's real search results |
| Credibility filter rejected legitimate job sources (e.g. Adzuna's own redirect domain, Shine, Foundit) | Trusted-domain list was incomplete relative to actual sources in use | Expanded and audited the trusted-board list against real observed domains |
| Every log line printed multiple times | `logging.getLogger(name)` returns a shared singleton; handlers were re-added on every import across multiple modules | Added a guard (`if not logger.handlers:`) so handlers are only configured once |
| Tool responses of `[]` were rejected by the LLM provider | Groq's API requires non-empty content for any tool-role message | Search tools return an informational placeholder instead of an empty list when nothing new is found |
| `StructuredTool` object is not callable | `@tool`-decorated functions must be invoked via `.invoke({...})`, not called directly | Standardized all tool call sites to use `.invoke()` |
| Frequent 429 rate-limit errors under heavy same-day testing | Free-tier Groq limits (30 RPM / 1K RPD / 12K TPM / 100K TPD for Llama 3.3 70B) are easily exhausted with unthrottled, repeated testing | Built a proactive usage tracker with a pre-call budget guard, using a 90% safety margin against all four limit types |
| A single job's scoring failure or a single query's total failure could abort an entire run | No isolation between units of work | Per-job and per-query try/except boundaries; a failure is logged and the run continues |
| Excel export silently showed empty apply links | `apply_link` was an optional tool parameter the LLM sometimes omitted | Made `apply_link` a required parameter, removing the LLM's ability to skip it |
| Embedding calls failed with a Vertex AI billing error (`BILLING_DISABLED`) despite intending to use a free-tier API key | The embedding implementation used the `vertexai` SDK with service-account credentials — a genuinely different product (Vertex AI, GCP-billed, no free tier) from the Gemini Developer API (AI Studio, API-key auth, real free tier) that was actually intended | Rewrote the embedding call as a plain authenticated REST request to `generativelanguage.googleapis.com` (AI Studio), removing all Vertex/service-account code entirely |
| Duplicate `@tool` decorator and duplicate `save_score(...)` call caused a `ValueError` at import time | A pasted code edit landed above the existing line instead of replacing it | Removed the duplicated lines; adopted a stricter search-and-replace habit for subsequent edits |
| No way to tell, from the log alone, whether a skipped job was an exact repeat or a genuine fuzzy-title catch | Both cases returned `True` from the same function, but only one branch logged anything | Added a log line to the silent (exact-key) branch so both outcomes are distinguishable in the log |
| A crash partway through a run wasted every search/LLM call made before the crash | No persisted progress between pipeline stages | Postgres-backed checkpointing after each stage; the graph's entry point is conditionally routed to resume at the correct stage |
| Search Agent's `found_jobs` state was silently overwritten rather than merged when the graph looped back through search a second time | LangGraph doesn't auto-merge dict/list state values across repeated node execution unless the node explicitly merges them | `search_node` now tracks already-searched queries separately and appends only newly found, deduplicated jobs to the accumulated list on every pass, including replanned ones |
| A `.env` file containing real credentials was committed to git history | Missing from `.gitignore` from the start | Untracked with `git rm --cached`, added to `.gitignore`, verified removal from history, rotated all exposed credentials |

## 7. Rate Limit & Token Management

Groq's free-tier limits for the model in use (Llama 3.3 70B Versatile):

| Limit type | Value |
|---|---|
| Requests per minute (RPM) | 30 |
| Requests per day (RPD) | 1,000 |
| Tokens per minute (TPM) | 12,000 |
| Tokens per day (TPD) | 100,000 |

External job-data APIs are also tracked against their own free-tier quotas (JSearch/RapidAPI, Adzuna), with real call counts recorded on every network request and surfaced in each run's summary email — not just Groq.

Measures taken:

- Every LLM response's real token usage (`response_metadata['token_usage']`) is recorded immediately after each call — actual usage, not estimates.
- Before every LLM call, a guard checks the last-60-seconds and today's totals against all four Groq limits with a 90% safety margin, and refuses the call proactively if it would breach that margin.
- Retry logic distinguishes recoverable delays (Groq reports a short wait, e.g. seconds) from unrecoverable ones (a long suggested wait indicates a daily cap, which retrying cannot fix) and fails fast in the latter case rather than burning time on retries that cannot succeed.
- Expensive operations (resume tailoring, skill research) are deliberately scoped to only the highest-value subset of results, not applied to every item, keeping per-run token cost proportional to output value.
- Every search-API call (JSearch, Adzuna) is counted against its own monthly free-tier limit, so quota exhaustion is visible ahead of time rather than discovered as a sudden failure.
- Reactive replanning is capped (`MAX_REPLANS`, currently 2) specifically to bound the additional API/LLM spend that mid-run looping could otherwise introduce.

## 8. Setup

```bash
pip install -r requirements.txt
```

Create `.env`:

```
RAPIDAPI_KEY=...
GROQ_API_KEY=...
GEMINI_API_KEY=...
GMAIL_FROM=...
GMAIL_APP_PASSWORD=...
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
PGHOST=...
PGPORT=5432
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=job-ai-agent
```

`GEMINI_API_KEY` comes from Google AI Studio (aistudio.google.com), not the GCP/Cloud Console — this is the Gemini Developer API, which has a genuine free tier, as distinct from Vertex AI (GCP-billed, no free tier).

Add resume text to `my_resume.txt`, set target roles in `config/settings.py` (`SEARCH_QUERIES`), then:

```bash
python main.py
```

Mark an application:

```bash
python mark_applied.py "Employer Name" "Job Title" [apply_link]
```

## 9. Repository Structure

```
job-ai-agent/
├── main.py                   # Entry point — orchestration, checkpoint resume logic
├── mark_applied.py           # CLI utility
├── config/                   # Settings, prompts, target queries
├── db/                       # Persistence: scored jobs, applications, API usage,
│                              # checkpoints, embeddings, query performance, resume chunks
├── tools/                    # Search (JSearch, Adzuna) and scoring tools
├── graph/phase3/             # Multi-agent graph: planner + 3 sub-agents + replan routing
├── utils/                    # Retry logic, logging
├── reports/                  # Excel and summary generation
├── notifications/            # Email delivery
└── tests/                    # Module-level smoke tests
```

## 10. Current Limitations & Roadmap

Known limitation: the checkpoint-resume logic resumes a crashed run at a fixed next stage based on the last completed stage name — it doesn't know it was mid-replan-loop when it crashed. In practice this is still safe (all accumulated state — `found_jobs`, `searched_queries`, `replan_count` — is preserved correctly in the checkpoint), but a resumed run won't re-evaluate "should I have replanned here" the way a live run would. Minor edge case, not a correctness bug.

Near-term:

- Human-in-the-loop approval step before emailing High matches (currently fully automated)
- Scoping semantic dedup comparisons to same-employer only, to reduce any risk of cross-employer false positives
- Query-history awareness across days to avoid re-selecting recently-exhausted queries, beyond the current within-run exclusion

**Done since the last version of this document:** cloud deployment (AWS RDS Postgres), observability/tracing (LangSmith), retrieval-augmented generation (resume-chunk RAG), semantic deduplication, adaptive query selection, checkpointed resumability, and **reactive mid-run replanning** — the planner now re-engages after Search (on zero results) or after Resume (on a high-yield streak), bounded by a hard replan cap, closing the "plan once, execute blind" gap noted in earlier versions of this document.

---

Built as a hands-on demonstration of applied agentic AI engineering: orchestration, tool use, cost-aware LLM operation, retrieval-augmented generation, observability, adaptive and reactive planning, and — deliberately — active, tested defenses against an LLM's own unreliability, not only its capability.