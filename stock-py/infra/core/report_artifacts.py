from __future__ import annotations

import argparse
import os
from pathlib import Path

DEFAULT_LOAD_SCENARIOS = (
    "auth_read",
    "dashboard_read",
    "notification_read",
    "trade_action",
    "tradingagents_submit",
)

DEFAULT_LOAD_FIXTURES = (
    "LOAD_TEST_ACCESS_TOKEN",
    "LOAD_TEST_REFRESH_TOKEN",
    "LOAD_TEST_TRADE_ID",
    "LOAD_TEST_TRADE_TOKEN",
)


def _display(value: str | None, placeholder: str) -> str:
    normalized = (value or "").strip()
    return normalized or placeholder


def _replace_markdown_field(template: str, label: str, value: str) -> str:
    target_prefix = f"- {label}:"
    replacement = f"{target_prefix} {value}"
    lines = template.splitlines()
    replaced = False

    for index, line in enumerate(lines):
        if line.startswith(target_prefix):
            lines[index] = replacement
            replaced = True
            break

    if not replaced:
        raise ValueError(f"Template field not found: {label}")

    return "\n".join(lines) + "\n"


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def build_load_command(host: str, users: str, spawn_rate: str, duration: str) -> str:
    return " ".join(
        [
            f"LOAD_TEST_HOST={_display(host, '<set before run>')}",
            f"LOAD_USERS={_display(users, '5')}",
            f"LOAD_SPAWN_RATE={_display(spawn_rate, '1')}",
            f"LOAD_DURATION={_display(duration, '1m')}",
            "make load-baseline",
        ]
    )


def bootstrap_load_report(
    *,
    template_path: str,
    report_prefix: str,
    environment: str,
    release_sha: str,
    run_id: str,
    qa_owner: str,
    backend_owner: str,
    command: str,
    scenario_mix: str,
    host: str,
    users: str,
    spawn_rate: str,
    duration: str,
    disposable_fixtures: str,
) -> tuple[Path, bool]:
    report_prefix_path = Path(report_prefix)
    summary_path = report_prefix_path.parent / "baseline-summary.md"
    if summary_path.exists():
        return summary_path, False

    template = Path(template_path).read_text(encoding="utf-8")

    content = template
    replacements = {
        "Environment": _display(environment, "staging"),
        "Release SHA": _display(release_sha, "<fill before review>"),
        "Run UTC timestamp": _display(run_id, "<set before run>"),
        "QA owner": _display(qa_owner, "<assign owner>"),
        "Backend owner": _display(backend_owner, "<assign owner>"),
        "Command": _display(command, build_load_command(host, users, spawn_rate, duration)),
        "Scenario mix": _display(scenario_mix, ", ".join(DEFAULT_LOAD_SCENARIOS)),
        "Host": _display(host, "<set before run>"),
        "Users": _display(users, "5"),
        "Spawn rate": _display(spawn_rate, "1"),
        "Duration": _display(duration, "1m"),
        "Disposable fixtures used": _display(disposable_fixtures, ", ".join(DEFAULT_LOAD_FIXTURES)),
        "CSV path": f"{report_prefix}_stats.csv",
        "HTML path": f"{report_prefix}.html",
        "Dashboard / screenshots": f"{report_prefix_path.parent}/screenshots/",
    }
    for label, value in replacements.items():
        content = _replace_markdown_field(content, label, value)

    return summary_path, _write_if_missing(summary_path, content)


