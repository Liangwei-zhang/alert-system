# Canary / Rollback Rehearsal Record

## Metadata

- Environment:
- Release SHA:
- Rehearsal UTC timestamp:
- QA owner:
- Backend owner:
- On-call reviewer:

## Deployment Inputs

- Canary percentage:
- Feature flags changed:
- Migration revision at start:
- Rollback target version:

## Validation Timeline

| Checkpoint | Start UTC | End UTC | Result | Notes |
|---|---|---|---|---|
| Deployment gate | | | | |
| Migration checks | | | | |
| OpenAPI diff | | | | |
| Shadow read | | | | |
| Dual-write parity | | | | |
| Load gate review | | | | |
| Rollback drill | | | | |

## Key Metrics During Rehearsal

| Metric | Before | During | After rollback / steady state |
|---|---|---|---|
| Public API 5xx rate | | | |
| Admin API 5xx rate | | | |
| Auth P95 | | | |
| Dashboard P95 | | | |
| Notifications P95 | | | |
| Trades P95 | | | |
| Worker queue depth | | | |

## Parity Findings

- Shadow read mismatches:
- Dual-write mismatches:
- Analytics / outbox backlog observations:

## Rollback Drill

- Trigger used:
- Time to stop canary expansion:
- Time to restore previous stable deployment:
- Smoke tests rerun:
- Backlog reconciliation outcome:

## Follow-up

- Incidents / tickets created:
- Required fixes before real cutover:
- Approval status: