import tempfile
import unittest
from pathlib import Path

from infra.core.report_artifacts import bootstrap_cutover_report, bootstrap_load_report


class ReportArtifactsTest(unittest.TestCase):
    def test_bootstrap_load_report_creates_prefilled_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "baseline-summary-template.md"
            template.write_text(
                "\n".join(
                    [
                        "- Environment:",
                        "- Release SHA:",
                        "- Run UTC timestamp:",
                        "- QA owner:",
                        "- Backend owner:",
                        "- Command:",
                        "- Scenario mix:",
                        "- Host:",
                        "- Users:",
                        "- Spawn rate:",
                        "- Duration:",
                        "- Disposable fixtures used:",
                        "- CSV path:",
                        "- HTML path:",
                        "- Dashboard / screenshots:",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            summary_path, created = bootstrap_load_report(
                template_path=str(template),
                report_prefix=str(root / "ops/reports/load/20260405T030000Z/baseline"),
                environment="staging",
                release_sha="abc1234",
                run_id="20260405T030000Z",
                qa_owner="qa@example.com",
                backend_owner="backend@example.com",
                command="LOAD_TEST_HOST=https://staging.example.com make load-baseline",
                scenario_mix="auth_read, dashboard_read",
                host="https://staging.example.com",
                users="25",
                spawn_rate="5",
                duration="3m",
                disposable_fixtures="trade fixture set A",
            )

            self.assertTrue(created)
            self.assertEqual(
                summary_path,
                root / "ops/reports/load/20260405T030000Z/baseline-summary.md",
            )
            content = summary_path.read_text(encoding="utf-8")
            self.assertIn("- Environment: staging", content)
            self.assertIn("- Release SHA: abc1234", content)
            self.assertIn("- Users: 25", content)
            self.assertIn(
                f"- CSV path: {root / 'ops/reports/load/20260405T030000Z/baseline_stats.csv'}",
                content,
            )
            self.assertIn(
                f"- HTML path: {root / 'ops/reports/load/20260405T030000Z/baseline.html'}",
                content,
            )
            self.assertIn(
                f"- Dashboard / screenshots: {root / 'ops/reports/load/20260405T030000Z/screenshots'}",
                content,
            )

    def test_bootstrap_cutover_report_creates_record_and_support_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "canary-template.md"
            template.write_text(
                "\n".join(
                    [
                        "- Environment:",
                        "- Release SHA:",
                        "- Rehearsal UTC timestamp:",
                        "- QA owner:",
                        "- Backend owner:",
                        "- On-call reviewer:",
                        "- Canary percentage:",
                        "- Feature flags changed:",
                        "- Migration revision at start:",
                        "- Rollback target version:",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report_dir = root / "ops/reports/cutover/20260405T040000Z"
            record_path, created = bootstrap_cutover_report(
                template_path=str(template),
                report_dir=str(report_dir),
                environment="canary",
                release_sha="def5678",
                run_id="20260405T040000Z",
                qa_owner="qa@example.com",
                backend_owner="backend@example.com",
                on_call_reviewer="oncall@example.com",
                canary_percentage="10%",
                feature_flags="shadow_read,trades_dual_write",
                migration_revision="20260404_0003",
                rollback_target_version="release-2026.04.04.1",
            )

            self.assertTrue(created)
            self.assertEqual(record_path, report_dir / "canary-rollback-rehearsal.md")
            self.assertTrue((report_dir / "screenshots").is_dir())
            self.assertTrue((report_dir / "logs").is_dir())
            content = record_path.read_text(encoding="utf-8")
            self.assertIn("- Environment: canary", content)
            self.assertIn("- Canary percentage: 10%", content)
            self.assertIn("- Migration revision at start: 20260404_0003", content)

    def test_bootstrap_preserves_existing_reviewed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "baseline-summary-template.md"
            template.write_text("- Environment:\n", encoding="utf-8")
            report_prefix = root / "ops/reports/load/20260405T050000Z/baseline"
            summary_path = report_prefix.parent / "baseline-summary.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text("reviewed summary\n", encoding="utf-8")

            _, created = bootstrap_load_report(
                template_path=str(template),
                report_prefix=str(report_prefix),
                environment="staging",
                release_sha="",
                run_id="",
                qa_owner="",
                backend_owner="",
                command="",
                scenario_mix="",
                host="",
                users="",
                spawn_rate="",
                duration="",
                disposable_fixtures="",
            )

            self.assertFalse(created)
            self.assertEqual(summary_path.read_text(encoding="utf-8"), "reviewed summary\n")


if __name__ == "__main__":
    unittest.main()
