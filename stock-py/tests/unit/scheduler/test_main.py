from __future__ import annotations

import unittest

from apps.scheduler.main import build_scheduler


class SchedulerMainTest(unittest.TestCase):
    def test_build_scheduler_registers_orchestration_jobs(self) -> None:
        scheduler = build_scheduler()

        job_ids = {job.id for job in scheduler.get_jobs()}

        self.assertSetEqual(
            job_ids,
            {
                "scheduler-heartbeat",
                "event-relay",
                "event-dispatch",
                "tradingagents-poll",
                "market-data-refresh",
                "scanner-refresh",
                "retention-maintenance",
                "receipt-escalation",
                "push-dispatch",
                "email-dispatch",
                "backtest-refresh",
                "cold-storage-archive",
            },
        )