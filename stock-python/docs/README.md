# Stock Python - Documentation

Documentation for the Stock Python trading platform migration and API contracts.

## Overview

This project is a Python-based stock trading platform with FastAPI backend, Celery workers, and PostgreSQL database.

## API Contracts

### OpenAPI Specifications

- **[Public API](contracts/openapi/public_api.yaml)** - Client-facing endpoints (auth, stocks, portfolio, signals, notifications)
- **[Admin API](contracts/openapi/admin_api.yaml)** - Administrative endpoints (user management, stats, audit, tasks)
- **[Internal API](contracts/openapi/internal_api.yaml)** - Runtime metrics and configuration

## Team Execution Guides

### Platform Team
- [PLATFORM_TEAM_EXECUTION.md](python-migration/PLATFORM_TEAM_EXECUTION.md) - Infrastructure and core platform tasks

### Account Team
- [ACCOUNT_TEAM_EXECUTION.md](python-migration/ACCOUNT_TEAM_EXECUTION.md) - User authentication and account management

### Signal Team
- [SIGNAL_TEAM_EXECUTION.md](python-migration/SIGNAL_TEAM_EXECUTION.md) - Trading signal generation and management

### Notification Team
- [NOTIFICATION_TEAM_EXECUTION.md](python-migration/NOTIFICATION_TEAM_EXECUTION.md) - Push notifications, email dispatch

### QA Team
- [QA_TEAM_EXECUTION.md](python-migration/QA_TEAM_EXECUTION.md) - Testing strategies and validation

## Migration Definition

### Definition of Done
- [DOD.md](DOD.md) - Definition of Done for each domain

### Completion Checklist
- [CHECKLIST.md](CHECKLIST.md) - Domain completion checklist

## Project Structure

```
stock-python/
├── apps/
│   ├── public_api/       # FastAPI public endpoints
│   ├── admin_api/        # FastAPI admin endpoints
│   ├── workers/          # Celery workers
│   └── scheduler/        # Task scheduling
├── domains/              # Business logic
├── contracts/
│   └── openapi/          # OpenAPI specifications
├── docs/                 # Documentation
│   └── python-migration/ # Team execution guides
├── infra/                # Infrastructure code
└── tests/                # Test suites
```