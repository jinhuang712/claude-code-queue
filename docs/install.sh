#!/usr/bin/env bash
# claude-code-queue — installer for the /queue skill.
#
#   curl -fsSL https://jinhuang712.github.io/claude-code-queue/install.sh | bash
#
# Installs a single file — SKILL.md — into ~/.claude/skills/queue/. That folder
# name (queue) is what registers the bare /queue command. It ships as a
# standalone skill, NOT a plugin, on purpose: a plugin would always namespace
# the command as /queue:queue. See the repo README for the full reasoning.
#
# Re-running updates the skill in place. To uninstall: rm -rf ~/.claude/skills/queue
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/jinhuang712/claude-code-queue/master"
DEST="${HOME}/.claude/skills/queue"

command -v curl >/dev/null 2>&1 || { echo "error: curl is required" >&2; exit 1; }

echo "Installing the /queue skill → ${DEST}"
mkdir -p "${DEST}"
curl -fsSL "${REPO_RAW}/SKILL.md" -o "${DEST}/SKILL.md"

echo "✓ Done. Restart Claude Code (skills load at session start), then type /queue"
echo
echo "  If you previously installed the plugin version, remove it so the bare"
echo "  /queue wins over the namespaced /queue:queue — inside Claude Code run:"
echo "    /plugin uninstall queue@jinhuang712"
echo "    /plugin marketplace remove jinhuang712"
