import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infra.core.report_artifacts import (
    bootstrap_cutover_report,
    bootstrap_load_report,
    capture_dual_write_summary,
    capture_rollback_verification,
    capture_shadow_read_summary,
    capture_cutover_evidence,
    capture_load_evidence,
    validate_cutover_signoff,
)


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
            self.assertTrue((root / "ops/reports/load/20260405T030000Z/evidence").is_dir())
            self.assertTrue(
                (root / "ops/reports/load/20260405T030000Z/artifact-manifest.json").is_file()
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
            self.assertTrue((report_dir / "evidence").is_dir())
            self.assertTrue((report_dir / "openapi").is_dir())
            self.assertTrue((report_dir / "shadow-read-scenarios.json").is_file())
            self.assertTrue((report_dir / "dual-write-scenarios.json").is_file())
            self.assertTrue((report_dir / "shadow-read-summary.md").is_file())
            self.assertTrue((report_dir / "dual-write-summary.md").is_file())
            self.assertTrue((report_dir / "rollback-verification.md").is_file())
            self.assertTrue((report_dir / "artifact-manifest.json").is_file())
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

    def test_capture_load_and_cutover_evidence_write_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_prefix = root / "ops/reports/load/20260405T050000Z/baseline"
            report_prefix.parent.mkdir(parents=True, exist_ok=True)
            (report_prefix.parent / "baseline-summary.md").write_text(
                "\n".join(
                    [
                        "# Load Baseline Summary",
                        "",
                        "## Key Results",
                        "",
                        "| Metric | Value |",
                        "|---|---|",
                        "| Total requests | |",
                        "| Error rate | |",
                        "| P50 latency | |",
                        "| P95 latency | |",
                        "| P99 latency | |",
                        "| Peak RPS | |",
                        "| Saturation signals | |",
                        "",
                        "## Scenario Notes",
                        "",
                        "| Scenario | Weight / users | Notes |",
                        "|---|---|---|",
                        "| auth_read | | |",
                        "| dashboard_read | | |",
                        "| notification_read | | |",
                        "| trade_action | | |",
                        "| tradingagents_submit | | |",
                        "",
                        "## Findings",
                        "",
                        "- Regressions found:",
                        "- Expected limits hit:",
                        "- Follow-up ticket(s):",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}_stats.csv").write_text(
                "\n".join(
                    [
                        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%",
                        "GET,account.dashboard,60,0,3,3.5,2.0,8.0,100,2.0,0.0,3,3,3,3,4,5,6,7,8,8,8",
                        "POST,auth.send_code,40,10,4,4.0,2.0,10.0,100,1.5,0.5,4,4,4,4,5,6,7,8,10,10,10",
                        "POST,tradingagents.submit,20,20,3,3.0,2.0,5.0,100,0.8,0.8,3,3,3,3,4,4,5,5,5,5,5",
                        ",Aggregated,120,30,3,3.6,2.0,10.0,100,4.3,1.3,3,3,4,4,5,6,7,8,10,10,10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}_stats_history.csv").write_text(
                "\n".join(
                    [
                        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%,Total Request Count,Total Failure Count,Total Median Response Time,Total Average Response Time,Total Min Response Time,Total Max Response Time,Total Average Content Size",
                        "1,10,,Aggregated,4.30,1.30,3,3,4,4,5,6,7,8,10,10,10,120,30,3,3.6,2,10,100",
                        "2,10,,Aggregated,5.20,1.70,3,3,4,4,5,6,7,8,10,10,10,120,30,3,3.6,2,10,100",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}_failures.csv").write_text(
                "\n".join(
                    [
                        "Method,Name,Error,Occurrences",
                        'POST,auth.send_code,"CatchResponseError(\'unexpected status 429, expected (200,): {\"error\":{\"code\":\"send_code_rate_limited\"}}\')",10',
                        'POST,tradingagents.submit,"CatchResponseError(\'unexpected status 422, expected (200,): {\"error\":{\"code\":\"invalid_trigger_type\"}}\')",20',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}.html").write_text("<html></html>\n", encoding="utf-8")
            cutover_dir = root / "ops/reports/cutover/20260405T060000Z"
            cutover_dir.mkdir(parents=True, exist_ok=True)
            (cutover_dir / "canary-rollback-rehearsal.md").write_text("record\n", encoding="utf-8")
            (cutover_dir / "logs").mkdir(exist_ok=True)
            (cutover_dir / "logs/compose-ps.txt").write_text("ps\n", encoding="utf-8")
            (cutover_dir / "logs/compose.log").write_text("log\n", encoding="utf-8")
            (cutover_dir / "openapi").mkdir(exist_ok=True)
            (cutover_dir / "shadow-read-summary.md").write_text("shadow\n", encoding="utf-8")
            (cutover_dir / "dual-write-summary.md").write_text("dual\n", encoding="utf-8")
            (cutover_dir / "rollback-verification.md").write_text("rollback\n", encoding="utf-8")
            captured_headers: list[tuple[str, dict[str, str] | None]] = []

            def fake_capture(*, url, destination, headers=None, timeout_seconds=10.0):
                del timeout_seconds
                captured_headers.append((url, headers))
                if destination.suffix == ".json":
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text('{"ok": true}\n', encoding="utf-8")
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text("metric 1\n", encoding="utf-8")
                return {
                    "url": url,
                    "path": str(destination),
                    "status_code": 200,
                    "content_type": "application/json",
                }

            with patch("infra.core.report_artifacts._capture_http_payload", side_effect=fake_capture):
                load_summary = capture_load_evidence(
                    report_prefix=str(report_prefix),
                    public_health_url="https://staging.example.com/health",
                    public_metrics_url="https://staging.example.com/api/monitoring/metrics",
                    public_metrics_token="monitoring-secret",
                )
                cutover_summary = capture_cutover_evidence(
                    report_dir=str(cutover_dir),
                    public_health_url="https://staging.example.com/health",
                    admin_runtime_metrics_url="https://admin.example.com/v1/admin/runtime/metrics",
                    admin_runtime_alerts_url="https://admin.example.com/v1/admin/runtime/alerts",
                    admin_token="secret",
                )

            self.assertTrue(load_summary["artifacts"]["csv_exists"])
            self.assertEqual(load_summary["load_summary"]["total_requests"], 120)
            self.assertEqual(len(load_summary["http_checks"]), 2)
            self.assertTrue((report_prefix.parent / "evidence/load-evidence-summary.json").is_file())
            load_markdown = (report_prefix.parent / "baseline-summary.md").read_text(encoding="utf-8")
            self.assertIn("| Total requests | 120 |", load_markdown)
            self.assertIn("| Peak RPS | 5.20 req/s |", load_markdown)
            self.assertIn("auth.send_code 429 send_code_rate_limited x10", load_markdown)
            self.assertEqual(
                captured_headers[1],
                (
                    "https://staging.example.com/api/monitoring/metrics",
                    {"Authorization": "Bearer monitoring-secret"},
                ),
            )
            self.assertEqual(len(cutover_summary["http_checks"]), 3)
            self.assertTrue((cutover_dir / "evidence/cutover-validation.json").is_file())

    def test_capture_evidence_records_http_errors_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_prefix = root / "ops/reports/load/20260405T050500Z/baseline"
            report_prefix.parent.mkdir(parents=True, exist_ok=True)
            (report_prefix.parent / "baseline-summary.md").write_text(
                "\n".join(
                    [
                        "| Metric | Value |",
                        "|---|---|",
                        "| Total requests | |",
                        "| Error rate | |",
                        "| P50 latency | |",
                        "| P95 latency | |",
                        "| P99 latency | |",
                        "| Peak RPS | |",
                        "| Saturation signals | |",
                        "| auth_read | | |",
                        "| dashboard_read | | |",
                        "| notification_read | | |",
                        "| trade_action | | |",
                        "| tradingagents_submit | | |",
                        "- Regressions found:",
                        "- Expected limits hit:",
                        "- Follow-up ticket(s):",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}_stats.csv").write_text(
                "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%\n,Aggregated,10,0,3,3.0,2.0,4.0,10,1.0,0.0,3,3,3,3,3,3,4,4,4,4,4\n",
                encoding="utf-8",
            )
            Path(f"{report_prefix}_stats_history.csv").write_text(
                "Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%,Total Request Count,Total Failure Count,Total Median Response Time,Total Average Response Time,Total Min Response Time,Total Max Response Time,Total Average Content Size\n1,1,,Aggregated,1.0,0.0,3,3,3,3,3,3,4,4,4,4,4,10,0,3,3,2,4,10\n",
                encoding="utf-8",
            )

            def raise_capture(*, url, destination, headers=None, timeout_seconds=10.0):
                del url, destination, headers, timeout_seconds
                raise RuntimeError("boom")

            with patch("infra.core.report_artifacts._capture_http_payload", side_effect=raise_capture):
                summary = capture_load_evidence(
                    report_prefix=str(report_prefix),
                    public_health_url="https://staging.example.com/health",
                )

            self.assertEqual(summary["http_checks"][0]["error"], "boom")
            self.assertTrue((report_prefix.parent / "evidence/public-health.json").is_file())

    def test_capture_shadow_read_summary_writes_summary_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "ops/reports/cutover/20260405T070000Z"
            report_dir.mkdir(parents=True, exist_ok=True)
            config_path = report_dir / "shadow-read-scenarios.json"
            config_path.write_text(
                json.dumps(
                    {
                        "owner": "qa@example.com",
                        "scope": "account dashboard/profile, trade info",
                        "primary_label": "legacy",
                        "shadow_label": "python",
                        "scenarios": [
                            {
                                "name": "account-dashboard",
                                "scope": "account",
                                "method": "GET",
                                "primary_url": "${LEGACY_BASE}/api/account/dashboard",
                                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/account/dashboard",
                                "headers": {
                                    "Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"
                                },
                            },
                            {
                                "name": "trade-info",
                                "scope": "trades",
                                "method": "GET",
                                "primary_url": "${LEGACY_BASE}/api/trade/${LOAD_TEST_TRADE_ID}/app-info",
                                "shadow_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                                "headers": {
                                    "Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            call_counts = {"account-dashboard": 0, "trade-info": 0}

            def fake_execute_pair(scenario, timeout_seconds):
                del timeout_seconds
                call_counts[scenario.name] += 1
                if scenario.name == "trade-info":
                    return {
                        "scenario": scenario.name,
                        "scope": scenario.scope,
                        "primary": {
                            "status_code": 200,
                            "latency_ms": 120.0,
                            "payload": {"status": "pending"},
                            "error": "",
                        },
                        "shadow": {
                            "status_code": 200,
                            "latency_ms": 98.0,
                            "payload": {"status": "accepted"},
                            "error": "",
                        },
                        "request_error": False,
                        "status_mismatch": False,
                        "payload_mismatch": True,
                        "mismatch_reason": "payload_mismatch",
                        "primary_preview": '{"status": "pending"}',
                        "shadow_preview": '{"status": "accepted"}',
                    }

                return {
                    "scenario": scenario.name,
                    "scope": scenario.scope,
                    "primary": {
                        "status_code": 200,
                        "latency_ms": 88.0,
                        "payload": {"ok": True},
                        "error": "",
                    },
                    "shadow": {
                        "status_code": 200,
                        "latency_ms": 82.0,
                        "payload": {"ok": True},
                        "error": "",
                    },
                    "request_error": False,
                    "status_mismatch": False,
                    "payload_mismatch": False,
                    "mismatch_reason": "",
                    "primary_preview": "",
                    "shadow_preview": "",
                }

            with patch.dict(
                os.environ,
                {
                    "LEGACY_BASE": "https://legacy.example.com",
                    "SHADOW_READ_SHADOW_BASE_URL": "https://python.example.com",
                    "LOAD_TEST_ACCESS_TOKEN": "token-123",
                    "LOAD_TEST_TRADE_ID": "trade-123",
                },
                clear=False,
            ):
                summary = capture_shadow_read_summary(
                    report_dir=str(report_dir),
                    config_path=str(config_path),
                    duration_seconds=60,
                    interval_seconds=0,
                    iterations=2,
                    execute_pair=fake_execute_pair,
                    sleep_fn=lambda _: None,
                )

            self.assertEqual(summary["owner"], "qa@example.com")
            self.assertEqual(summary["iterations"], 2)
            self.assertEqual(call_counts["account-dashboard"], 2)
            self.assertEqual(call_counts["trade-info"], 2)
            self.assertEqual(len(summary["mismatches"]), 2)
            self.assertTrue((report_dir / "evidence/shadow-read-results.json").is_file())

            summary_content = (report_dir / "shadow-read-summary.md").read_text(encoding="utf-8")
            self.assertIn("- Owner: qa@example.com", summary_content)
            self.assertIn("| trade-info | trades | 2 | 0 | 2 |", summary_content)
            self.assertIn("payload_mismatch", summary_content)

    def test_capture_dual_write_summary_writes_summary_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "ops/reports/cutover/20260405T080000Z"
            report_dir.mkdir(parents=True, exist_ok=True)
            config_path = report_dir / "dual-write-scenarios.json"
            config_path.write_text(
                json.dumps(
                    {
                        "owner": "backend@example.com",
                        "scope": "trade confirm, TradingAgents submit",
                        "containment_decision": "hold canary at 5% on mismatch",
                        "primary_label": "legacy",
                        "shadow_label": "python",
                        "scenarios": [
                            {
                                "name": "trade-confirm",
                                "scope": "trades",
                                "write_method": "POST",
                                "primary_write_url": "${LEGACY_BASE}/api/trade/${LOAD_TEST_TRADE_ID}/app-confirm",
                                "primary_write_headers": {
                                    "Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"
                                },
                                "primary_verify_url": "${LEGACY_BASE}/api/trade/${LOAD_TEST_TRADE_ID}/app-info",
                                "shadow_verify_url": "${SHADOW_READ_SHADOW_BASE_URL}/v1/trades/${LOAD_TEST_TRADE_ID}/app-info",
                                "verify_headers": {
                                    "Authorization": "Bearer ${LOAD_TEST_ACCESS_TOKEN}"
                                },
                            },
                            {
                                "name": "tradingagents-submit",
                                "scope": "tradingagents",
                                "write_method": "POST",
                                "primary_write_url": "${LEGACY_BASE}/internal/integrations/tradingagents/submit",
                                "primary_write_json": {
                                    "request_id": "${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}"
                                },
                                "primary_verify_url": "${LEGACY_BASE}/admin-api/tradingagents/${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                                "shadow_verify_url": "${ADMIN_RUNTIME_URL}/v1/admin/tradingagents/analyses/${DUAL_WRITE_TRADINGAGENTS_REQUEST_ID}",
                                "verify_headers": {
                                    "Authorization": "Bearer ${ADMIN_RUNTIME_TOKEN}"
                                },
                                "containment_decision": "pause TradingAgents canary",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calls: list[tuple[str, str]] = []

            def fake_request(client, *, method, url, headers, params, json_payload):
                del client, headers, params, json_payload
                calls.append((method, url))
                if "analyses" in url:
                    payload = {"status": "submitted"}
                    if "python" in url:
                        payload = {"status": "completed"}
                    return {
                        "status_code": 200,
                        "latency_ms": 42.0,
                        "payload": payload,
                        "error": "",
                    }
                return {
                    "status_code": 200,
                    "latency_ms": 25.0,
                    "payload": {"ok": True},
                    "error": "",
                }

            with patch.dict(
                os.environ,
                {
                    "LEGACY_BASE": "https://legacy.example.com",
                    "SHADOW_READ_SHADOW_BASE_URL": "https://python.example.com",
                    "LOAD_TEST_ACCESS_TOKEN": "token-123",
                    "LOAD_TEST_TRADE_ID": "trade-123",
                    "DUAL_WRITE_TRADINGAGENTS_REQUEST_ID": "req-123",
                    "ADMIN_RUNTIME_URL": "https://python.example.com",
                    "ADMIN_RUNTIME_TOKEN": "admin-token",
                    "DUAL_WRITE_ALLOW_MUTATIONS": "true",
                },
                clear=False,
            ):
                summary = capture_dual_write_summary(
                    report_dir=str(report_dir),
                    config_path=str(config_path),
                    execute_request=fake_request,
                    sleep_fn=lambda _: None,
                )

            self.assertEqual(summary["owner"], "backend@example.com")
            self.assertEqual(len(summary["scenario_summaries"]), 2)
            self.assertEqual(len(summary["mismatches"]), 1)
            self.assertTrue((report_dir / "evidence/dual-write-results.json").is_file())
            dual_write_content = (report_dir / "dual-write-summary.md").read_text(encoding="utf-8")
            self.assertIn("- Containment decision: hold canary at 5% on mismatch", dual_write_content)
            self.assertIn("pause TradingAgents canary", dual_write_content)
            self.assertIn("payload_mismatch", dual_write_content)
            self.assertGreaterEqual(len(calls), 6)

    def test_capture_rollback_verification_and_validate_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            load_dir = root / "ops/reports/load/20260405T090000Z"
            load_dir.mkdir(parents=True, exist_ok=True)
            (load_dir / "baseline-summary.md").write_text(
                "\n".join(
                    [
                        "# Load Baseline Summary",
                        "",
                        "- QA sign-off: qa@example.com",
                        "- Backend sign-off: backend@example.com",
                        "",
                        "| Metric | Value |",
                        "|---|---|",
                        "| Total requests | 1200 |",
                        "| Error rate | 0.1% |",
                        "| P95 latency | 210ms |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report_dir = root / "ops/reports/cutover/20260405T090500Z"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "openapi").mkdir(exist_ok=True)
            (report_dir / "evidence").mkdir(exist_ok=True)
            (report_dir / "canary-rollback-rehearsal.md").write_text(
                "\n".join(
                    [
                        "# Canary / Rollback Rehearsal Record",
                        "",
                        "- Release SHA: abc123",
                        "- QA owner: qa@example.com",
                        "- Backend owner: backend@example.com",
                        "- On-call reviewer: oncall@example.com",
                        "- Approval status: approved",
                        "",
                        "| Checkpoint | Start UTC | End UTC | Result | Notes |",
                        "|---|---|---|---|---|",
                        "| Shadow read | 00:00 | 00:15 | pass | none |",
                        "| Rollback drill | 00:20 | 00:30 | pass | restored |",
                        "",
                        "| Metric | Before | During | After rollback / steady state |",
                        "|---|---|---|---|",
                        "| Public API 5xx rate | 0 | 0 | 0 |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (report_dir / "shadow-read-summary.md").write_text(
                "# Shadow Read Summary\n\n- Owner: qa@example.com\n- Total scenarios: 3\n",
                encoding="utf-8",
            )
            (report_dir / "dual-write-summary.md").write_text(
                "# Dual-Write Summary\n\n- Owner: backend@example.com\n- Containment decision: hold\n- Total scenarios: 4\n",
                encoding="utf-8",
            )
            (report_dir / "openapi/openapi-diff.md").write_text("reviewed diff\n", encoding="utf-8")
            (report_dir / "k8s/validation").mkdir(parents=True, exist_ok=True)
            (report_dir / "k8s/validation/summary.json").write_text("{}\n", encoding="utf-8")

            backup_dir = root / ".local/backups/20260405T091000Z"
            (backup_dir / "postgres").mkdir(parents=True, exist_ok=True)
            (backup_dir / "minio").mkdir(parents=True, exist_ok=True)
            (backup_dir / "postgres/stock_py.dump").write_text("dump", encoding="utf-8")
            (backup_dir / "minio/report.txt").write_text("artifact", encoding="utf-8")
            (backup_dir / "compose-ps.txt").write_text("stack", encoding="utf-8")

            def fake_capture(*, url, destination, headers=None, timeout_seconds=10.0):
                del headers, timeout_seconds
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text('{"ok": true}\n', encoding="utf-8")
                return {
                    "url": url,
                    "path": str(destination),
                    "status_code": 200,
                    "content_type": "application/json",
                }

            with patch("infra.core.report_artifacts._capture_http_payload", side_effect=fake_capture):
                rollback_summary = capture_rollback_verification(
                    report_dir=str(report_dir),
                    backup_dir=str(backup_dir),
                    trigger_used="manual rollback rehearsal",
                    smoke_suite_rerun="auth,dashboard,notifications",
                    backlog_reconciliation="none",
                    final_decision="approved",
                    restore_command=f"make ops-restore-baseline BACKUP_DIR={backup_dir}",
                    public_health_url="https://python.example.com/health",
                )

            signoff = validate_cutover_signoff(
                report_dir=str(report_dir),
                load_report_dir=str(load_dir),
                backup_dir=str(backup_dir),
            )

            self.assertTrue(rollback_summary["backup_artifacts"]["backup_readable"])
            self.assertTrue((report_dir / "evidence/rollback-verification.json").is_file())
            self.assertTrue(signoff["ready"])
            self.assertEqual(signoff["deployment_posture"], "handoff_baseline")
            self.assertTrue((report_dir / "evidence/cutover-signoff-summary.json").is_file())
            signoff_markdown = (report_dir / "cutover-signoff-summary.md").read_text(encoding="utf-8")
            self.assertIn("- Ready for cutover: yes", signoff_markdown)
            self.assertIn("- Deployment posture: handoff_baseline", signoff_markdown)


if __name__ == "__main__":
    unittest.main()
