#!/bin/bash
# Auto-sync toss spaces after file writes in space directories
SPACES_DIR="${HOME}/.toss/spaces"
# Only trigger if the tool wrote to a spaces directory
if echo "$TOOL_INPUT" | grep -q "$SPACES_DIR" 2>/dev/null; then
    cd /Users/hanhaoke/2026/project/toss && uv run toss space sync --quiet 2>/dev/null &
fi
