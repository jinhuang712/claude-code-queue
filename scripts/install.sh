#!/usr/bin/env bash
# Install claude-code-queue into ~/.claude (hooks + command + skill + settings).
# Idempotent: safe to re-run. Requires Python 3 (already a Claude Code dep).
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
# this script lives in scripts/; the repo root (hooks/, commands/, SKILL.md) is its parent
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing claude-code-queue → $CLAUDE_DIR"

mkdir -p "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/commands" "$CLAUDE_DIR/skills/claude-code-queue"

cp "$SRC/hooks/queue-hook.py" "$CLAUDE_DIR/hooks/queue-hook.py"
chmod +x "$CLAUDE_DIR/hooks/queue-hook.py"
cp "$SRC/commands/queue.md"   "$CLAUDE_DIR/commands/queue.md"
cp "$SRC/SKILL.md"            "$CLAUDE_DIR/skills/claude-code-queue/SKILL.md"

# Wire hooks into settings.json (idempotent).
CLAUDE_DIR="$CLAUDE_DIR" python3 - "$CLAUDE_DIR/settings.json" <<'PY'
import json, os, sys
settings_path = sys.argv[1]
claude_dir = os.environ["CLAUDE_DIR"]
hook = os.path.join(claude_dir, "hooks", "queue-hook.py")

try:
    with open(settings_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
except FileNotFoundError:
    cfg = {}

hooks = cfg.setdefault("hooks", {})

def add_hook(event, command):
    arr = hooks.setdefault(event, [])
    for entry in arr:
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return False
    arr.append({"hooks": [{"type": "command", "command": command}]})
    return True

added = []
if add_hook("UserPromptSubmit", f"python3 '{hook}' enqueue"):
    added.append("UserPromptSubmit(enqueue)")
if add_hook("Stop", f"python3 '{hook}' deliver"):
    added.append("Stop(deliver)")

with open(settings_path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

print("  hooks: " + (", ".join(added) if added else "already present (no change)"))
PY

echo
echo "✓ Done. Restart Claude Code (or start a new session) so the hooks load."
echo "  Usage:  /queue 请帮我...   (while Claude is busy OR idle)"
