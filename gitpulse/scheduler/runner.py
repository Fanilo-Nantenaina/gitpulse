from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from ..core.dateparse import parse_interval


class _Scheduler(Protocol):
    """The slice of APScheduler's BlockingScheduler GitPulse depends on.

    APScheduler ships no type information, so binding the instance to this
    Protocol is what gives the two call sites below a checked signature.
    """

    def add_job(
        self,
        func: Callable[[], None],
        trigger: str,
        *,
        seconds: float,
        next_run_time: datetime,
    ) -> object: ...

    def start(self) -> None: ...


def _blocking_scheduler() -> _Scheduler:
    # APScheduler is an optional extra and ships no stubs of its own; the
    # _Scheduler Protocol above is what types the two methods we call.
    from apscheduler.schedulers.blocking import (  # pyright: ignore[reportMissingTypeStubs]
        BlockingScheduler,
    )

    return BlockingScheduler(timezone="UTC")


def run_scheduler(job: Callable[[], None], every: str) -> None:
    delta = parse_interval(every)
    sched = _blocking_scheduler()
    sched.add_job(
        job,
        "interval",
        seconds=delta.total_seconds(),
        next_run_time=datetime.now(timezone.utc),
    )
    sched.start()


def systemd_timer_unit(interval: str, command: str) -> tuple[str, str]:
    service = f"""[Unit]
Description=GitPulse digest

[Service]
Type=oneshot
ExecStart={command}
"""
    timer = f"""[Unit]
Description=GitPulse digest timer

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval}
Persistent=true

[Install]
WantedBy=timers.target
"""
    return service, timer
