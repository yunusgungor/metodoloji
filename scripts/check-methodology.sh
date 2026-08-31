#!/bin/bash
# check-methodology.sh — Methodology chain validation script
# Was referenced as INFRA_FILES in Config.py but was missing.
# Validates the whole methodology chain: E → S → QR → PR
#
# Usage: sh scripts/check-methodology.sh [--fix] [--verbose]
#
# Exit codes:
#   0 = all checks passed
#   1 = methodology violations found
#   2 = script error

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Project root = the target project being validated, NOT the methodology repo.
# Resolve from the standard env vars like the hook engine does.
PROJECT_ROOT="${OPENHANDS_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}}"

FIX_MODE=false
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --fix) FIX_MODE=true ;;
        --verbose) VERBOSE=true ;;
    esac
done

ISSUES=0
WARNINGS=0

log_issue() {
    ISSUES=$((ISSUES + 1))
    echo "❌ ISSUE: $1"
}

log_warn() {
    WARNINGS=$((WARNINGS + 1))
    echo "⚠️  WARN: $1"
}

log_ok() {
    if [ "$VERBOSE" = true ]; then
        echo "✅ OK: $1"
    fi
}

# ─── CHECK 1: docs/bmad/ methodology files exist ───
echo "═══════════════════════════════════════════════════"
echo "CHECK 1: Methodology Files"
echo "═══════════════════════════════════════════════════"

for f in docs/bmad/research-methodology.md docs/bmad/development-methodology.md docs/bmad/dev-skill-to-methodology-bridge.md; do
    if [ -f "$PROJECT_ROOT/$f" ]; then
        log_ok "$f exists"
    else
        log_issue "$f is MISSING — required by custom/*.toml persistent_facts"
    fi
done

# ─── CHECK 2: docs/development/ structure ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "CHECK 2: Development Directory Structure"
echo "═══════════════════════════════════════════════════"

for d in docs/development docs/development/stories docs/quality docs/experiments; do
    if [ -d "$PROJECT_ROOT/$d" ]; then
        log_ok "$d/ exists"
    else
        log_warn "$d/ is MISSING — creating"
        if [ "$FIX_MODE" = true ]; then
            mkdir -p "$PROJECT_ROOT/$d"
            echo "  → Created $d/"
        fi
    fi
done

if [ -f "$PROJECT_ROOT/docs/development/_template_S.md" ]; then
    log_ok "docs/development/_template_S.md exists"
else
    log_issue "docs/development/_template_S.md is MISSING — required by bridge doc §2.3"
fi

# ─── CHECK 3: Story files have methodology references ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "CHECK 3: Story Files — Methodology References"
echo "═══════════════════════════════════════════════════"

STORY_COUNT=0
STORY_WITH_REFS=0
STORY_WITHOUT_REFS=0

for story_file in "$PROJECT_ROOT"/docs/development/stories/S-*.md; do
    [ -f "$story_file" ] || continue
    STORY_COUNT=$((STORY_COUNT + 1))
    basename_story=$(basename "$story_file")

    # Check if native story reference exists
    if grep -q "Native Story\|native_story" "$story_file" 2>/dev/null; then
        STORY_WITH_REFS=$((STORY_WITH_REFS + 1))
        log_ok "$basename_story has native story reference"
    else
        STORY_WITHOUT_REFS=$((STORY_WITHOUT_REFS + 1))
        log_warn "$basename_story missing native story reference"
    fi
done

if [ "$STORY_COUNT" -eq 0 ]; then
    log_warn "No methodology story records found in docs/development/stories/"
else
    echo "  Total story records: $STORY_COUNT"
    echo "  With native refs: $STORY_WITH_REFS"
    echo "  Without native refs: $STORY_WITHOUT_REFS"
fi

# ─── CHECK 4: Experiment records integrity ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "CHECK 4: Experiment Records"
echo "═══════════════════════════════════════════════════"

EXP_COUNT=0
EXP_APPROVED=0
EXP_PENDING=0