def bootstrap_cutover_report(
    *,
    template_path: str,
    report_dir: str,
    environment: str,
    release_sha: str,
    run_id: str,
    qa_owner: str,
    backend_owner: str,
    on_call_reviewer: str,
    canary_percentage: str,
    feature_flags: str,
    migration_revision: str,
    rollback_target_version: str,
) -> tuple[Path, bool]:
    report_dir_path = Path(report_dir)
    report_dir_path.mkdir(parents=True, exist_ok=True)
    (report_dir_path / "screenshots").mkdir(exist_ok=True)
    (report_dir_path / "logs").mkdir(exist_ok=True)
    record_path = report_dir_path / "canary-rollback-rehearsal.md"
    if record_path.exists():
        return record_path, False

    template = Path(template_path).read_text(encoding="utf-8")

    content = template
    replacements = {
        "Environment": _display(environment, "staging"),
        "Release SHA": _display(release_sha, "<fill before rehearsal>"),
        "Rehearsal UTC timestamp": _display(run_id, report_dir_path.name),
        "QA owner": _display(qa_owner, "<assign owner>"),
        "Backend owner": _display(backend_owner, "<assign owner>"),
        "On-call reviewer": _display(on_call_reviewer, "<assign reviewer>"),
        "Canary percentage": _display(canary_percentage, "<planned percentage>"),
        "Feature flags changed": _display(feature_flags, "<record changed flags>"),
        "Migration revision at start": _display(migration_revision, "<record alembic revision>"),
        "Rollback target version": _display(rollback_target_version, "<record stable version>"),
    }
    for label, value in replacements.items():
        content = _replace_markdown_field(content, label, value)

    return record_path, _write_if_missing(record_path, content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap load and cutover report artifacts.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    load_parser = subparsers.add_parser(
        "load-baseline",
        help="Create a prefilled load baseline summary next to raw Locust artifacts.",
    )
    load_parser.add_argument(
        "--template-path", default="ops/reports/load/baseline-summary-template.md"
    )
    load_parser.add_argument("--report-prefix", required=True)
    load_parser.add_argument("--environment", default=os.getenv("LOAD_TEST_ENVIRONMENT", "staging"))
    load_parser.add_argument(
        "--release-sha", default=os.getenv("RELEASE_SHA", os.getenv("GITHUB_SHA", ""))
    )
    load_parser.add_argument("--run-id", default=os.getenv("LOAD_RUN_ID", ""))
    load_parser.add_argument("--qa-owner", default=os.getenv("QA_OWNER", ""))
    load_parser.add_argument("--backend-owner", default=os.getenv("BACKEND_OWNER", ""))
    load_parser.add_argument("--command", default="")
    load_parser.add_argument("--scenario-mix", default=", ".join(DEFAULT_LOAD_SCENARIOS))
    load_parser.add_argument("--host", default=os.getenv("LOAD_TEST_HOST", ""))
    load_parser.add_argument("--users", default=os.getenv("LOAD_USERS", ""))
    load_parser.add_argument("--spawn-rate", default=os.getenv("LOAD_SPAWN_RATE", ""))
    load_parser.add_argument("--duration", default=os.getenv("LOAD_DURATION", ""))
    load_parser.add_argument("--disposable-fixtures", default=", ".join(DEFAULT_LOAD_FIXTURES))

    cutover_parser = subparsers.add_parser(
        "cutover-rehearsal",
        help="Create a prefilled cutover rehearsal record with screenshots/log directories.",
    )
    cutover_parser.add_argument(
        "--template-path", default="ops/reports/cutover/canary-rollback-rehearsal-template.md"
    )
    cutover_parser.add_argument("--report-dir", required=True)
    cutover_parser.add_argument(
        "--environment", default=os.getenv("CUTOVER_ENVIRONMENT", "staging")
    )
    cutover_parser.add_argument(
        "--release-sha", default=os.getenv("RELEASE_SHA", os.getenv("GITHUB_SHA", ""))
    )
    cutover_parser.add_argument("--run-id", default=os.getenv("CUTOVER_RUN_ID", ""))
    cutover_parser.add_argument("--qa-owner", default=os.getenv("QA_OWNER", ""))
    cutover_parser.add_argument("--backend-owner", default=os.getenv("BACKEND_OWNER", ""))
    cutover_parser.add_argument("--on-call-reviewer", default=os.getenv("ON_CALL_REVIEWER", ""))
    cutover_parser.add_argument("--canary-percentage", default="")
    cutover_parser.add_argument("--feature-flags", default="")
    cutover_parser.add_argument("--migration-revision", default="")
    cutover_parser.add_argument("--rollback-target-version", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "load-baseline":
        path, created = bootstrap_load_report(
            template_path=args.template_path,
            report_prefix=args.report_prefix,
            environment=args.environment,
            release_sha=args.release_sha,
            run_id=args.run_id,
            qa_owner=args.qa_owner,
            backend_owner=args.backend_owner,
            command=args.command,
            scenario_mix=args.scenario_mix,
            host=args.host,
            users=args.users,
            spawn_rate=args.spawn_rate,
            duration=args.duration,
            disposable_fixtures=args.disposable_fixtures,
        )
        status = "Created" if created else "Preserved"
        print(f"{status} load summary: {path}")
        return 0

    path, created = bootstrap_cutover_report(
        template_path=args.template_path,
        report_dir=args.report_dir,
        environment=args.environment,
        release_sha=args.release_sha,
        run_id=args.run_id,
        qa_owner=args.qa_owner,
        backend_owner=args.backend_owner,
        on_call_reviewer=args.on_call_reviewer,
        canary_percentage=args.canary_percentage,
        feature_flags=args.feature_flags,
        migration_revision=args.migration_revision,
        rollback_target_version=args.rollback_target_version,
    )
    status = "Created" if created else "Preserved"
    print(f"{status} cutover record: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
