import json
import tempfile
import unittest
from pathlib import Path

from infra.core.openapi_artifacts import diff_openapi_manifests, export_openapi_diff_artifacts


class OpenapiArtifactsTest(unittest.TestCase):
    def test_diff_openapi_manifests_detects_added_removed_and_changed_operations(self) -> None:
        baseline = {
            "title": "Baseline API",
            "version": "1.0.0",
            "paths": {
                "/v1/foo": {
                    "get": {
                        "operationId": "getFoo",
                        "summary": "Get foo",
                        "tags": ["foo"],
                    }
                },
                "/v1/bar": {
                    "post": {
                        "operationId": "createBar",
                        "summary": "Create bar",
                        "tags": ["bar"],
                    }
                },
            },
        }
        current = {
            "title": "Current API",
            "version": "1.0.1",
            "paths": {
                "/v1/foo": {
                    "get": {
                        "operationId": "getFoo",
                        "summary": "Fetch foo",
                        "tags": ["foo", "read"],
                    }
                },
                "/v1/baz": {
                    "delete": {
                        "operationId": "deleteBaz",
                        "summary": "Delete baz",
                        "tags": ["baz"],
                    }
                },
            },
        }

        diff = diff_openapi_manifests(baseline, current)

        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(diff["added"][0]["path"], "/v1/baz")
        self.assertEqual(len(diff["removed"]), 1)
        self.assertEqual(diff["removed"][0]["path"], "/v1/bar")
        self.assertEqual(len(diff["changed"]), 1)
        self.assertEqual(diff["changed"][0]["path"], "/v1/foo")

    def test_export_openapi_diff_artifacts_writes_manifests_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline_dir = root / "baseline"
            output_dir = root / "artifacts"
            baseline_dir.mkdir(parents=True, exist_ok=True)

            public_baseline = {
                "title": "Public API",
                "version": "1.0.0",
                "paths": {
                    "/v1/account/profile": {
                        "get": {
                            "operationId": "getProfile",
                            "summary": "Get profile",
                            "tags": ["account"],
                        }
                    }
                },
            }
            admin_baseline = {
                "title": "Admin API",
                "version": "1.0.0",
                "paths": {},
            }
            (baseline_dir / "public_api_openapi_manifest.json").write_text(
                json.dumps(public_baseline), encoding="utf-8"
            )
            (baseline_dir / "admin_api_openapi_manifest.json").write_text(
                json.dumps(admin_baseline), encoding="utf-8"
            )

            current_manifests = {
                "public_api_openapi_manifest.json": {
                    "title": "Public API",
                    "version": "1.0.1",
                    "paths": {
                        "/v1/account/profile": {
                            "get": {
                                "operationId": "getProfile",
                                "summary": "Fetch profile",
                                "tags": ["account"],
                            }
                        },
                        "/v1/account/dashboard": {
                            "get": {
                                "operationId": "getDashboard",
                                "summary": "Get dashboard",
                                "tags": ["account"],
                            }
                        },
                    },
                },
                "admin_api_openapi_manifest.json": admin_baseline,
            }

            report_path, results = export_openapi_diff_artifacts(
                output_dir=str(output_dir),
                baseline_dir=str(baseline_dir),
                release_sha="abc1234",
                run_id="20260405T070000Z",
                manifests=current_manifests,
            )

            self.assertEqual(report_path, output_dir / "openapi-diff.md")
            self.assertTrue((output_dir / "public_api_openapi_manifest.json").is_file())
            self.assertTrue((output_dir / "admin_api_openapi_manifest.json").is_file())
            self.assertEqual(results["admin_api_openapi_manifest.json"]["status"], "identical")
            self.assertEqual(
                results["public_api_openapi_manifest.json"]["status"], "review-required"
            )
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("# OpenAPI Diff Review", report)
            self.assertIn("- Release SHA: abc1234", report)
            self.assertIn("Added `GET /v1/account/dashboard`", report)
            self.assertIn("Changed `GET /v1/account/profile`", report)


if __name__ == "__main__":
    unittest.main()
