"""Per-process admission bound, including work still running after a timeout."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore


class AgentCapacityError(RuntimeError):
    pass


class BoundedAgentExecutor:
    def __init__(self, max_workers=8, max_pending=16):
        if max_workers < 1 or max_pending < max_workers:
            raise ValueError("capacity must include all workers")
        self._slots = BoundedSemaphore(max_pending)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="medguard-agent")

    def submit(self, operation):
        if not self._slots.acquire(blocking=False):
            raise AgentCapacityError("agent_capacity_exhausted")
        try:
            future = self._executor.submit(operation)
        except BaseException:
            self._slots.release()
            raise
        # Caller timeout cannot release a running provider's capacity early.
        future.add_done_callback(lambda _: self._slots.release())
        return future

    def shutdown(self, **kwargs):
        self._executor.shutdown(**kwargs)
