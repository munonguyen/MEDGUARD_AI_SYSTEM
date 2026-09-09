"""Run the OCR worker loop with graceful shutdown and stale-claim recovery."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path
from threading import Event
from time import monotonic, sleep

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.core.queue import job_queue
from app.workers.ocr_worker import process_next_ocr_job


def run_worker(
    *,
    once: bool,
    visibility_timeout_seconds: float,
    reclaim_interval_seconds: float,
    idle_sleep_seconds: float,
) -> int:
    if settings.environment.lower() == "production" and not job_queue.is_healthy:
        print("A healthy Redis queue is required for the production worker", file=sys.stderr)
        return 2

    stop = Event()

    def request_shutdown(signum, frame) -> None:
        del signum, frame
        stop.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    last_reclaim = 0.0

    while not stop.is_set():
        now = monotonic()
        if now - last_reclaim >= reclaim_interval_seconds:
            reclaimed = job_queue.reclaim_stale(visibility_timeout_seconds)
            if reclaimed:
                print(f"reclaimed_stale_jobs={reclaimed}")
            last_reclaim = now

        processed_job_id = process_next_ocr_job(timeout_seconds=0.5)
        if processed_job_id:
            print(f"processed_job_id={processed_job_id}")
        elif idle_sleep_seconds:
            sleep(idle_sleep_seconds)
        if once:
            break
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--visibility-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--reclaim-interval-seconds", type=float, default=30.0)
    parser.add_argument("--idle-sleep-seconds", type=float, default=0.25)
    args = parser.parse_args()
    if min(
        args.visibility_timeout_seconds,
        args.reclaim_interval_seconds,
        args.idle_sleep_seconds,
    ) < 0:
        parser.error("worker timing values cannot be negative")
    if args.visibility_timeout_seconds == 0 or args.reclaim_interval_seconds == 0:
        parser.error("visibility and reclaim intervals must be greater than zero")
    return run_worker(
        once=args.once,
        visibility_timeout_seconds=args.visibility_timeout_seconds,
        reclaim_interval_seconds=args.reclaim_interval_seconds,
        idle_sleep_seconds=args.idle_sleep_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
