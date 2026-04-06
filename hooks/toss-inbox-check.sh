#!/bin/bash
# Check Toss inbox on session start
# Requires: toss installed globally (uv tool install .)
if ! command -v toss &>/dev/null; then
    exit 0
fi
output=$(toss inbox 2>/dev/null)
# Count data rows (lines with │ but not header/border lines)
count=$(echo "$output" | grep "^│" | wc -l | tr -d ' ')
if [ "$count" -gt 0 ]; then
    echo "You have $count document(s) in your Toss inbox. Run 'toss inbox' to see them."
fi
