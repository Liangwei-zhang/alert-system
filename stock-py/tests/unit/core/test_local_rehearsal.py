import json
import tempfile
import unittest
from pathlib import Path

from infra.core.local_rehearsal import (
    calibrate_runtime_alerts,
    recommend_runtime_alerts,
    render_k8s_cutover_overrides,
)


class LocalRehearsalTest(unittest.TestCase):
    def test_recommend_runtime_alerts_scales_runtime_metrics(self) -> None:
        recommendations = recommend_runtime_alerts(
            {
                "metrics": [
                    {"name": "event_broker_consumer_lag_total", "value": 250},
                    {"name": "pgbouncer_clients_waiting", "value": 4},
                    {"name": "redis_memory_utilization_percent", "value": 90},
                    {"name": "clickhouse_write_failure_rate_percent", "value": 8},
                    {"name": "object_storage_archive_failure_rate_percent", "value": 1},
                ]
            }
        )

        index = {item["env_key"]: item for item in recommendations}
        self.assertEqual(index["RUNTIME_ALERT_BROKER_LAG_THRESHOLD"]["suggested_value"], 520)
        self.assertEqual(
            index["RUNTIME_ALERT_PGBOUNCER_WAITING_CLIENTS_THRESHOLD"]["suggested_value"],
            10,
        )
        self.assertEqual(
            index["RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD"]["suggested_value"],
            95.0,
        )
        self.assertEqual(
            index["RUNTIME_ALERT_CLICKHOUSE_WRITE_FAILURE_RATE_THRESHOLD"]["suggested_value"],
            16.0,
        )
        self.assertEqual(
            index["RUNTIME_ALERT_OBJECT_STORAGE_ARCHIVE_FAILURE_RATE_THRESHOLD"]["suggested_value"],
            5.0,
        )

    def test_calibrate_runtime_alerts_writes_env_and_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metrics_dir = root / "ops/reports/cutover/20260406T010203Z/evidence"
            metrics_dir.mkdir(parents=True, exist_ok=True)
            metrics_path = metrics_dir / "admin-runtime-metrics.json"
            metrics_path.write_text(
                json.dumps(
                    {
                        "metrics": [
                            {"name": "event_broker_consumer_lag_total", "value": 25},
                            {"name": "pgbouncer_clients_waiting", "value": 6},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = calibrate_runtime_alerts(
                metrics_path=str(metrics_dir.parent),
                output_env=str(metrics_dir / "runtime-alert-thresholds.env"),
                output_json=str(metrics_dir / "runtime-alert-thresholds.json"),
            )

            env_content = (metrics_dir / "runtime-alert-thresholds.env").read_text(encoding="utf-8")
            self.assertIn("RUNTIME_ALERT_BROKER_LAG_THRESHOLD=200", env_content)
            self.assertIn("RUNTIME_ALERT_PGBOUNCER_WAITING_CLIENTS_THRESHOLD=14", env_content)
            self.assertTrue((metrics_dir / "runtime-alert-thresholds.json").is_file())
            self.assertEqual(summary["metrics_path"], str(metrics_path))

    def test_render_k8s_cutover_overrides_writes_overlay_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_overlay = root / "ops/k8s/overlays/staging"
            base_overlay.mkdir(parents=True, exist_ok=True)
            (base_overlay / "kustomization.yaml").write_text(
                "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n",
                encoding="utf-8",
            )
            env_path = root / "runtime-alert-thresholds.env"
            env_path.write_text(
                "\n".join(
                    [
                        "RUNTIME_ALERT_BROKER_LAG_THRESHOLD=320",
                        "RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD=91.5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = render_k8s_cutover_overrides(
                runtime_alert_env=str(env_path),
                output_dir=str(root / "rendered"),
                environment="staging",
                base_kustomize_path=str(base_overlay),
                namespace="stock-py-staging",
                ingress_host="stock-py-staging.example.com",
                release_image="ghcr.io/openclaw/stock-py:20260406",
            )

            overlay_dir = root / "rendered"
            kustomization = (overlay_dir / "kustomization.yaml").read_text(encoding="utf-8")
            config_patch = (overlay_dir / "runtime-alert-thresholds.patch.yaml").read_text(
                encoding="utf-8"
            )
            prometheus_patch = (
                overlay_dir / "prometheus-runtime-thresholds.patch.yaml"
            ).read_text(encoding="utf-8")

            self.assertIn("namespace: stock-py-staging", kustomization)
            self.assertIn(f"  - {Path('../ops/k8s/overlays/staging')}", kustomization)
            self.assertIn("newTag: 20260406", kustomization)
            self.assertIn(
                'RUNTIME_ALERT_BROKER_LAG_THRESHOLD: "320"',
                config_patch,
            )
            self.assertIn(
                'RUNTIME_ALERT_REDIS_MEMORY_PERCENT_THRESHOLD: "91.5"',
                config_patch,
            )
            self.assertIn(
                'value: "max(stock_signal_admin_event_broker_consumer_lag_total) > 320"',
                prometheus_patch,
            )
            self.assertEqual(summary["namespace"], "stock-py-staging")
            self.assertEqual(summary["threshold_values"]["RUNTIME_ALERT_BROKER_LAG_THRESHOLD"], "320")


if __name__ == "__main__":
    unittest.main()
