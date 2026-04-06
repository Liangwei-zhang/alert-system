from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

MANIFEST_FILE_MAP = {
    "public": "public_api_openapi_manifest.json",
    "admin": "admin_api_openapi_manifest.json",
}


def build_openapi_manifest(app: FastAPI) -> dict[str, Any]:
    schema = app.openapi()
    return {
        "title": schema.get("info", {}).get("title"),
        "version": schema.get("info", {}).get("version"),
        "paths": {
            path: {
                method: {
                    "operationId": details.get("operationId"),
                    "summary": details.get("summary"),
                    "tags": details.get("tags", []),
                }
                for method, details in sorted(methods.items())
            }
            for path, methods in sorted(schema.get("paths", {}).items())
        },
    }


def build_current_manifests() -> dict[str, dict[str, Any]]:
    from apps.admin_api.main import app as admin_app
    from apps.public_api.main import app as public_app

    return {
        MANIFEST_FILE_MAP["public"]: build_openapi_manifest(public_app),
        MANIFEST_FILE_MAP["admin"]: build_openapi_manifest(admin_app),
    }


def _build_operation_index(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    for path, methods in manifest.get("paths", {}).items():
        for method, details in methods.items():
            operations[(path, method.lower())] = details
    return operations


def diff_openapi_manifests(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    baseline_ops = _build_operation_index(baseline)
    current_ops = _build_operation_index(current)

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []

    for path, method in sorted(current_ops.keys() - baseline_ops.keys()):
        added.append(
            {
                "path": path,
                "method": method,
                "current": current_ops[(path, method)],
            }
        )

    for path, method in sorted(baseline_ops.keys() - current_ops.keys()):
        removed.append(
            {
                "path": path,
                "method": method,
                "baseline": baseline_ops[(path, method)],
            }
        )

    for path, method in sorted(baseline_ops.keys() & current_ops.keys()):
        baseline_details = baseline_ops[(path, method)]
        current_details = current_ops[(path, method)]
        if baseline_details != current_details:
            changed.append(
                {
                    "path": path,
                    "method": method,
                    "baseline": baseline_details,
                    "current": current_details,
                }
            )

    return {"added": added, "removed": removed, "changed": changed}


def _format_operation(path: str, method: str, details: dict[str, Any]) -> str:
    operation_id = details.get("operationId") or "<missing operationId>"
    summary = details.get("summary") or "<missing summary>"
    tags = ", ".join(details.get("tags", [])) or "<no tags>"
    return f"`{method.upper()} {path}` (`{operation_id}`; summary: `{summary}`; tags: `{tags}`)"


def _render_api_diff_section(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    status = result["status"]

    if status == "missing-baseline":
        lines.append(f"- Baseline file missing: `{result['baseline_path']}`")
        return lines

    diff = result["diff"]
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        lines.append("- No manifest differences detected.")
        return lines

    for item in diff["added"]:
        lines.append(
            f"- Added { _format_operation(item['path'], item['method'], item['current']) }"
        )
    for item in diff["removed"]:
        lines.append(
            f"- Removed { _format_operation(item['path'], item['method'], item['baseline']) }"
        )
    for item in diff["changed"]:
        lines.append(
            "- Changed "
            f"`{item['method'].upper()} {item['path']}`: "
            f"operationId `{item['baseline'].get('operationId')}` -> `{item['current'].get('operationId')}`, "
            f"summary `{item['baseline'].get('summary')}` -> `{item['current'].get('summary')}`, "
            f"tags `{', '.join(item['baseline'].get('tags', [])) or '<no tags>'}` -> "
            f"`{', '.join(item['current'].get('tags', [])) or '<no tags>'}`"
        )

    return lines


def render_openapi_diff_report(
    *,
    output_dir: str,
    baseline_dir: str,
    release_sha: str,
    run_id: str,
    results: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "# OpenAPI Diff Review",
        "",
        "## Metadata",
        "",
        f"- Release SHA: {release_sha or '<fill before review>'}",
        f"- Review UTC timestamp: {run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"- Baseline directory: {baseline_dir}",
        f"- Output directory: {output_dir}",
        "",
        "## Summary",
        "",
        "| API | Added | Removed | Changed | Status |",
        "|---|---|---|---|---|",
    ]

    for file_name, result in sorted(results.items()):
        diff = result.get("diff", {"added": [], "removed": [], "changed": []})
        lines.append(
            f"| {file_name} | {len(diff['added'])} | {len(diff['removed'])} | {len(diff['changed'])} | {result['status']} |"
        )

    for file_name, result in sorted(results.items()):
        lines.extend(["", f"## {file_name}", ""])
        lines.append(f"- Current manifest: `{result['current_path']}`")
        lines.append(f"- Baseline manifest: `{result['baseline_path']}`")
        lines.extend(_render_api_diff_section(result))

    return "\n".join(lines) + "\n"


def export_openapi_diff_artifacts(
    *,
    output_dir: str,
    baseline_dir: str,
    release_sha: str,
    run_id: str,
    manifests: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, dict[str, Any]]]:
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    baseline_dir_path = Path(baseline_dir)

    manifests = manifests or build_current_manifests()
    results: dict[str, dict[str, Any]] = {}

    for file_name, manifest in manifests.items():
        current_path = output_dir_path / file_name
        current_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        baseline_path = baseline_dir_path / file_name

        if baseline_path.exists():
            baseline_manifest = json.loads(baseline_path.read_text(encoding="utf-8"))
            diff = diff_openapi_manifests(baseline_manifest, manifest)
            status = "identical"
            if diff["added"] or diff["removed"] or diff["changed"]:
                status = "review-required"
            results[file_name] = {
                "status": status,
                "diff": diff,
                "baseline_path": str(baseline_path),
                "current_path": str(current_path),
            }
            continue

        results[file_name] = {
            "status": "missing-baseline",
            "diff": {"added": [], "removed": [], "changed": []},
            "baseline_path": str(baseline_path),
            "current_path": str(current_path),
        }

    report_path = output_dir_path / "openapi-diff.md"
    report_path.write_text(
        render_openapi_diff_report(
            output_dir=str(output_dir_path),
            baseline_dir=str(baseline_dir_path),
            release_sha=release_sha,
            run_id=run_id,
            results=results,
        ),
        encoding="utf-8",
    )
    return report_path, results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export current OpenAPI manifests and diff them.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    diff_parser = subparsers.add_parser(
        "cutover-diff",
        help="Write current public/admin manifests and a markdown diff summary for cutover review.",
    )
    diff_parser.add_argument("--output-dir", required=True)
    diff_parser.add_argument("--baseline-dir", default="tests/contract/snapshots")
    diff_parser.add_argument(
        "--release-sha", default=os.getenv("RELEASE_SHA", os.getenv("GITHUB_SHA", ""))
    )
    diff_parser.add_argument("--run-id", default=os.getenv("CUTOVER_RUN_ID", ""))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report_path, _ = export_openapi_diff_artifacts(
        output_dir=args.output_dir,
        baseline_dir=args.baseline_dir,
        release_sha=args.release_sha,
        run_id=args.run_id,
    )
    print(f"Wrote OpenAPI diff artifacts: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
