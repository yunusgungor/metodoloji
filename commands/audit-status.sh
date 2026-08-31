#!/bin/sh
# audit-status.sh — Periodic audit: check methodology status
# Usage: sh audit-status.sh

echo "=== BMAD Methodology Status Report ==="
echo "Date: $(date)"
echo

# 1. Gate Key Status
echo "1. Gate Key:"
if [ -f "$HOME/.bmad/gate-key" ]; then
    echo "   ✓ Installed ($(wc -c < "$HOME/.bmad/gate-key") bytes)"
else
    echo "   ✗ Missing (create with: python3 run_experiment.py --init-secret)"
fi

# 2. Experiment Records
echo "2. Experiment Records:"
if [ -d "docs/experiments" ]; then
    COUNT=$(ls -1 docs/experiments/*.md 2>/dev/null | wc -l)
    echo "   $COUNT records present"
    ls -1 docs/experiments/*.md 2>/dev/null | head -5
else
    echo "   ✗ docs/experiments/ directory missing"
fi

# 3. Hook Log Status
echo "3. Hook Logs:"
if [ -f ".metodoloji/logs/hook-audit.log" ]; then
    LINES=$(wc -l < ".metodoloji/logs/hook-audit.log")
    echo "   $LINES log lines present"
else
    echo "   ✗ Log file missing"
fi

# 4. Plugin Directory Structure
echo "4. Plugin Structure:"
echo "   Skills: $(ls -1 skills/ 2>/dev/null | wc -l)"
echo "   Custom TOML: $(ls -1 custom/*.toml 2>/dev/null | wc -l)"
echo "   Commands: $(ls -1 commands/*.md 2>/dev/null | wc -l)"

# 5. Guard Hook Test
echo "5. Guard Hook Test:"
RESULT=$(echo '{"tool_name": "terminal", "tool_input": {"command": "ls"}}' | python3 hooks/engine/main.py guard 2>/dev/null)
if echo "$RESULT" | grep -q '"allow"'; then
    echo "   ✓ Guard hook is working"
else
    echo "   ✗ Guard hook has an issue: $RESULT"
fi

echo
echo "=== End of Report ==="