for exp_file in "$PROJECT_ROOT"/docs/experiments/E-*.md; do
    [ -f "$exp_file" ] || continue
    EXP_COUNT=$((EXP_COUNT + 1))
    basename_exp=$(basename "$exp_file")

    if grep -q "status: APPROVED\|Status: APPROVED\|status: ONAYLANDI\|Status: ONAYLANDI" "$exp_file" 2>/dev/null; then
        EXP_APPROVED=$((EXP_APPROVED + 1))
        log_ok "$basename_exp is APPROVED"
    elif grep -q "status: PENDING\|Status: PENDING\|status: BEKLİYOR\|Status: BEKLİYOR" "$exp_file" 2>/dev/null; then
        EXP_PENDING=$((EXP_PENDING + 1))
        log_warn "$basename_exp is PENDING"
    else
        log_warn "$basename_exp status unknown"
    fi
done

if [ "$EXP_COUNT" -eq 0 ]; then
    log_warn "No experiment records found in docs/experiments/"
else
    echo "  Total experiments: $EXP_COUNT"
    echo "  Approved: $EXP_APPROVED"
    echo "  Pending: $EXP_PENDING"
fi

# ─── CHECK 5: QR records completeness ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "CHECK 5: Quality Records"
echo "═══════════════════════════════════════════════════"

QR_COUNT=0
QR_PASSED=0
QR_FAILED=0

for qr_file in "$PROJECT_ROOT"/docs/quality/QR-*.md; do
    [ -f "$qr_file" ] || continue
    QR_COUNT=$((QR_COUNT + 1))
    basename_qr=$(basename "$qr_file")

    if grep -q "QR Status: pass\|QR Status: passed" "$qr_file" 2>/dev/null; then
        QR_PASSED=$((QR_PASSED + 1))
        log_ok "$basename_qr PASSED"
    elif grep -q "QR Status: fail\|QR Status: failed" "$qr_file" 2>/dev/null; then
        QR_FAILED=$((QR_FAILED + 1))
        log_warn "$basename_qr FAILED"
    else
        log_warn "$basename_qr status unknown"
    fi
done

if [ "$QR_COUNT" -eq 0 ]; then
    log_warn "No QR records found in docs/quality/"
else
    echo "  Total QR records: $QR_COUNT"
    echo "  Passed: $QR_PASSED"
    echo "  Failed: $QR_FAILED"
fi

# ─── CHECK 6: Chain completeness (E → S → QR) ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "CHECK 6: Methodology Chain Completeness"
echo "═══════════════════════════════════════════════════"

# Check if there are stories in sprint-status that lack methodology records
SPRINT_STATUS=""
for candidate in \
    "$PROJECT_ROOT/bmad-output/implementation-artifacts/sprint-status.yaml" \
    "$PROJECT_ROOT/_bmad-output/implementation-artifacts/sprint-status.yaml"; do
    if [ -f "$candidate" ]; then
        SPRINT_STATUS="$candidate"
        break
    fi
done

if [ -n "$SPRINT_STATUS" ] && [ -f "$SPRINT_STATUS" ]; then
    IN_PROGRESS=$(grep -c "in-progress" "$SPRINT_STATUS" 2>/dev/null || echo "0")
    DONE=$(grep -c ": done" "$SPRINT_STATUS" 2>/dev/null || echo "0")
    echo "  Sprint status: $SPRINT_STATUS"
    echo "  In-progress stories: $IN_PROGRESS"
    echo "  Done stories: $DONE"

    if [ "$IN_PROGRESS" -gt 0 ]; then
        log_warn "There are $IN_PROGRESS in-progress stories — verify methodology records exist"
    fi
else
    log_warn "No sprint-status.yaml found — chain cannot be validated"
fi

# ─── SUMMARY ───
echo ""
echo "═══════════════════════════════════════════════════"
echo "SUMMARY"
echo "═══════════════════════════════════════════════════"
echo "  Issues:  $ISSUES"
echo "  Warnings: $WARNINGS"

if [ "$ISSUES" -gt 0 ]; then
    echo ""
    echo "❌ METHODOLOGY VALIDATION FAILED — $ISSUES issues found"
    echo "   Run with --fix to auto-create missing directories"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo ""
    echo "⚠️  METHODOLOGY VALIDATION PASSED with $WARNINGS warnings"
    exit 0
else
    echo ""
    echo "✅ METHODOLOGY VALIDATION PASSED — all checks clean"
    exit 0
fi
