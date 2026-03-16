from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import KeywordRules, Settings
from .pipeline import run_once


def run_scheduler(settings: Settings, rules: KeywordRules) -> None:
    scheduler = BlockingScheduler(timezone=settings.schedule.timezone)

    def _job() -> None:
        result = run_once(settings, rules)
        print(
            f"[scheduled] run_id={result.run_id} fetched={result.fetched} "
            f"matched={result.matched} channels={','.join(result.notified_channels)}"
        )

    scheduler.add_job(
        _job,
        trigger="cron",
        hour=settings.schedule.hour,
        minute=settings.schedule.minute,
        id="arxiv-daily-job",
        replace_existing=True,
    )

    print(
        "scheduler started: "
        f"timezone={settings.schedule.timezone} at {settings.schedule.hour:02d}:{settings.schedule.minute:02d}"
    )
    scheduler.start()
