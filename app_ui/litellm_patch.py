"""Strip the unsupported `cache_breakpoint` key from messages before LiteLLM sees them."""
import litellm


def apply() -> None:
    """Patch litellm.completion once. Call before project modules import litellm."""
    if getattr(litellm, "_cache_breakpoint_patched", False):
        return

    original = litellm.completion

    def patched(*args, **kwargs):
        for msg in kwargs.get("messages") or []:
            if isinstance(msg, dict):
                msg.pop("cache_breakpoint", None)
        return original(*args, **kwargs)

    litellm.completion = patched
    litellm._cache_breakpoint_patched = True
