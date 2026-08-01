import time
import re
from utils.logger import get_logger
from db.api_usage import can_make_request

log = get_logger()

def call_llm_with_retry(llm, prompt, max_retries=3, estimated_tokens=1500):
    # Check the budget BEFORE spending a real call on it. If blocked by a
    # per-MINUTE limit (RPM/TPM), wait for the trailing-60s window to roll
    # over and retry — instead of giving up immediately and losing the job
    # entirely, which is what was happening before. Per-DAY limits (RPD/TPD)
    # can't be waited out within a single run, so those still fail fast.
    budget_wait_seconds = 20
    max_budget_retries = 3
    ok, reason = can_make_request(estimated_tokens)
    budget_attempt = 0
    while not ok and budget_attempt < max_budget_retries:
        if "today" in reason:
            log.error(f"Blocked before call — {reason}")
            raise RuntimeError(f"API usage guard: {reason}")
        budget_attempt += 1
        log.warning(f"Blocked before call — {reason} — waiting {budget_wait_seconds}s for window to roll over (attempt {budget_attempt}/{max_budget_retries})")
        time.sleep(budget_wait_seconds)
        ok, reason = can_make_request(estimated_tokens)

    if not ok:
        log.error(f"Still blocked after {max_budget_retries} waits — {reason}")
        raise RuntimeError(f"API usage guard: {reason}")

    for attempt in range(max_retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            error_text = str(e)
            if "rate_limit" in error_text or "429" in error_text:
                wait_seconds = 15
                match = re.search(r"try again in ([\d.]+)s", error_text)
                if match:
                    wait_seconds = float(match.group(1)) + 1
                if wait_seconds > 60:
                    raise RuntimeError(f"Daily/long-term rate limit hit (suggested wait: {wait_seconds}s) — stopping retries")
                log.warning(f"Rate limited — waiting {wait_seconds:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_seconds)
            else:
                raise
    raise RuntimeError(f"Gave up after {max_retries} retries due to rate limiting")