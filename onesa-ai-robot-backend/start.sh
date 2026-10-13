#!/bin/sh
set -eu
# One process owns the simulator/watchdog; multiple workers cannot share authority.
exec python -m uvicorn robot_api.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8431}" --workers 1 --no-proxy-headers --no-access-log --limit-concurrency 64 --timeout-keep-alive 5 --timeout-graceful-shutdown 10
