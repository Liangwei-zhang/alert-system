#!/usr/bin/env bash
set -euo pipefail

cd /home/nico/.openclaw/workspace-main/stock-py
DEBUG=false DATABASE_ECHO=false .venv/bin/python import_history_archive.py --all-symbols --batch-size 10000