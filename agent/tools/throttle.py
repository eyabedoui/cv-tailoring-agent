"""
Per-site request throttle for live web calls.

Tracks the last request time per host and sleeps if the minimum gap has
not elapsed. Only call throttle() in WEB_MODE=live paths.
"""
import time

from agent.config import SITE_THROTTLE_SECONDS

# Maps host → last-call monotonic timestamp.
_last_call: dict[str, float] = {}

# Injectable clock — replace in tests to avoid real sleeps.
_clock = time.monotonic


def throttle(host: str, seconds: float | None = None) -> None:
    """
    Block until *seconds* have elapsed since the last call for *host*.

    Uses SITE_THROTTLE_SECONDS when *seconds* is None.
    First call to a given host never blocks.
    """
    gap = seconds if seconds is not None else SITE_THROTTLE_SECONDS
    now = _clock()
    last = _last_call.get(host)  # None on first call → no sleep
    if last is not None:
        wait = gap - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_call[host] = _clock()


def _reset() -> None:
    """Clear all throttle state. For tests only."""
    _last_call.clear()
