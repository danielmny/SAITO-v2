#!/usr/bin/env bash
# stop.sh — Runs after each Claude Code session ends (Cowork agent post-run hook)
# Scans recent agent output files for [ESCALATE TO FOUNDER] and writes pending escalation files.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
OUTPUTS_DIR="$PROJECT_DIR/outputs"
ESCALATIONS_PENDING="$OUTPUTS_DIR/escalations/pending"
HANDOFFS_DIR="$OUTPUTS_DIR/handoffs"

# Only run escalation scan if we're in a scheduled agent session
# (CLAUDE_TASK_ID is set by the scheduled-tasks MCP when a task fires)
if [ -z "${CLAUDE_TASK_ID:-}" ]; then
  exit 0
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE=$(date -u +"%Y-%m-%d")

# Find output files written in the last 10 minutes
RECENT_FILES=$(find "$OUTPUTS_DIR" -name "*.md" -newer "$OUTPUTS_DIR/state.json" -not -path "*/handoffs/*" -not -path "*/escalations/*" 2>/dev/null || true)

for file in $RECENT_FILES; do
  if grep -q "\[ESCALATE TO FOUNDER\]" "$file" 2>/dev/null; then
    # Extract agent name from path: outputs/AGENT_NAME/...
    AGENT_NAME=$(echo "$file" | sed "s|$OUTPUTS_DIR/||" | cut -d'/' -f1)

    # Generate escalation ID
    ESC_SEQ=$(ls "$ESCALATIONS_PENDING" 2>/dev/null | grep -c "^ESC-$DATE" || echo "0")
    ESC_SEQ=$((ESC_SEQ + 1))
    ESC_ID="ESC-$DATE-$(printf '%03d' $ESC_SEQ)"
    ESC_FILE="$ESCALATIONS_PENDING/${ESC_ID}.md"

    # Skip if already recorded
    if [ -f "$ESC_FILE" ]; then
      continue
    fi

    # Extract the escalation context (lines around [ESCALATE TO FOUNDER])
    CONTEXT=$(grep -A 3 -B 1 "\[ESCALATE TO FOUNDER\]" "$file" | head -20 || echo "(see source file)")

    cat > "$ESC_FILE" <<EOF
---
escalation_id: $ESC_ID
agent: $AGENT_NAME
source_file: $file
status: pending
created: $TIMESTAMP
---

# Escalation: $ESC_ID

**Agent:** $AGENT_NAME
**Created:** $TIMESTAMP
**Source:** $file

## Context

$CONTEXT

## To Respond

Create a file in \`FOUNDER_RESPONSES/\` named \`RE: $ESC_ID.md\` with your decision or answer.
MERIDIAN will detect it on its next daily run and unblock the relevant agents.
EOF

    echo "Escalation created: $ESC_FILE" >&2
  fi
done
