#!/bin/bash
# Auto-sync toss spaces after file writes in space directories
# Requires: toss installed globally (uv tool install .)
SPACES_DIR="${HOME}/.toss/spaces"
if ! command -v toss &>/dev/null; then
    exit 0
fi
# Only trigger if the tool wrote to a spaces directory
if echo "$TOOL_INPUT" | grep -q "$SPACES_DIR" 2>/dev/null; then
    toss space sync --quiet 2>/dev/null &
fi
