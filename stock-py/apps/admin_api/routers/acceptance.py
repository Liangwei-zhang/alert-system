from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/v1/admin/acceptance", tags=["admin", "acceptance"])

REPO_ROOT = Path(__file__).resolve().parents[3]


class AcceptanceArtifactResponse(BaseModel):
    path: str
    exists: bool
    reviewed: bool | None = None
    updated_at: datetime | None = None


class AcceptanceStatusResponse(BaseModel):
    qa_workflow_ready: bool
    qa_runbook_ready: bool
    public_openapi_snapshot_ready: bool
    admin_openapi_snapshot_ready: bool
    load_template_ready: bool
    cutover_template_ready: bool
    reviewed_load_reports: int
    reviewed_cutover_reports: int
    latest_load_report: str | None = None
    latest_cutover_report: str | None = None
    acceptance_ready: bool


class AcceptanceReportResponse(BaseModel):
    status: AcceptanceStatusResponse
    commands: list[str]
    automation_artifacts: list[AcceptanceArtifactResponse]
    openapi_snapshots: list[AcceptanceArtifactResponse]
    load_reports: list[AcceptanceArtifactResponse]
    cutover_reports: list[AcceptanceArtifactResponse]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _artifact(path: Path, *, reviewed: bool | None = None) -> AcceptanceArtifactResponse:
    exists = path.exists()
    updated_at = None
    if exists:
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return AcceptanceArtifactResponse(
        path=_relative(path),
        exists=exists,
        reviewed=reviewed,
        updated_at=updated_at,
    )


def _list_reviewed_reports(
    base_dir: Path, file_name: str, *, limit: int = 10
) -> list[AcceptanceArtifactResponse]:
    if not base_dir.exists():
        return []
    reports: list[AcceptanceArtifactResponse] = []
    for child in sorted(
        (item for item in base_dir.iterdir() if item.is_dir()),
        key=lambda item: item.name,
        reverse=True,
    ):
        report_path = child / file_name
        if report_path.exists():
            reports.append(_artifact(report_path, reviewed=True))
        if len(reports) >= limit:
            break
    return reports


def _build_status() -> AcceptanceStatusResponse:
    qa_workflow = REPO_ROOT / ".github/workflows/qa.yml"
    qa_runbook = REPO_ROOT / "ops/runbooks/qa-cutover-checklist.md"
    public_openapi = REPO_ROOT / "tests/contract/snapshots/public_api_openapi_manifest.json"
    admin_openapi = REPO_ROOT / "tests/contract/snapshots/admin_api_openapi_manifest.json"
    load_template = REPO_ROOT / "ops/reports/load/baseline-summary-template.md"
    cutover_template = REPO_ROOT / "ops/reports/cutover/canary-rollback-rehearsal-template.md"
    load_reports = _list_reviewed_reports(REPO_ROOT / "ops/reports/load", "baseline-summary.md")
    cutover_reports = _list_reviewed_reports(
        REPO_ROOT / "ops/reports/cutover", "canary-rollback-rehearsal.md"
    )
    acceptance_ready = all(
        [
            qa_workflow.exists(),
            qa_runbook.exists(),
            public_openapi.exists(),
            admin_openapi.exists(),
            load_template.exists(),
            cutover_template.exists(),
            len(load_reports) > 0,
            len(cutover_reports) > 0,
        ]
    )
    return AcceptanceStatusResponse(
        qa_workflow_ready=qa_workflow.exists(),
        qa_runbook_ready=qa_runbook.exists(),
        public_openapi_snapshot_ready=public_openapi.exists(),
        admin_openapi_snapshot_ready=admin_openapi.exists(),
        load_template_ready=load_template.exists(),
        cutover_template_ready=cutover_template.exists(),
        reviewed_load_reports=len(load_reports),
        reviewed_cutover_reports=len(cutover_reports),
        latest_load_report=load_reports[0].path if load_reports else None,
        latest_cutover_report=cutover_reports[0].path if cutover_reports else None,
        acceptance_ready=acceptance_ready,
    )


@router.get("/status", response_model=AcceptanceStatusResponse)
async def get_acceptance_status() -> AcceptanceStatusResponse:
    return _build_status()


@router.get("/report", response_model=AcceptanceReportResponse)
async def get_acceptance_report() -> AcceptanceReportResponse:
    status = _build_status()
    automation_artifacts = [
        _artifact(REPO_ROOT / ".github/workflows/qa.yml"),
        _artifact(REPO_ROOT / "ops/runbooks/qa-cutover-checklist.md"),
        _artifact(REPO_ROOT / "ops/reports/load/baseline-summary-template.md"),
        _artifact(REPO_ROOT / "ops/reports/cutover/canary-rollback-rehearsal-template.md"),
    ]
    openapi_snapshots = [
        _artifact(REPO_ROOT / "tests/contract/snapshots/public_api_openapi_manifest.json"),
        _artifact(REPO_ROOT / "tests/contract/snapshots/admin_api_openapi_manifest.json"),
    ]
    load_reports = _list_reviewed_reports(REPO_ROOT / "ops/reports/load", "baseline-summary.md")
    cutover_reports = _list_reviewed_reports(
        REPO_ROOT / "ops/reports/cutover", "canary-rollback-rehearsal.md"
    )
    return AcceptanceReportResponse(
        status=status,
        commands=[
            "make qa-ci",
            "make load-report-init",
            "make cutover-report-init",
            "make cutover-openapi-diff",
        ],
        automation_artifacts=automation_artifacts,
        openapi_snapshots=openapi_snapshots,
        load_reports=load_reports,
        cutover_reports=cutover_reports,
    )
