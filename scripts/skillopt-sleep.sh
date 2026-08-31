#!/bin/sh
# skillopt-sleep.sh — nightly self-evolution launcher for this methodology repo.
#
# Wraps the pip-installed skillopt-sleep CLI with the repo's config so the
# self-optimization loop runs against the actual skills/ tree. It also runs
# scripts/bridge_real_usage.py first, so the night's training data includes
# real sessions (experiments, learnings, audit events) — not just synthetic
# benchmark scenarios.
#
# Usage:
#   sh scripts/skillopt-sleep.sh run         # full cycle → proposal staged
#   sh scripts/skillopt-sleep.sh dry-run     # report only, no writes
#   sh scripts/skillopt-sleep.sh status      # show staged proposal
#   sh scripts/skillopt-sleep.sh adopt       # apply approved changes
#   sh scripts/skillopt-sleep.sh schedule    # install nightly cron/schtasks
#   sh scripts/skillopt-sleep.sh unschedule  # remove it
set -u

SELF=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF/.." && pwd)
MODE="${1:-dry-run}"

PY=
for c in python3 python py; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
done
if [ -z "$PY" ]; then
    echo "[skillopt-sleep] python not found" >&2
    exit 2
fi

case "$MODE" in
    run|dry-run)
        # Bridge real usage into training data before the cycle.
        "$PY" "$ROOT/scripts/bridge_real_usage.py" || echo "[skillopt-sleep] bridge warning" >&2
        exec "$PY" -m skillopt_sleep "$MODE"
        ;;
    status|adopt|schedule|unschedule|harvest)
        exec "$PY" -m skillopt_sleep "$MODE"
        ;;
    *)
        echo "usage: sh scripts/skillopt-sleep.sh <run|dry-run|status|adopt|schedule|unschedule|harvest>" >&2
        exit 2
        ;;
esac
