"""
What a timer shows: the abyssal countdown or the incursion stopwatch, read from
how long it has run. Shared by the full timer and the pocket overlay.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ClockFace:
    text: str  # 'MM:SS'
    state: str  # 'ready', 'running', 'paused' or 'expired'
    urgency: str  # 'normal', 'warning' or 'critical'
    share_left: float | None  # share of the countdown left, None for a stopwatch


def read_clock(countdown, elapsed, running):
    """
    The face of a timer.

    Args:
        countdown (float | None): Length of the countdown in seconds, or None for a stopwatch.
        elapsed (float): Seconds the timer has run.
        running (bool): Whether it is running now.

    Returns:
        ClockFace
    """
    state = "running" if running else "paused" if elapsed > 0 else "ready"
    if countdown is None:
        mins, secs = divmod(int(elapsed), 60)
        return ClockFace(f"{mins:02d}:{secs:02d}", state, "normal", None)

    seconds = max(0.0, countdown - elapsed)
    mins, secs = divmod(int(seconds + 0.999), 60)  # show 00:01 until the last second is gone
    if seconds <= 0:
        state = "expired"
    urgency = "critical" if seconds < 120 else "warning" if seconds < 300 else "normal"
    return ClockFace(f"{mins:02d}:{secs:02d}", state, urgency, seconds / countdown)
