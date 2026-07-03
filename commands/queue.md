---
description: Queue a prompt to the waiting area — runs after the current turn, in this session only (Codex-style queue)
---

The `/queue` message has **already been placed in the waiting area** by the UserPromptSubmit hook (scoped to this session). You do not need to run any command — just acknowledge in one line and stop:

```
📝 已入队·等候区
```

Do not work on the queued request now. If you were mid-task, immediately resume that task after the one-line ack. The queued item will be popped and auto-started automatically when the current turn ends.

If `$ARGUMENTS` is empty, run this instead to show the queue:

```bash
python3 "$HOME/.claude/hooks/queue-hook.py" list
```
