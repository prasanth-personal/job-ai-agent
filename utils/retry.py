import time
import re
from utils.logger import get_logger
from db.api_usage import can_make_request

log = get_logger()


def call_llm_with_retry(llm, prompt, max_retries=3, estimated_tokens=1500):
    # Check the budget BEFORE spending a real call on it.
    ok, reason = can_make_request(estimated_tokens)
    if not ok:
        log.error(f"Blocked before call — {reason}")
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