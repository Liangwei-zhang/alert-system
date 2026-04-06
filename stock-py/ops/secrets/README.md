# Secrets Layout

- `ops/secrets/dev/`: checked-in development defaults for the single-node baseline.
- `ops/secrets/local/`: local-only overrides; ignored by git.
- `ops/secrets/production/`: production secret material; ignored by git.

Use `OPS_SECRET_DIR` to point Compose at a different secret directory:

```bash
OPS_SECRET_DIR=./secrets/production docker compose -f ops/docker-compose.yml up -d
```

The application containers read `*_FILE` environment variables directly, so the Compose file mounts secrets without exposing them in plain env vars.