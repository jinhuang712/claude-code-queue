#!/usr/bin/env bash
# Remove claude-code-queue hooks from settings.json and delete installed files.
# The queue directory (~/.claude/queue) is preserved in case it holds items.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
echo "Uninstalling claude-code-queue from $CLAUDE_DIR"

# Remove hook entries from settings.json.
if [ -f "$CLAUDE_DIR/settings.json" ]; then
  python3 - "$CLAUDE_DIR/settings.json" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)
hooks = cfg.get("hooks", {})
for event in ("UserPromptSubmit", "Stop"):
    arr = hooks.get(event, [])
    kept = []
    for entry in arr:
        hs = entry.get("hooks", [])
        if any("queue-hook.py" in h.get("command", "") for h in hs):
            continue
        kept.append(entry)
    if arr:
        hooks[event] = kept
with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print("  removed queue-hook entries from settings.json")
PY
fi

rm -f "$CLAUDE_DIR/hooks/queue-hook.py"
rm -f "$CLAUDE_DIR/commands/queue.md"
rm -rf "$CLAUDE_DIR/skills/claude-code-queue"
echo "✓ Done. (Queue data at $CLAUDE_DIR/queue left untouched.)"
