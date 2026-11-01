import os, time, logging
import litellm
from dotenv import load_dotenv

load_dotenv()
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)


class QuotaExhausted(Exception):
    pass


_streak = 0


def call(prompt, gap=4.5, model=None):
    """Return text, or None after repeated other errors.
    Raises QuotaExhausted after 3 rate limits in a row."""
    global _streak
    if not model:
        model = os.environ.get("VERITAS_MODEL", "gemini/gemini-3.5-flash-lite")
    for attempt in range(3):
        try:
            r = litellm.completion(
                model=model, api_key=os.environ["GEMINI_API_KEY"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0, timeout=60, num_retries=0)
            text = (r.choices[0].message.content or "").strip()
            if text:
                _streak = 0
                time.sleep(gap)
                return text
        except litellm.RateLimitError as e:
            _streak += 1
            print("  rate limit:", str(e).replace("\n", " ")[:200])
            if _streak >= 3:
                raise QuotaExhausted("3 rate limits in a row. Rerun after the quota resets.")
            time.sleep(60)
        except Exception as e:
            print("  llm error:", type(e).__name__)
            time.sleep(10)
    return None