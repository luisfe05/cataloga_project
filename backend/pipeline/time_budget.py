"""Time limits for reading one file, shared by every step and AI call.

Each file gets a budget. Its work runs in its own thread, and the caller
stops waiting when the time is up. The thread may stay stuck in a call
that cannot be interrupted, but it can no longer write anything: writing
needs commit(), and only one side, the thread or the caller, can win.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Everything for one file: reading, every AI call, every retry.
FILE_SECONDS = 120
# One AI call. A whole file took 3 s (median) and 12 s (slowest) in real use.
CALL_SECONDS = 60
# A retry with less time than this left has no chance of finishing.
MIN_RETRY_SECONDS = 10
# Retries inside the provider's own library, per call.
CLIENT_RETRIES = 1

# Each thread sees only its own budget.
local = threading.local()


class TimedOut(Exception):
    """A file used up its time. The message says in which step."""


class Budget:
    """The time left for one file, and who may still write its result."""

    def __init__(self, seconds):
        """Start counting now."""
        self.seconds = seconds
        self.deadline = time.monotonic() + seconds
        self.step = "start"
        self.lock = threading.Lock()
        # open, then committed (the thread writes) or abandoned (the caller).
        self.state = "open"

    def remaining(self):
        """Return the seconds left."""
        return self.deadline - time.monotonic()

    def commit(self):
        """Claim the right to write. False if the caller gave up already."""
        with self.lock:
            if self.state == "abandoned":
                return False
            self.state = "committed"
            return True

    def abandon(self):
        """Give up on the thread. False if it is already writing."""
        with self.lock:
            if self.state == "committed":
                return False
            self.state = "abandoned"
            return True


def current():
    """Return this thread's budget, or None outside a limited run."""
    return getattr(local, "budget", None)


def call_seconds():
    """Return how long the next AI call may take."""
    budget = current()
    if budget is None:
        return CALL_SECONDS
    return max(1, min(CALL_SECONDS, budget.remaining()))


def can_retry():
    """Say whether there is time for one more AI call."""
    budget = current()
    return budget is None or budget.remaining() >= MIN_RETRY_SECONDS


def check():
    """Raise TimedOut if this file's time is over."""
    budget = current()
    if budget is None or budget.state == "committed":
        return
    if budget.state == "abandoned" or budget.remaining() <= 0:
        raise TimedOut(budget.step)


def commit():
    """Call right before the first write. Raise TimedOut if it is too late."""
    budget = current()
    if budget is not None and not budget.commit():
        raise TimedOut(budget.step)


def timed(step, function, *args, **kwargs):
    """Run one step of reading a file and log how long it took."""
    check()
    budget = current()
    if budget is not None:
        budget.step = step
    started = time.monotonic()
    try:
        return function(*args, **kwargs)
    finally:
        logger.info("  %s %.1fs", step, time.monotonic() - started)


def run_limited(work, seconds=None):
    """Run work() in a thread and return its result, or raise TimedOut."""
    budget = Budget(FILE_SECONDS if seconds is None else seconds)
    outcome = {}

    def runner():
        """Do the work with this budget; keep the result or the error."""
        local.budget = budget
        try:
            outcome["result"] = work()
        except Exception as error:
            outcome["error"] = error

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(budget.seconds)
    if thread.is_alive() and budget.abandon():
        raise TimedOut(budget.step)
    # Already writing: a write is not cut in half.
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")
