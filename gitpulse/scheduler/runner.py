from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Callable


def parse_interval(s: str) -> timedelta:
    """Parse '7d', '24h', '30m' into a timedelta."""
    s = s.strip().lower()
    unit = s[-1]
    n = int(s[:-1])
    return {"d": timedelta(days=n), "h": timedelta(hours=n),
            "m": timedelta(minutes=n)}[unit]


def run_scheduler(job: Callable[[], None], every: str) -> None:
    """Run `job` every `every` interval. Blocks. Requires apscheduler."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    delta = parse_interval(every)
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(job, "interval", seconds=delta.total_seconds(),
                  next_run_time=datetime.now(timezone.utc))
    sched.start()


def systemd_timer_unit(interval: str, command: str) -> tuple[str, str]:
    """Return (service_unit, timer_unit) text for `gitpulse install-timer`."""
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
