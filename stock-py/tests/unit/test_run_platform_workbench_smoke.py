from __future__ import annotations

import unittest

import run_platform_workbench_smoke as smoke


class RunPlatformWorkbenchSmokeTest(unittest.TestCase):
    def test_summarize_payload_handles_platform_endpoint_shapes(self) -> None:
        self.assertEqual(
            smoke.summarize_payload(
                "summary",
                {
                    "active_signals": 2,
                    "triggered_signals": 1,
                    "avg_confidence": 73.4,
                    "ignored": 99,
                },
            ),
            {
                "active_signals": 2,
                "triggered_signals": 1,
                "avg_confidence": 73.4,
            },
        )
        self.assertEqual(
            smoke.summarize_payload("signal_stats", {"data": [1, 2, 3]}),
            {"count": 3},
        )
        self.assertEqual(
            smoke.summarize_payload(
                "scanner",
                {
                    "recent_decisions": [1, 2],
                    "summary": {"total_decisions": 9, "emitted_decisions": 4},
                },
            ),
            {
                "recent_decisions": 2,
                "total_decisions": 9,
                "emitted_decisions": 4,
            },
        )
        self.assertEqual(smoke.summarize_payload("rankings", {"data": [1, 2]}), {"count": 2})
        self.assertEqual(smoke.summarize_payload("health", {"strategies": [1]}), {"count": 1})
        self.assertEqual(smoke.summarize_payload("runs", {"data": []}), {"count": 0})
        self.assertEqual(smoke.summarize_payload("analyses", {"data": [1, 2, 3, 4]}), {"count": 4})

    def test_summarize_text_markers_reports_missing_platform_markers(self) -> None:
        self.assertEqual(
            smoke.summarize_text_markers(
                ["Desktop Launchpad", "Execution Relay", "Research Relay"],
                "Desktop Launchpad\nExecution Relay\n",
            ),
            {
                "required": 3,
                "matched": 2,
                "missing": ["Research Relay"],
            },
        )

    def test_platform_text_checks_cover_html_and_workspace_scripts(self) -> None:
        check_names = {name for name, _, _ in smoke.PLATFORM_TEXT_CHECKS}
        self.assertEqual(
            check_names,
            {"platform_html", "workspace_script", "platform_script", "market_script"},
        )


if __name__ == "__main__":
    unittest.main()